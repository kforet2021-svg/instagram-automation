"""
trend_evidence.py

Hook候補ごとに「どこで話題になっているか」を調査し、根拠レベルを付与する。

取得できる情報源（現時点）:
  ✅ Instagram — reels シートに蓄積済みの投稿データ（キーワード一致）
  ✅ 季節・気候コンテキスト — world_context.get_season_context()（月次固定値）
  ✅ 過去フック実績 — hook_library シートのデータ
  ❌ Threads / X / Google Trends / ニュース / 美容メディア / 実際の気象 — 未取得

根拠レベル:
  A: 複数媒体で話題（異なる2媒体以上）
  B: 1媒体で強い反応
  C: 季節性・社会背景あり
  D: 過去実績あり（自分のアカウント）
  E: AIオリジナル（外部トレンド・実績・季節性いずれも確認できない）

【2026-07-17: 新規作成】
  - gather_evidence(): 候補リストに証拠フィールドを追加して返す
  - _search_reels_sheet(): reels シートからキーワード一致投稿を検索
  - _search_hook_library(): hook_library シートから過去実績を検索
  - _assign_level(): A〜Eの根拠レベルを決定
"""

from __future__ import annotations

import datetime
import re
from typing import Optional

# reels シートで照合するキーワード抽出対象フィールド（優先順）
_REELS_TEXT_FIELDS = ["キャプション全文", "投稿URL"]

# 「実績あり」と見なすいいね数の閾値
_LIKES_THRESHOLD = 50

# 最近N日以内の投稿を「直近トレンド」として扱う
_RECENCY_DAYS = 45


def gather_evidence(
    candidates: list[dict],
    world_ctx: dict,
    instagram_fetched_today: int = -1,
) -> list[dict]:
    """
    候補リスト全件に証拠フィールドを付与して返す。
    Sheet取得失敗時も候補自体は返す（証拠ゼロ＝Eレベル）。

    instagram_fetched_today: 今回実行で取得したInstagram投稿件数。
      -1 = 不明（通常実行）
       0 = 取得0件（reelsシートの過去データをInstagram根拠に使わない、最高レベルC）
    """
    checked_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    ig_zero_today = (instagram_fetched_today == 0)

    # 一度だけシートを読み込む
    # Instagram取得0件のときは reels シートを読まない（過去キャッシュを根拠に使わない）
    reels_rows = [] if ig_zero_today else _load_reels_sheet()
    hook_lib_rows = _load_hook_library()

    enriched = []
    for c in candidates:
        c = dict(c)  # コピーして元を変更しない

        keyword = _extract_keyword(c)

        # Topic と関連するキーワードリストを作成（意味的フィルタ用）
        topic_keywords: list[str] = []
        for field in ("perspective", "theme", "hook", "angle"):
            val = c.get(field, "") or ""
            if val:
                topic_keywords.append(val)

        # Instagram 証拠（今回0件の場合は強制的に空リスト）
        ig_hits_raw = _search_reels_sheet(reels_rows, keyword)

        # 意味的関連フィルタ: Topic と無関係な投稿（AI・針美容液・スキンケア等）を除外
        # relevance_score 60未満は採用しない、有効件数だけ表示（最大5件を無理に埋めない）
        ig_hits = filter_ig_hits_by_relevance(ig_hits_raw, topic_keywords)
        filtered_out = len(ig_hits_raw) - len(ig_hits)
        if filtered_out > 0:
            print(
                f"  [関連性フィルタ] {keyword}: {len(ig_hits_raw)}件中{filtered_out}件を除外"
                f" → 有効{len(ig_hits)}件"
            )
        if len(ig_hits) < 3 and len(ig_hits) > 0:
            print(
                f"  [Instagram根拠不足] {keyword}: 有効参考{len(ig_hits)}件のみ"
                f"（3件未満 — 無理に埋めません）"
            )
        elif len(ig_hits) == 0 and len(ig_hits_raw) > 0:
            print(
                f"  [Instagram根拠なし] {keyword}: 全{len(ig_hits_raw)}件がTopicと無関係のため除外"
            )

        # 過去実績
        own_hits = _search_hook_library(hook_lib_rows, keyword)
        # 季節性
        seasonal = _get_seasonal_evidence(world_ctx, keyword)

        level, level_reason = _assign_level(ig_hits, own_hits, seasonal,
                                            ig_zero_today=ig_zero_today)

        # 参考URL（有効件数のみ・最大5件まで、無理に埋めない）
        ref_urls = [h["url"] for h in ig_hits]
        ref_dates = [h.get("date", "") for h in ig_hits]

        # 各媒体の証拠テキスト
        ig_evidence = _format_ig_evidence(ig_hits)

        c.update({
            "trend_sources":          _build_sources_text(ig_hits, seasonal, own_hits),
            "trend_source_count":     len(ig_hits),
            "trend_level":            level,
            "trend_reason":           level_reason,
            "trend_checked_at":       checked_at,
            "reference_urls":         "\n".join(ref_urls),
            "reference_dates":        "\n".join(ref_dates),
            "instagram_evidence":     ig_evidence,
            "x_evidence":             "未取得",
            "threads_evidence":       "未取得",
            "google_trends_evidence": "未取得",
            "news_evidence":          "未取得",
            "seasonal_evidence":      seasonal or "なし",
            "own_account_evidence":   _format_own_evidence(own_hits),
            "competitor_evidence":    "未取得",
            "ai_original_flag":       "1" if level == "E" else "0",
        })
        enriched.append(c)

    return enriched


# ── 内部ヘルパー ──────────────────────────────────────────────────────────────

def _extract_keyword(candidate: dict) -> str:
    """候補から検索キーワードを抽出する。perspective > theme > hookの順で採用。"""
    for key in ("perspective", "theme", "hook"):
        v = candidate.get(key, "")
        if v and len(v) >= 2:
            # 「〜する前に」「〜な人へ」などの修飾語を除いて体言止めにする
            v = re.sub(r"(する前に|していますか|している|してしまう|してから|という|からです|ために|ため|による|として)", "", v)
            # 最初の5〜8文字を使う（過剰一致防止）
            return v[:8].strip()
    return ""


def _load_reels_sheet() -> list[list[str]]:
    """reels シートの全行を返す。失敗時は空リスト。"""
    try:
        from sheets_writer import _get_or_create_worksheet
        ws = _get_or_create_worksheet("reels", [])
        rows = ws.get_all_values()
        return rows if len(rows) >= 2 else []
    except Exception:
        return []


def _load_hook_library() -> list[list[str]]:
    """hook_library シートの全行を返す。失敗時は空リスト。"""
    try:
        from sheets_writer import _get_or_create_worksheet
        ws = _get_or_create_worksheet("hook_library", [])
        rows = ws.get_all_values()
        return rows if len(rows) >= 2 else []
    except Exception:
        return []


def _search_reels_sheet(rows: list[list[str]], keyword: str) -> list[dict]:
    """
    reels シートからキーワードに一致する投稿を返す。
    取得フィールド: url, likes, plays, saves, date, caption_snippet
    """
    if not rows or not keyword:
        return []

    headers = rows[0]

    def _col(name: str) -> int:
        try:
            return headers.index(name)
        except ValueError:
            return -1

    url_i     = _col("投稿URL")
    cap_i     = _col("キャプション全文")
    likes_i   = _col("いいね数")
    plays_i   = _col("再生数")
    saves_i   = _col("保存数")
    date_i    = _col("投稿日")

    if url_i < 0:
        return []

    def _int(row: list, i: int) -> int:
        if i < 0 or i >= len(row):
            return 0
        try:
            return int(float(row[i])) if row[i] else 0
        except (ValueError, TypeError):
            return 0

    cutoff = datetime.datetime.now() - datetime.timedelta(days=_RECENCY_DAYS)

    hits = []
    for row in rows[1:]:
        url = row[url_i] if url_i < len(row) else ""
        cap = row[cap_i] if cap_i >= 0 and cap_i < len(row) else ""
        text = (url + " " + cap).lower()

        if keyword.lower() not in text:
            continue

        # 日付チェック（あれば）
        date_str = row[date_i] if date_i >= 0 and date_i < len(row) else ""
        if date_str:
            try:
                post_date = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
                if post_date < cutoff:
                    continue
            except ValueError:
                pass

        hits.append({
            "url":              url,
            "likes":            _int(row, likes_i),
            "plays":            _int(row, plays_i),
            "saves":            _int(row, saves_i),
            "date":             date_str[:10] if date_str else "",
            "caption_snippet":  cap[:60] if cap else "",
        })

    # いいね数 > 再生数 > 保存数 の順でソート
    hits.sort(key=lambda h: (h["likes"], h["plays"], h["saves"]), reverse=True)
    return hits[:5]


def _search_hook_library(rows: list[list[str]], keyword: str) -> list[dict]:
    """hook_library シートからキーワードに一致する過去フックを返す。"""
    if not rows or not keyword:
        return []

    headers = rows[0]

    def _col(name: str) -> int:
        try:
            return headers.index(name)
        except ValueError:
            return -1

    hook_i  = _col("hook")
    theme_i = _col("theme")
    rate_i  = _col("success_rate")

    hits = []
    for row in rows[1:]:
        hook  = row[hook_i]  if hook_i  >= 0 and hook_i  < len(row) else ""
        theme = row[theme_i] if theme_i >= 0 and theme_i < len(row) else ""
        if keyword.lower() in (hook + " " + theme).lower():
            hits.append({
                "hook":         hook,
                "theme":        theme,
                "success_rate": row[rate_i] if rate_i >= 0 and rate_i < len(row) else "",
            })

    return hits[:3]


def _get_seasonal_evidence(world_ctx: dict, keyword: str) -> str:
    """
    world_ctx から季節・気候の関連性テキストを返す。
    関連なければ空文字。
    """
    season     = world_ctx.get("season", "")
    month_ctx  = world_ctx.get("month_context", "")
    hot        = world_ctx.get("hot_tension", "")
    brand_ctx  = world_ctx.get("brand_relevant_context", "") or world_ctx.get("social_trends", "")

    # キーワードが季節コンテキストに含まれているか確認
    ctx_text = " ".join([season, month_ctx, hot, brand_ctx])
    if keyword and keyword.lower() in ctx_text.lower():
        return f"{season}の時期。{month_ctx}".strip(" 。")
    # 季節だけでも何か言えれば
    if season and month_ctx:
        return f"{season}（月次気候コンテキスト: {month_ctx[:30]}）"
    return ""


def _has_valid_instagram_evidence(ig_hits: list[dict], min_count: int = 3) -> bool:
    """
    Instagram根拠として有効かどうかを判定する。
    - 有効件数が min_count 未満 → 無効
    - 再生数が取得できている件数が0 → 最上位根拠に使わない
    """
    if len(ig_hits) < min_count:
        return False
    # 再生数が1件も取れていない場合は根拠として弱い
    has_views = any(h.get("plays", 0) for h in ig_hits)
    return has_views


# 無関係ジャンルキーワード（CORE HARIのTopicと無関係な美容一般コンテンツ）
_IRRELEVANT_KEYWORDS = [
    "AI", "人工知能", "ChatGPT", "針美容液", "美容液", "スキンケア", "美白", "美肌",
    "SPF", "UVケア", "日焼け止め", "サプリメント", "ダイエット", "痩身", "ファッション",
    "コーデ", "メイク", "リップ", "アイシャドウ", "ファンデ", "ネイル", "料理", "レシピ",
    "インテリア", "旅行", "ヘアカラー", "まつ毛", "脱毛", "ボトックス", "フィラー",
]

# CORE HARI専門分野キーワード（これらが含まれると relevance_score が上がる）
_CORE_HARI_DOMAIN_KEYWORDS = [
    "咬筋", "顎", "舌", "舌骨", "首", "胸郭", "頭皮", "表情筋", "顔筋",
    "呼吸", "姿勢", "骨盤", "肋骨", "後頭部", "噛み癖", "食いしばり",
    "左右差", "むくみ", "たるみ", "小顔", "顔の歪み", "筋膜", "リンパ",
    "エステ", "矯正", "施術", "顔専門", "フェイシャル",
]

# 意味的関連スコアの最低ライン（これ未満は参考表示しない）
_MIN_RELEVANCE_SCORE = 60


def _compute_relevance_score(hit: dict, topic_keywords: list[str]) -> int:
    """
    投稿とTopicの意味的関連スコアを 0〜100 で返す。

    採点方法:
      - 無関係ジャンルキーワードが含まれる → 即0点
      - topic_keywords との一致ごとに +30点（上限60点）
      - CORE HARI専門ドメイン語との一致ごとに +20点（上限40点）
    """
    cap       = (hit.get("caption", "") or hit.get("caption_snippet", "") or "").lower()
    title     = (hit.get("title", "") or "").lower()
    url       = (hit.get("url", "") or "").lower()
    combined  = f"{cap} {title} {url}"

    # 無関係ジャンル → 即0点
    if any(irr.lower() in combined for irr in _IRRELEVANT_KEYWORDS):
        return 0

    score = 0

    # Topic キーワードとの一致
    for kw in topic_keywords:
        if kw and kw.lower() in combined:
            score += 30
    score = min(score, 60)

    # CORE HARI 専門ドメイン語との一致
    for domain_kw in _CORE_HARI_DOMAIN_KEYWORDS:
        if domain_kw.lower() in combined:
            score += 20
            break  # 1件見つかれば加点は1回のみ
    score = min(score, 100)

    return score


def filter_ig_hits_by_relevance(
    ig_hits: list[dict],
    topic_keywords: list[str],
    min_score: int = _MIN_RELEVANCE_SCORE,
) -> list[dict]:
    """
    参考Instagram投稿のうち、topicとの意味的関連スコアが min_score 未満のものを除外する。

    topic_keywords: テーマを表すキーワードリスト（例: ["咬筋", "左右差"]）
    min_score: この値未満は参考根拠に採用しない（デフォルト60）
    有効件数だけ返す（最大5件を無理に埋めない）。
    """
    if not topic_keywords:
        return ig_hits

    relevant = []
    for hit in ig_hits:
        score = _compute_relevance_score(hit, topic_keywords)
        if score >= min_score:
            relevant.append({**hit, "relevance_score": score})

    # 関連スコア降順でソート
    relevant.sort(key=lambda h: h.get("relevance_score", 0), reverse=True)
    return relevant


def _assign_level(
    ig_hits: list[dict],
    own_hits: list[dict],
    seasonal: str,
    ig_zero_today: bool = False,
) -> tuple[str, str]:
    """
    根拠レベル A〜E を決定する。

    ig_zero_today=True の場合:
      - Instagram根拠は使用不可（今回取得0件のため）
      - 最高レベルは C（レベルA・Bは禁止）

    追加ルール:
      - Instagram根拠が3件未満、または再生数が1件も取れていない場合はA/Bにしない
      - いいね数だけで伸びている投稿（再生数0）は最上位根拠に使わない

    Returns: (level, reason_text)
    """
    has_instagram = len(ig_hits) > 0 and not ig_zero_today
    has_own       = len(own_hits) > 0
    has_seasonal  = bool(seasonal)
    # 有効なInstagram根拠（件数・再生数チェック通過）
    ig_valid = has_instagram and _has_valid_instagram_evidence(ig_hits, min_count=3)

    # A: Instagram あり + 季節性あり（2媒体）
    # ig_zero_today のとき A は禁止; 有効根拠不足のときも A は禁止
    if ig_valid and has_seasonal and not ig_zero_today:
        count = len(ig_hits)
        reason = (
            f"Instagramの直近投稿{count}件でキーワードを確認。"
            f"かつ季節・気候コンテキストとも合致。"
        )
        return "A", reason

    # B: Instagramだけで複数件、または高いいいね数
    # ig_zero_today のとき B は禁止; 有効根拠不足のときも B は禁止
    if ig_valid and not ig_zero_today:
        top = ig_hits[0]
        count = len(ig_hits)
        reason = (
            f"Instagramの直近{_RECENCY_DAYS}日以内の投稿{count}件でキーワードを確認。"
            f"最高いいね: {top.get('likes', 0)}件。"
        )
        return "B", reason

    # Instagram hit はあるが有効根拠未満 → 不足ログ
    if has_instagram and not ig_valid and not ig_zero_today:
        count = len(ig_hits)
        plays_count = sum(1 for h in ig_hits if h.get("plays", 0))
        # Bには使えないが、Cの補足情報として保持
        pass

    # C: 季節性のみ
    if has_seasonal:
        prefix = "（Instagram取得0件のため根拠除外）" if ig_zero_today else ""
        reason = f"{prefix}季節・気候コンテキストから今扱う理由がある。（{seasonal[:50]}）"
        return "C", reason

    # D: 自分の過去実績のみ
    if has_own:
        reason = f"現在の外部トレンドは確認できないが、過去のhook_libraryに類似テーマあり（{own_hits[0].get('hook', '')[:30]}）。"
        return "D", reason

    # E: いずれも確認できない
    return "E", "外部トレンド・季節性・自分の実績いずれも確認できないAIオリジナル案。"


def _build_sources_text(
    ig_hits: list[dict],
    seasonal: str,
    own_hits: list[dict],
) -> str:
    """話題の情報源をまとめたテキストを返す。"""
    lines = []
    if ig_hits:
        lines.append(f"・Instagram: 直近{_RECENCY_DAYS}日で{len(ig_hits)}件")
    else:
        lines.append("・Instagram: 0件（未確認）")
    lines.append("・Threads: 未取得")
    lines.append("・X: 未取得")
    lines.append("・Google Trends: 未取得")
    lines.append("・ニュース: 未取得")
    if seasonal:
        lines.append(f"・季節・気候: {seasonal[:60]}")
    else:
        lines.append("・季節・気候: 直接的な関連なし")
    if own_hits:
        lines.append(f"・自分の過去実績（hook_library）: {len(own_hits)}件")
    else:
        lines.append("・自分の過去実績（hook_library）: 0件")
    lines.append("・競合アカウント分析: 未取得")
    return "\n".join(lines)


def _format_ig_evidence(ig_hits: list[dict]) -> str:
    """Instagram証拠を1行テキストにまとめる。"""
    if not ig_hits:
        return "0件（直近45日以内の一致投稿なし）"
    parts = []
    for h in ig_hits[:3]:
        parts.append(
            f"{h['url']} （いいね:{h['likes']} 再生:{h['plays']}）"
        )
    return "\n".join(parts)


def _format_own_evidence(own_hits: list[dict]) -> str:
    """過去実績を1行テキストにまとめる。"""
    if not own_hits:
        return "0件"
    return " / ".join(h.get("hook", "")[:30] for h in own_hits[:2])


# ── 表示ヘルパー ───────────────────────────────────────────────────────────────

LEVEL_LABELS = {
    "A": "A: 複数媒体で話題",
    "B": "B: 1媒体で強い反応",
    "C": "C: 季節性・社会背景あり",
    "D": "D: 過去実績あり",
    "E": "E: AIオリジナル／トレンド未確認",
}


def format_evidence_block(candidate: dict) -> str:
    """
    表示用の「根拠ブロック」テキストを返す（ターミナル表示用）。
    """
    level  = candidate.get("trend_level", "E")
    reason = candidate.get("trend_reason", "")
    sources = candidate.get("trend_sources", "（証拠収集なし）")
    ref_urls = candidate.get("reference_urls", "")
    seasonal = candidate.get("seasonal_evidence", "")
    own      = candidate.get("own_account_evidence", "")
    checked  = candidate.get("trend_checked_at", "")
    ai_flag  = candidate.get("ai_original_flag", "1") == "1"

    lines = []
    lines.append(f"  根拠レベル: {LEVEL_LABELS.get(level, level)}")
    if ai_flag:
        lines.append("  ⚠️  AIオリジナル案／トレンド未確認")
    lines.append(f"  確認日時: {checked}")
    lines.append("")
    lines.append("  話題の情報源:")
    for src_line in sources.splitlines():
        lines.append(f"    {src_line}")
    if ref_urls:
        lines.append("")
        lines.append("  参考URL:")
        for url in ref_urls.splitlines()[:3]:
            if url:
                lines.append(f"    {url}")
    if reason:
        lines.append("")
        lines.append(f"  採用理由: {reason}")
    return "\n".join(lines)


def evidence_score_post(post: dict) -> dict:
    """
    投稿ごとの Evidence スコアを計算する（0〜100各項目）。
    欠損値と0実績を区別する（None = 未取得, 0 = 実際に0）。

    Returns:
      {
        "recency_score": 0-100,
        "views_score": 0-100,
        "follower_ratio_score": 0-100,
        "like_rate_score": 0-100,
        "comment_rate_score": 0-100,
        "data_completeness_score": 0-100,
        "evidence_score": 0-100,
        "views_available": bool,
        "date_available": bool,
        "date_within_10days": bool,
      }
    """
    import datetime as _dt

    now = _dt.datetime.now(_dt.timezone.utc)

    # ── 投稿日 ────────────────────────────────────────────────────────────────
    date_available = False
    date_within_10 = False
    recency_score  = 0
    ts = post.get("timestamp") or post.get("post_date") or ""
    if ts:
        try:
            t = _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            # 未来日付・異常日付チェック
            if t > now + _dt.timedelta(days=1):
                pass  # 異常日付: スコアなし
            elif t > now - _dt.timedelta(days=365):
                date_available = True
                age_days = (now - t).days
                date_within_10 = age_days <= 10
                recency_score = max(0, 100 - age_days * 3)  # 33日で0点
        except Exception:
            pass

    # ── 再生数 ────────────────────────────────────────────────────────────────
    # 0 は「実際0再生」なので or で読み飛ばしてはいけない（None と区別する）
    if "play_count" in post and post["play_count"] is not None:
        raw_views = post["play_count"]
    elif "video_view_count" in post and post["video_view_count"] is not None:
        raw_views = post["video_view_count"]
    else:
        raw_views = None
    views_available = raw_views is not None  # None = 未取得, 0 = 実際0
    views = float(raw_views) if raw_views is not None else 0.0
    views_score = 0
    if views_available:
        views_score = min(100, int(views / 10000))  # 100万再生で100点

    # ── フォロワー比 ──────────────────────────────────────────────────────────
    followers = post.get("followers") or post.get("followers_count") or 0
    follower_ratio_score = 0
    if followers > 0 and views_available and views > 0:
        ratio = views / followers
        follower_ratio_score = min(100, int(ratio * 50))

    # ── いいね率・コメント率 ──────────────────────────────────────────────────
    likes    = post.get("like_count") or post.get("likes_count") or 0
    comments = post.get("comment_count") or post.get("comments_count") or 0
    denom    = followers if followers > 0 else None
    like_rate_score    = min(100, int(likes / denom * 1000)) if denom else 0
    comment_rate_score = min(100, int(comments / denom * 5000)) if denom else 0

    # ── データ完全性 ──────────────────────────────────────────────────────────
    fields_available = sum([
        date_available, views_available,
        followers > 0, likes > 0,
    ])
    data_completeness_score = int(fields_available / 4 * 100)

    # ── 総合 evidence_score ───────────────────────────────────────────────────
    evidence_score = int(
        recency_score * 0.25 +
        views_score   * 0.25 +
        follower_ratio_score * 0.20 +
        like_rate_score      * 0.15 +
        data_completeness_score * 0.15
    )

    return {
        "recency_score":          recency_score,
        "views_score":            views_score,
        "follower_ratio_score":   follower_ratio_score,
        "like_rate_score":        like_rate_score,
        "comment_rate_score":     comment_rate_score,
        "data_completeness_score": data_completeness_score,
        "evidence_score":         evidence_score,
        "views_available":        views_available,
        "date_available":         date_available,
        "date_within_10days":     date_within_10,
    }


def compute_account_diversity_score(ig_hits: list[dict]) -> dict:
    """
    参考Instagram投稿のアカウント多様性を評価する。
    同一アカウントの連投は根拠件数を割り引く。
    最低3アカウントで類似テーマが確認できているかを評価する。

    Returns:
      {
        "unique_accounts": int,
        "account_diversity_score": 0-100,
        "effective_evidence_count": int,  # 重複割引後の実効件数
        "meets_multi_account_threshold": bool,  # 3アカウント以上
      }
    """
    if not ig_hits:
        return {
            "unique_accounts": 0,
            "account_diversity_score": 0,
            "effective_evidence_count": 0,
            "meets_multi_account_threshold": False,
        }

    account_counts: dict[str, int] = {}
    for h in ig_hits:
        acct = (h.get("account") or h.get("source_account") or h.get("username") or "unknown").lower()
        account_counts[acct] = account_counts.get(acct, 0) + 1

    unique = len(account_counts)
    # 重複割引: 同一アカウントの2件目以降は0.5件としてカウント
    effective = sum(1 + (cnt - 1) * 0.5 for cnt in account_counts.values())
    diversity_score = min(100, unique * 20)  # 5アカウントで100点

    return {
        "unique_accounts": unique,
        "account_diversity_score": diversity_score,
        "effective_evidence_count": int(effective),
        "meets_multi_account_threshold": unique >= 3,
    }
