"""
competitor_discovery.py
「CORE HARI FACEの集客につながる競合分析」のための競合自動発見モジュール。

accounts.py で競合・参考アカウントを手入力管理する方式は廃止した。
代わりに、このモジュールが main.py 実行のたびに以下を行う。

【STEP1】Instagram全体からハッシュタグ経由でリールを広く取得する
         (Apify: apify/instagram-hashtag-scraper)
【STEP2】投稿者(ユーザー名)単位で集計し、以下をすべて満たすアカウントのみを
         競合候補として抽出する
         - 日本語アカウント(キャプション/ハッシュタグに日本語が含まれる)
         - 美容ジャンルの場合: 美容・エステ・小顔・整体・表情筋・スキンケア・
           美容医療関連のキーワードに合致する
         - 直近20日以内に投稿
         - 再生数5万以上
         - 再生数 >= フォロワー数
         のうえで、average_views / max_views / view_multiplier(平均再生倍率)を
         アカウント単位で計算する
【STEP3】competitors.xlsx を自動生成する
         (username, followers, average_views, max_views, view_multiplier,
          category, profile_url)
【STEP4】この競合リストのユーザー名を、翌日以降ではなく「この実行内で」
         そのままapify_fetcher.fetch_beauty_trend_posts() /
         fetch_general_trend_posts() の取得対象として使う
         (main.py 実行ごとに毎回、発見〜更新〜分析までを一気通貫で行う)

※ apify/instagram-hashtag-scraper はハッシュタグ単位の投稿/リール取得に
   特化したActorで、本プロジェクトで過去に失敗した apify/instagram-scraper の
   ハッシュタグ検索機能(search + searchType="hashtag")とは別物。
   ただし出力にフォロワー数が含まれない場合があるため、フォロワー数が
   1件も取得できなかったアカウントのみ、追加で apify/instagram-profile-scraper
   にプロフィール情報(フォロワー数)を問い合わせる。
"""

import datetime as dt
import re

from apify_fetcher import (
    CATEGORY_BEAUTY,
    CATEGORY_GENERAL,
    _extract_followers,
    _get_client,
    _get_first,
    _normalize_post,
    _run_actor_and_collect,
    _to_int_or_none,
    _to_username,
)

# --- Apify Actor設定 ---
# Instagram全体からハッシュタグ経由でリールを発見するための専用Actor。
# 参考: https://apify.com/apify/instagram-hashtag-scraper/input-schema
DISCOVERY_ACTOR_ID = "apify/instagram-hashtag-scraper"

# ハッシュタグ検索の結果にフォロワー数が含まれないアカウントのみ、
# プロフィール情報を別途取得するためのActor。
# 参考: https://apify.com/apify/instagram-profile-scraper/input-schema
PROFILE_ACTOR_ID = "apify/instagram-profile-scraper"

# 1ハッシュタグあたりの取得件数上限
DISCOVERY_RESULTS_LIMIT_PER_HASHTAG = 30

# --- 競合候補の抽出条件(STEP2) ---
RECENT_DAYS_DISCOVERY = 20
MIN_VIEWS_DISCOVERY = 50_000

COMPETITORS_FILE_PATH = "competitors.xlsx"
COMPETITORS_COLUMNS = [
    "username",
    "followers",
    "average_views",
    "max_views",
    "view_multiplier",
    "category",
    "profile_url",
]

# --- STEP1で検索するハッシュタグ ---
# A. 美容ジャンル(顔トレ・小顔・たるみ改善・表情筋トレーニング等)
BEAUTY_DISCOVERY_HASHTAGS = [
    "小顔",
    "小顔矯正",
    "顔トレ",
    "顔ヨガ",
    "表情筋トレーニング",
    "たるみ改善",
    "ほうれい線",
    "リフトアップ",
    "美容整体",
    "フェイシャルエステ",
    "スキンケア",
    "美容医療",
    "エステ",
]

# B. Instagram全体トレンド(ジャンル不問で伸びているリールを広く発見する)
GENERAL_DISCOVERY_HASHTAGS = [
    "リール",
    "バズリール",
    "リール動画",
    "おすすめにのりたい",
    "トレンド",
]

# 美容ジャンルかどうかを判定するためのキーワード(STEP2のカテゴリ条件)
BEAUTY_CATEGORY_KEYWORDS = [
    "美容",
    "エステ",
    "小顔",
    "整体",
    "表情筋",
    "スキンケア",
    "美容医療",
    "たるみ",
    "リフトアップ",
    "フェイシャル",
    "顔トレ",
    "顔ヨガ",
    "ほうれい線",
]

_JAPANESE_PATTERN = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")


def _is_japanese_text(text: str) -> bool:
    """キャプション/ハッシュタグに日本語(ひらがな・カタカナ・漢字)が
    含まれるかどうかで「日本語アカウント」を簡易的に判定する。"""
    return bool(_JAPANESE_PATTERN.search(text or ""))


def _matches_category_keywords(text: str, keywords: list) -> bool:
    lowered = (text or "").lower()
    return any(kw.lower() in lowered for kw in keywords)


def _lookup_followers(client, usernames: list) -> dict:
    """
    apify/instagram-hashtag-scraper の出力にフォロワー数が含まれなかった
    アカウントについて、apify/instagram-profile-scraper でフォロワー数のみを
    追加取得する。戻り値は {username: followers} の辞書。
    """
    if not usernames:
        return {}

    print(f"フォロワー数を確認中: {len(usernames)}アカウント (プロフィール取得)")
    raw_items = _run_actor_and_collect(
        client, PROFILE_ACTOR_ID, {"usernames": usernames}
    )

    result = {}
    for item in raw_items:
        username = _to_username(
            _get_first(item, ["username", "ownerUsername", "userName"], "") or ""
        )
        if not username:
            continue

        followers = _extract_followers(item)
        if followers is None:
            followers = _to_int_or_none(
                _get_first(
                    item, ["followersCount", "followerCount", "followers"], None
                )
            )
        if followers is not None:
            result[username] = followers

    return result


def discover_competitors(
    category: str,
    hashtags: list,
    category_keywords: list = None,
    require_category_match: bool = False,
) -> list:
    """
    STEP1〜STEP2: 指定ハッシュタグ群からInstagram全体のリールを取得し、
    競合候補となるアカウントを集計・抽出する。

    戻り値: [{username, followers, average_views, max_views,
              view_multiplier, category, profile_url}, ...]
            (average_viewsの多い順)
    """
    client = _get_client()

    hashtags_clean = [h.lstrip("#").strip() for h in hashtags if h and h.strip()]
    if not hashtags_clean:
        return []

    run_input = {
        "hashtags": hashtags_clean,
        "resultsType": "reels",
        "resultsLimit": DISCOVERY_RESULTS_LIMIT_PER_HASHTAG,
    }

    print(f"競合発見中: {category} / ハッシュタグ{len(hashtags_clean)}件から探索")
    raw_items = _run_actor_and_collect(client, DISCOVERY_ACTOR_ID, run_input)

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=RECENT_DAYS_DISCOVERY)
    by_username = {}

    for item in raw_items:
        owner_username = (
            _get_first(item, ["ownerUsername", "username", "userName"], "") or ""
        )
        post = _normalize_post(item, source_account=owner_username, category=category)

        username = _to_username(post.get("username") or owner_username)
        if not username:
            continue

        if not post.get("is_reel"):
            continue

        posted_at_dt = post.get("posted_at_dt")
        if posted_at_dt is None or posted_at_dt < cutoff:
            continue

        if post.get("views", 0) < MIN_VIEWS_DISCOVERY:
            continue

        text = f"{post.get('caption', '')} " + " ".join(post.get("hashtags") or [])
        if not _is_japanese_text(text):
            continue

        if require_category_match and category_keywords:
            if not _matches_category_keywords(text, category_keywords):
                continue

        by_username.setdefault(username, []).append(post)

    if not by_username:
        print(f"{category}: 競合候補となるアカウントが見つかりませんでした")
        return []

    # ハッシュタグ検索の結果に1件もフォロワー数が含まれなかったアカウントのみ、
    # プロフィール情報を追加取得する(Apify呼び出しコストを抑えるため)。
    usernames_needing_followers = [
        username
        for username, posts in by_username.items()
        if all(p.get("followers") is None for p in posts)
    ]
    followers_lookup = _lookup_followers(client, usernames_needing_followers)

    candidates = []
    for username, posts in by_username.items():
        followers = None
        for p in posts:
            if p.get("followers") is not None:
                followers = p["followers"]
                break
        if followers is None:
            followers = followers_lookup.get(username)

        if followers is None:
            # フォロワー数が最後まで取得できなければ競合候補にしない
            # (再生数 >= フォロワー数 の判定ができないため)
            continue

        qualifying_posts = [p for p in posts if p.get("views", 0) >= followers]
        if not qualifying_posts:
            continue

        views_list = [p["views"] for p in qualifying_posts]
        multipliers = [round(v / followers, 2) for v in views_list]

        candidates.append(
            {
                "username": username,
                "followers": followers,
                "average_views": round(sum(views_list) / len(views_list)),
                "max_views": max(views_list),
                "view_multiplier": round(sum(multipliers) / len(multipliers), 2),
                "category": category,
                "profile_url": f"https://www.instagram.com/{username}/",
            }
        )

    candidates.sort(key=lambda c: c["average_views"], reverse=True)
    print(f"{category}: 競合候補 {len(candidates)}件を発見しました")
    return candidates


def save_competitors_file(rows: list, path: str = COMPETITORS_FILE_PATH) -> None:
    """STEP3: 発見した競合候補をcompetitors.xlsxに書き出す(毎回上書き)。"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "competitors"
    ws.append(COMPETITORS_COLUMNS)
    for row in rows:
        ws.append([row.get(col, "") for col in COMPETITORS_COLUMNS])
    wb.save(path)
    print(f"{path} を保存しました({len(rows)}件)")


def discover_all_competitors() -> tuple:
    """
    STEP1〜STEP4のうち発見〜保存までを一括で行うエントリーポイント。
    main.py から呼び出され、美容トレンド/Instagram全体トレンドそれぞれの
    競合候補リストを返す(この戻り値のusernameがそのまま次の取得対象になる)。
    """
    beauty_competitors = discover_competitors(
        CATEGORY_BEAUTY,
        BEAUTY_DISCOVERY_HASHTAGS,
        category_keywords=BEAUTY_CATEGORY_KEYWORDS,
        require_category_match=True,
    )
    general_competitors = discover_competitors(
        CATEGORY_GENERAL,
        GENERAL_DISCOVERY_HASHTAGS,
        category_keywords=None,
        require_category_match=False,
    )

    save_competitors_file(beauty_competitors + general_competitors)

    return beauty_competitors, general_competitors
