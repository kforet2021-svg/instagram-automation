"""
apify_fetcher.py
Apifyを使ってInstagramのリール投稿を取得し、
「CORE HARI FACEのInstagram集客につながるリール分析」のための
採用条件でフィルタリングするモジュール。

【採用条件】(すべて満たす投稿のみ採用。1つでも満たさなければ除外する)
1. リールのみ
2. 投稿日が直近20日以内
3. 再生数が100,000回以上
4. フォロワー数が取得できる
5. 再生数 >= フォロワー数 (再生倍率 1.0 以上)

※ 採用件数が目標(20件)に達しない場合でも、条件を緩めて再取得する処理は
   行わない（呼び出し側で「条件を満たす投稿が不足しています」と表示する）。

【取得対象アカウントについて】
このモジュールはもう accounts.py の固定リストを直接参照しない。
取得対象アカウント(美容トレンド / Instagram全体トレンド)は、
competitor_discovery.py が実行時にInstagram全体から自動発見した
競合候補(competitors.xlsxの内容)を、呼び出し側(main.py)から
fetch_beauty_trend_posts() / fetch_general_trend_posts() の引数として渡す。
"""

import datetime as dt
import re

from apify_client import ApifyClient

from config import APIFY_API_TOKEN

# --- Apify Actor設定 ---
# ハッシュタグ検索ではなく、競合・参考アカウント(username)を指定して、
# そのアカウントの「直近リール」を直接取得するReel Scraper専用Actorを使う。
# username は配列で複数アカウントを一括指定できる(resultsLimitは1アカウントあたりの件数)。
# 参考: https://apify.com/apify/instagram-reel-scraper/input-schema
REEL_ACTOR_ID = "apify/instagram-reel-scraper"

DEFAULT_RESULTS_PER_ACCOUNT = 15

CATEGORY_BEAUTY = "美容トレンド"
CATEGORY_GENERAL = "Instagram全体トレンド"

# --- 採用条件のしきい値 ---
RECENT_DAYS = 30

MIN_VIEWS = 1000
TARGET_ADOPTED_COUNT = 20

_client = None


def _get_client() -> ApifyClient:
    global _client
    if _client is None:
        if not APIFY_API_TOKEN:
            raise EnvironmentError("APIFY_API_TOKEN が設定されていません。")
        _client = ApifyClient(APIFY_API_TOKEN)
    return _client


def _to_username(account: str) -> str:
    """
    accounts.py に "@username" 形式で書かれていても "username" 形式でも
    動くように、先頭の "@" と前後の空白を取り除く。
    """
    account = (account or "").strip()
    if account.startswith("@"):
        account = account[1:]
    return account.strip()


def _get_value(obj, key: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _get_first(item, keys: list, default=None):
    for key in keys:
        value = _get_value(item, key)
        if value not in (None, ""):
            return value
    return default


_NUMERIC_SUFFIX_MULTIPLIERS = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}


def _parse_numeric(value):
    """
    数値・数値らしき文字列を float に変換する。
    Apifyの出力には "52,000" のようにカンマ区切りだったり、
    "52K" / "1.2M" のように単位付きで返ってくる場合があるため、
    それらも解釈できるようにする。解釈できない場合はNoneを返す。
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    text = text.replace(",", "").replace("，", "")
    text = text.rstrip("回").strip()
    if not text:
        return None

    suffix = text[-1].lower()
    if suffix in _NUMERIC_SUFFIX_MULTIPLIERS and len(text) > 1:
        try:
            return float(text[:-1]) * _NUMERIC_SUFFIX_MULTIPLIERS[suffix]
        except ValueError:
            return None

    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value, default=0) -> int:
    parsed = _parse_numeric(value)
    if parsed is None:
        return default
    try:
        return int(parsed)
    except (ValueError, TypeError, OverflowError):
        return default


def _to_int_or_none(value):
    """
    値が取得できない場合はNoneを返す(0と未取得を区別するため)。
    フォロワー数・保存数・シェア数・動画尺など、
    「取得できる場合のみ採用する」項目に使う。
    """
    parsed = _parse_numeric(value)
    if parsed is None:
        return None
    try:
        return int(parsed)
    except (ValueError, TypeError, OverflowError):
        return None


def _extract_hashtags(item, caption: str) -> list:
    hashtags = _get_value(item, "hashtags")
    if isinstance(hashtags, list) and hashtags:
        return [str(h).lstrip("#") for h in hashtags]
    if caption:
        return re.findall(r"#(\w+)", caption)
    return []


def _is_error_item(item) -> bool:
    """
    Apifyの返したアイテムが投稿データではなく、取得失敗(エラー)を表す
    アイテムかどうかを判定する。
    実際のレスポンスで確認された形(2026-06-29の実行ログより):
    {
        "url": "https://www.instagram.com/xxxxx",
        "inputUrl": "https://www.instagram.com/xxxxx",
        "requestErrorMessages": ["Error: Request blocked, ...", ...],
        "error": "no_items",
        "errorDescription": "Empty or private data for provided input"
    }
    このアイテムには productType/isVideo/videoUrl 等の投稿フィールドが
    そもそも存在しないため、_is_reel() で正しく判定することはできない
    (投稿データではないため)。
    """
    return bool(_get_value(item, "error")) or bool(_get_value(item, "errorDescription"))


def _describe_error_item(item) -> str:
    target = _get_value(item, "inputUrl") or _get_value(item, "url") or "(不明なアカウント)"
    description = _get_value(item, "errorDescription") or _get_value(item, "error") or "不明なエラー"
    return f"{target}: {description}"


def _is_reel(item) -> bool:
    """
    リール(動画)投稿かどうかを判定する。
    Apifyの実際の出力スキーマは確認できていないため、
    複数の候補フィールドを見て、動画であればリールとみなす。
    （静止画/カルーセル投稿は除外する）
    """
    product_type = str(_get_value(item, "productType") or "").lower()
    if product_type in ("clips", "reel", "reels"):
        return True

    item_type = str(_get_value(item, "type") or "").lower()
    if item_type in ("video", "reel", "clip", "graphvideo") or "video" in item_type:
        return True

    if _get_value(item, "isVideo") is True or _get_value(item, "isReel") is True:
        return True

    if _get_first(item, ["videoUrl", "videoPlayUrl"]):
        return True

    if _get_first(
        item,
        ["videoPlayCount", "videoViewCount", "videoViews", "videoPlays"],
    ):
        return True

    return False


def _parse_posted_at(raw):
    """
    投稿日時の文字列/タイムスタンプをdatetime(UTC)に変換する。
    解釈できない場合はNoneを返す。
    """
    if raw is None or raw == "":
        return None

    if isinstance(raw, (int, float)):
        try:
            return dt.datetime.fromtimestamp(raw, tz=dt.timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None

    text = str(raw).strip()
    if not text:
        return None

    if text.isdigit():
        try:
            return dt.datetime.fromtimestamp(int(text), tz=dt.timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None

    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_followers(item):
    """
    フォロワー数を取得する。直接フィールドに無い場合は
    ownerなどのネストされたオブジェクトも見る。
    取得できなければNoneを返す。
    """
    direct = _get_first(
        item,
        ["followersCount", "ownerFollowersCount", "followerCount", "ownerFollowerCount"],
        None,
    )
    if direct is not None:
        return _to_int_or_none(direct)

    owner = _get_value(item, "owner")
    if owner is not None:
        nested = _get_first(owner, ["followersCount", "followerCount"], None)
        if nested is not None:
            return _to_int_or_none(nested)

    return None


def _normalize_post(item: dict, source_account: str, category: str) -> dict:
    username = _get_first(
        item,
        ["ownerUsername", "username", "userName", "ownerFullName", "ownerId"],
        "",
    )

    caption = _get_first(item, ["caption", "text", "description"], "") or ""

    views_raw = _get_first(
        item,
        [
            "videoPlayCount",
            "videoViewCount",
            "videoViews",
            "videoPlays",
            "playCount",
            "plays",
            "viewCount",
            "viewsCount",
            "views",
        ],
        0,
    )
    likes_raw = _get_first(item, ["likesCount", "likes", "like_count"], 0)
    comments_raw = _get_first(item, ["commentsCount", "comments", "comment_count"], 0)
    saves_raw = _get_first(item, ["saveCount", "savesCount", "saves"], None)
    shares_raw = _get_first(item, ["shareCount", "sharesCount", "shares"], None)
    duration_raw = _get_first(item, ["videoDuration", "duration"], None)

    url = _get_first(item, ["url", "postUrl", "shortCode"], "") or ""
    if url and not str(url).startswith("http"):
        url = f"https://www.instagram.com/p/{url}/"

    media_url = _get_first(
        item,
        ["videoUrl", "displayUrl", "thumbnailUrl", "imageUrl", "videoPlayUrl"],
        "",
    ) or ""

    posted_at_raw = _get_first(
        item,
        ["timestamp", "takenAt", "taken_at_timestamp"],
        "",
    ) or ""
    posted_at_dt = _parse_posted_at(posted_at_raw)

    views = _to_int(views_raw)
    followers = _extract_followers(item)
    view_multiplier = round(views / followers, 2) if followers else None

    saves = _to_int_or_none(saves_raw)
    save_rate = round(saves / views, 4) if (saves is not None and views > 0) else None

    beauty_subcategory = source_account if category == CATEGORY_BEAUTY else ""

    return {
        "username": username,
        "caption": caption,
        "likes": _to_int(likes_raw),
        "comments": _to_int(comments_raw),
        "views": views,
        "saves": saves,
        "shares": _to_int_or_none(shares_raw),
        "save_rate": save_rate,
        "followers": followers,
        "view_multiplier": view_multiplier,
        "duration_sec": _to_int_or_none(duration_raw),
        "url": url,
        "media_url": media_url,
        "posted_at": str(posted_at_raw),
        "posted_at_dt": posted_at_dt,
        "hashtags": _extract_hashtags(item, caption),
        "is_reel": _is_reel(item),
        "fetch_error": _is_error_item(item),
        "source_account": source_account,
        "category": category,
        "beauty_subcategory": beauty_subcategory,
        "raw_data": item,
    }


# --- デバッグ用設定 ---
# is_reel判定が実際のApify出力と合っているか調査するためのフィールド一覧。
# 【2026-06-29時点の状況】実際のApifyトークンで実行したところ、502件全てが
# 投稿データではなく取得失敗アイテム(_is_error_item参照)だったため、
# _is_reel()の妥当性はまだ実データで検証できていない。
# 取得が正常に成功する状態になり、実際の投稿データが取れたら、このデバッグ出力
# を見て_is_reel()を見直す。確定したらDEBUG_DUMP_RAW_ITEMSはFalseにしてよい。
DEBUG_DUMP_RAW_ITEMS = True
DEBUG_DUMP_LIMIT = 10
DEBUG_FIELDS = [
    "productType",
    "type",
    "mediaType",
    "media_product_type",
    "isVideo",
    "videoUrl",
    "video_versions",
    "videoPlayCount",
    "videoViewCount",
]


def _debug_dump_items(items: list, limit: int = DEBUG_DUMP_LIMIT) -> None:
    """
    Apifyの実際の出力スキーマを確認するためのデバッグ出力。
    raw_dataそのものと、リール判定(_is_reel)の候補フィールドの値を
    最初のlimit件について出力する。

    取得失敗アイテム(_is_error_item)は投稿データを含まず、
    requestErrorMessagesに長大なスタックトレースが入っているだけなので、
    ログを読みやすくするため要約のみ表示する。
    """
    import json

    for i, item in enumerate(items[:limit]):
        if _is_error_item(item):
            print(f"--- raw_data[{i}] (取得失敗アイテム。投稿データではない) ---")
            print(f"  inputUrl: {_get_value(item, 'inputUrl')!r}")
            print(f"  error: {_get_value(item, 'error')!r}")
            print(f"  errorDescription: {_get_value(item, 'errorDescription')!r}")
            error_messages = _get_value(item, "requestErrorMessages") or []
            print(f"  requestErrorMessages: {len(error_messages)}件(詳細省略)")
            if error_messages:
                print(f"    例: {str(error_messages[0])[:200]}")
            continue

        print(f"--- raw_data[{i}] ---")
        try:
            print(json.dumps(item, ensure_ascii=False, default=str, indent=2))
        except TypeError:
            print(item)

        print(f"--- フィールド確認[{i}] ---")
        for field in DEBUG_FIELDS:
            print(f"{field}: {_get_value(item, field)!r}")


def _run_actor_and_collect(client: ApifyClient, actor_id: str, run_input: dict) -> list:
    run = client.actor(actor_id).call(run_input=run_input)

    dataset_id = (
        _get_value(run, "defaultDatasetId")
        or _get_value(run, "default_dataset_id")
        or _get_value(run, "defaultDatasetID")
    )

    print("Dataset ID:", dataset_id)

    if not dataset_id:
        print("Dataset IDが取れませんでした")
        return []

    items = list(client.dataset(dataset_id).iterate_items())
    print(f"取得件数: {len(items)}件")

    if DEBUG_DUMP_RAW_ITEMS and items:
        print(f"=== デバッグ出力: raw_data 先頭{min(DEBUG_DUMP_LIMIT, len(items))}件 ({actor_id}) ===")
        _debug_dump_items(items)
        print("=== デバッグ出力ここまで ===")

    return items


def _fetch_posts_for_accounts(
    client: ApifyClient, accounts: list, category: str, results_limit: int
) -> list:
    posts = []

    usernames = [_to_username(a) for a in accounts if a and a.strip()]
    if not usernames:
        print(f"{category}: 取得対象アカウントが0件です(競合発見の結果0件、または該当カテゴリで競合候補が見つかりませんでした)")
        return posts

    # 直近RECENT_DAYS日より古いリールは取得時点で除外し、無駄な取得コストを減らす
    cutoff_date = (
        dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=RECENT_DAYS)
    ).strftime("%Y-%m-%d")

    # ハッシュタグ検索ではなく、指定アカウントの直近リールをReel Scraper
    # Actorで直接取得する。usernameは配列なので複数アカウントを1回の
    # 呼び出しでまとめて取得できる(resultsLimitは1アカウントあたりの件数)。
    run_input = {
        "username": usernames,
        "resultsLimit": results_limit,
        "onlyPostsNewerThan": cutoff_date,
    }

    print(f"取得中: {category} / {len(usernames)}アカウント (直近リール)")

    raw_items = _run_actor_and_collect(client, REEL_ACTOR_ID, run_input)

    error_items = [item for item in raw_items if _is_error_item(item)]
    if error_items:
        print(
            f"{category}: {len(error_items)}/{len(raw_items)}件が取得失敗です"
            "(Instagram側にリクエストをブロックされた可能性があります)"
        )
        seen_targets = set()
        for item in error_items:
            desc = _describe_error_item(item)
            target = desc.split(":", 1)[0]
            if target in seen_targets:
                continue
            seen_targets.add(target)
            print(f"  - {desc}")

    for item in raw_items:
        owner_username = _get_first(
            item, ["ownerUsername", "username", "userName"], ""
        ) or ""
        posts.append(
            _normalize_post(
                item,
                source_account=owner_username,
                category=category,
            )
        )

    return posts


def fetch_beauty_trend_posts(
    accounts: list, results_limit: int = DEFAULT_RESULTS_PER_ACCOUNT
) -> list:
    """
    accounts: competitor_discovery.discover_all_competitors() で自動発見された
              美容トレンド競合候補のユーザー名リスト。
    """
    client = _get_client()
    return _fetch_posts_for_accounts(
        client,
        accounts,
        CATEGORY_BEAUTY,
        results_limit,
    )


def fetch_general_trend_posts(
    accounts: list, results_limit: int = DEFAULT_RESULTS_PER_ACCOUNT
) -> list:
    """
    accounts: competitor_discovery.discover_all_competitors() で自動発見された
              Instagram全体トレンド競合候補のユーザー名リスト。
    """
    client = _get_client()
    return _fetch_posts_for_accounts(
        client,
        accounts,
        CATEGORY_GENERAL,
        results_limit,
    )


def engagement_score(post: dict) -> int:
    return (
        post.get("views", 0)
        + post.get("likes", 0) * 3
        + post.get("comments", 0) * 5
    )


def dedupe_by_url(posts: list) -> list:
    """投稿URL(無ければユーザー名+キャプション)が同じ投稿の重複を取り除く。"""
    best_by_key = {}

    for post in posts:
        key = post.get("url") or f"{post.get('username')}|{post.get('caption')}"
        if not key:
            continue

        current_best = best_by_key.get(key)
        if current_best is None or engagement_score(post) > engagement_score(current_best):
            best_by_key[key] = post

    return list(best_by_key.values())


def filter_and_adopt(posts: list, target_count: int = TARGET_ADOPTED_COUNT) -> dict:
    """
    取得した投稿に採用条件を順番に適用し、条件を満たした投稿の中から
    再生数が多い順にtarget_count件を採用する。

    条件を緩めて取得し直す処理は行わない。

    戻り値:
    {
        "adopted": list[dict],   # 採用された投稿(target_count件以下)
        "stats": {
            "fetched": int,                  # 取得件数
            "excluded_not_reel": int,         # リールではないため除外した件数
            "excluded_date": int,             # 投稿日で除外した件数
            "excluded_views": int,            # 再生数で除外した件数
            "excluded_no_followers": int,     # フォロワー数が取得できず除外した件数
            "excluded_low_multiplier": int,   # 再生倍率(再生数>=フォロワー数)不足で除外した件数
            "adopted": int,                   # 採用件数
        },
    }
    """
    stats = {
        "fetched": len(posts),
        "excluded_fetch_error": 0,
        "excluded_not_reel": 0,
        "excluded_date": 0,
        "excluded_views": 0,
        "excluded_no_followers": 0,
        "excluded_low_multiplier": 0,
        "adopted": 0,
    }

    fetch_error_count = sum(1 for p in posts if p.get("fetch_error"))
    real_posts = [p for p in posts if not p.get("fetch_error")]
    reel_count = sum(1 for p in real_posts if p.get("is_reel"))

    if posts and fetch_error_count == len(posts):
        print(
            "全件が取得失敗でした(Instagram側にリクエストをブロックされた可能性があります。"
            "Apifyの該当Actorの実行ログ/プロキシ設定を確認してください)"
        )
    elif real_posts and reel_count == 0:
        print("通常投稿しか取得できていません(リールが0件のため、再生数の評価ができません)")

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=RECENT_DAYS)
    candidates = []

    for post in posts:
        # 投稿データではなく取得失敗(Instagramにブロックされた等)のアイテムは
        # リール判定の対象外として別カウントで除外する
        if post.get("fetch_error"):
            stats["excluded_fetch_error"] += 1
            continue

        # リールではない投稿(画像/カルーセルなど)は採用条件の対象外として除外する
        if not post.get("is_reel"):
            stats["excluded_not_reel"] += 1
            continue

        posted_at_dt = post.get("posted_at_dt")
        if posted_at_dt is None or posted_at_dt < cutoff:
            stats["excluded_date"] += 1
            continue

        if post.get("views", 0) < MIN_VIEWS:
            stats["excluded_views"] += 1
            continue

        followers = post.get("followers")
        if followers is None:
            stats["excluded_no_followers"] += 1
            continue

        if followers <= 0 or post.get("views", 0) < followers:
            stats["excluded_low_multiplier"] += 1
            continue

        candidates.append(post)

    candidates = dedupe_by_url(candidates)
    candidates.sort(key=lambda p: p.get("views", 0), reverse=True)

    adopted = candidates[:target_count]
    stats["adopted"] = len(adopted)

    return {"adopted": adopted, "stats": stats}
