"""
notion_kb.py
CORE HARI Knowledge Base RAG — Notion からブランド知識を検索してプロンプトに注入する。

【設計方針】
- NOTION_API_KEY が未設定の場合はサイレントスキップ（Optional機能）
- NOTION_KB_DATABASE_ID が設定されている場合はそのDBを全件取得 → タイトル関連度順でランキング
- NOTION_KB_DATABASE_ID が未設定の場合はワークスペース全体を /search で検索
- requests（requirements.txt に既収録）のみを使用し、新規依存を追加しない
- エラーが発生しても例外を投げず [] を返す（メインフローを止めない）

【2026-07-31: 初回実装】
"""

import requests
from config import NOTION_API_KEY, NOTION_KB_DATABASE_ID

_NOTION_VERSION = "2022-06-28"
_BASE_URL = "https://api.notion.com/v1"
MAX_KB_PAGES = 5       # 1回あたりの最大返却ページ数
_MAX_DB_FETCH = 50     # DB全件取得の上限（小規模KBを想定）
_MAX_BLOCK_CHARS = 500  # ページあたりの最大テキスト文字数


def is_configured() -> bool:
    """NOTION_API_KEY が設定されているかどうか。"""
    return bool(NOTION_API_KEY)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _get_page_title(page: dict) -> str:
    """Notionページオブジェクトからタイトル文字列を抽出する。"""
    props = page.get("properties") or {}
    for prop in props.values():
        if prop.get("type") == "title":
            titles = prop.get("title") or []
            return "".join(t.get("plain_text", "") for t in titles).strip()
    return ""


def _score_relevance(title: str, theme: str) -> int:
    """テーマキーワードとページタイトルの単純キーワードマッチ数を返す。"""
    if not title or not theme:
        return 0
    title_lower = title.lower()
    score = 0
    for kw in theme.split():
        if kw and kw.lower() in title_lower:
            score += 1
    return score


def _get_page_content(page_id: str) -> str:
    """
    Notionページのブロック内容を取得してプレーンテキストに変換する。
    最大 _MAX_BLOCK_CHARS 文字に切り詰める。エラー時は "" を返す。
    """
    url = f"{_BASE_URL}/blocks/{page_id}/children"
    try:
        resp = requests.get(url, headers=_headers(), timeout=15)
        resp.raise_for_status()
    except Exception:
        return ""

    lines = []
    for block in resp.json().get("results", []):
        btype = block.get("type", "")
        bdata = block.get(btype) or {}
        rich_text = bdata.get("rich_text") or []
        text = "".join(t.get("plain_text", "") for t in rich_text).strip()
        if text:
            lines.append(text)

    content = "\n".join(lines)
    if len(content) > _MAX_BLOCK_CHARS:
        content = content[:_MAX_BLOCK_CHARS] + "…"
    return content


def _search_via_db(theme: str, limit: int) -> list:
    """
    NOTION_KB_DATABASE_ID が設定されている場合: DBを全件取得し、
    タイトル関連度の高い順に上位 limit 件を返す。
    """
    url = f"{_BASE_URL}/databases/{NOTION_KB_DATABASE_ID}/query"
    all_pages = []
    next_cursor = None

    while len(all_pages) < _MAX_DB_FETCH:
        payload: dict = {"page_size": min(100, _MAX_DB_FETCH - len(all_pages))}
        if next_cursor:
            payload["start_cursor"] = next_cursor

        resp = requests.post(url, headers=_headers(), json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        all_pages.extend(data.get("results", []))

        if not data.get("has_more"):
            break
        next_cursor = data.get("next_cursor")

    # タイトル関連度でランキング
    scored = [(page, _score_relevance(_get_page_title(page), theme)) for page in all_pages]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:limit]]


def _search_via_workspace(theme: str, limit: int) -> list:
    """
    NOTION_KB_DATABASE_ID が未設定の場合: ワークスペース全体を /search で検索する。
    """
    url = f"{_BASE_URL}/search"
    payload = {
        "query": theme,
        "filter": {"value": "page", "property": "object"},
        "page_size": limit,
    }
    resp = requests.post(url, headers=_headers(), json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json().get("results", [])[:limit]


def fetch_relevant_pages(theme: str, limit: int = MAX_KB_PAGES) -> list:
    """
    テーマに関連するNotionページを取得し、タイトル・内容を含むdictのリストを返す。

    戻り値: [{"title": str, "page_id": str, "content": str}]
    is_configured() が False の場合は [] を返す（サイレントスキップ）。
    ネットワークエラー・APIエラーも [] を返す（メインフローを止めない）。
    """
    if not is_configured():
        return []

    try:
        if NOTION_KB_DATABASE_ID:
            raw_pages = _search_via_db(theme, limit)
        else:
            raw_pages = _search_via_workspace(theme, limit)
    except Exception as e:
        print(f"[NotionKB] ページ検索中にエラーが発生しました: {e}")
        return []

    results = []
    for page in raw_pages:
        page_id = page.get("id", "")
        title = _get_page_title(page)
        content = _get_page_content(page_id) if page_id else ""
        if title or content:
            results.append({"title": title, "page_id": page_id, "content": content})

    return results


def format_kb_context(pages: list) -> str:
    """
    取得したNotionページリストをプロンプト注入用テキストにフォーマットする。
    pages が空の場合は "" を返す。
    """
    if not pages:
        return ""

    lines = [
        "【CORE HARI ブランド知識 (Notion Knowledge Base)】",
        "※ 以下のブランドルール・知識を最優先で参照し、一般的な美容情報よりCORE HARIらしい表現・考え方を優先すること。",
        "",
    ]
    for i, page in enumerate(pages, 1):
        lines.append(f"[KB-{i}] {page['title']}")
        if page["content"]:
            lines.append(page["content"])
        lines.append("")

    return "\n".join(lines)


def log_kb_pages(pages: list, theme: str) -> None:
    """取得したNotionページをログ出力する。"""
    db_info = f" (DB: {NOTION_KB_DATABASE_ID[:8]}…)" if NOTION_KB_DATABASE_ID else " (workspace search)"
    if not pages:
        print(f"[NotionKB] テーマ「{theme[:40]}」{db_info}: 関連ページなし")
        return
    print(f"[NotionKB] テーマ「{theme[:40]}」{db_info}: {len(pages)}件のKBページを参照")
    for i, page in enumerate(pages, 1):
        pid = page["page_id"]
        pid_short = pid[:8] + "…" if len(pid) > 8 else pid
        print(f"  [{i}] {page['title']} (id: {pid_short})")
