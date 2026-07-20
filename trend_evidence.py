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
) -> list[dict]:
    """
    候補リスト全件に証拠フィールドを付与して返す。
    Sheet取得失敗時も候補自体は返す（証拠ゼロ＝Eレベル）。
    """
    checked_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # 一度だけシートを読み込む
    reels_rows = _load_reels_sheet()
    hook_lib_rows = _load_hook_library()

    enriched = []
    for c in candidates:
        c = dict(c)  # コピーして元を変更しない

        keyword = _extract_keyword(c)

        # Instagram 証拠
        ig_hits = _search_reels_sheet(reels_rows, keyword)
        # 過去実績
        own_hits = _search_hook_library(hook_lib_rows, keyword)
        # 季節性
        seasonal = _get_seasonal_evidence(world_ctx, keyword)

        level, level_reason = _assign_level(ig_hits, own_hits, seasonal)

        # 参考URL（最大3件）
        ref_urls = [h["url"] for h in ig_hits[:3]]
        ref_dates = [h.get("date", "") for h in ig_hits[:3]]

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


def _assign_level(
    ig_hits: list[dict],
    own_hits: list[dict],
    seasonal: str,
) -> tuple[str, str]:
    """
    根拠レベル A〜E を決定する。

    Returns: (level, reason_text)
    """
    has_instagram = len(ig_hits) > 0
    has_own       = len(own_hits) > 0
    has_seasonal  = bool(seasonal)

    # A: Instagram あり + 季節性あり（2媒体）
    if has_instagram and has_seasonal:
        count = len(ig_hits)
        reason = (
            f"Instagramの直近投稿{count}件でキーワードを確認。"
            f"かつ季節・気候コンテキストとも合致。"
        )
        return "A", reason

    # B: Instagramだけで複数件、または高いいいね数
    if has_instagram:
        top = ig_hits[0]
        count = len(ig_hits)
        reason = (
            f"Instagramの直近{_RECENCY_DAYS}日以内の投稿{count}件でキーワードを確認。"
            f"最高いいね: {top.get('likes', 0)}件。"
        )
        return "B", reason

    # C: 季節性のみ
    if has_seasonal:
        reason = f"Instagram実績は確認できないが、季節・気候コンテキストから今扱う理由がある。（{seasonal[:50]}）"
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
