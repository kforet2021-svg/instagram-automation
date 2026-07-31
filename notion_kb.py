"""
notion_kb.py
CORE HARI Knowledge Base RAG — Notion からブランド知識を意味検索してプロンプトに注入する。

【設計方針: 2026-07-31 v2 Semantic Search】
- OpenAI text-embedding-3-small によるコサイン類似度で意味的に近いページをランキング
- 各ページの タイトル・本文(ブロック)・タグ・カテゴリー・キーワード 全フィールドを埋め込む
- クエリ + 全ページを1回のEmbedding API呼び出しでバッチ処理（コスト最小化）
- NOTION_API_KEY が未設定の場合はサイレントスキップ（Optional機能）
- NOTION_KB_DATABASE_ID 設定時はそのDB全件取得 → セマンティックランキング
  未設定時はワークスペース全体を /search で取得 → セマンティックランキング
- requests + openai のみ使用（新規依存なし）
- Embedding API エラー時はDBの順序（先着）でフォールバック（クラッシュしない）

コスト目安: text-embedding-3-small $0.020/1M tokens
  KB 50ページ × 500 tokens/ページ = 25,000 tokens → 約 $0.0005/実行

【2026-07-31: v1(タイトルキーワードマッチ)からv2(Semantic Search)へ全面改訂】
"""

import math
import requests
from openai import OpenAI

from config import NOTION_API_KEY, NOTION_KB_DATABASE_ID, OPENAI_API_KEY

_NOTION_VERSION = "2022-06-28"
_BASE_URL = "https://api.notion.com/v1"
_EMBED_MODEL = "text-embedding-3-small"

MAX_KB_PAGES = 5            # 1回あたりの最大返却ページ数
_MAX_DB_FETCH = 100         # DB全件取得の上限（Notion APIの1リクエスト上限）
_MAX_EMBED_CHARS = 2000     # ページあたり埋め込み用最大文字数（意味検索の精度確保）
_MAX_INJECT_CHARS = 500     # ページあたりプロンプト注入用最大文字数（prompt bloat防止）


def is_configured() -> bool:
    """NOTION_API_KEY が設定されているかどうか。"""
    return bool(NOTION_API_KEY)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Notion ページ内容の取得
# ---------------------------------------------------------------------------

def _get_page_title(page: dict) -> str:
    """Notionページオブジェクトからタイトル文字列を抽出する。"""
    for prop in (page.get("properties") or {}).values():
        if prop.get("type") == "title":
            return "".join(
                t.get("plain_text", "") for t in (prop.get("title") or [])
            ).strip()
    return ""


def _extract_property_texts(page: dict) -> list:
    """
    タイトル以外の全プロパティから「プロパティ名: 値」形式のテキストを抽出する。
    対象型: select / multi_select（タグ・カテゴリー）/ rich_text（キーワード等）/ date
    セマンティック検索のクエリテキスト構築に使う。
    """
    texts = []
    for prop_name, prop_data in (page.get("properties") or {}).items():
        prop_type = prop_data.get("type", "")

        if prop_type == "title":
            continue

        if prop_type == "select":
            val = (prop_data.get("select") or {}).get("name", "")
            if val:
                texts.append(f"{prop_name}: {val}")

        elif prop_type == "multi_select":
            vals = [
                item.get("name", "")
                for item in (prop_data.get("multi_select") or [])
                if item.get("name")
            ]
            if vals:
                texts.append(f"{prop_name}: {', '.join(vals)}")

        elif prop_type == "rich_text":
            val = "".join(
                t.get("plain_text", "") for t in (prop_data.get("rich_text") or [])
            ).strip()
            if val:
                texts.append(f"{prop_name}: {val}")

        elif prop_type == "date":
            val = (prop_data.get("date") or {}).get("start", "")
            if val:
                texts.append(f"{prop_name}: {val}")

    return texts


def _get_page_content(page_id: str, max_chars: int = _MAX_EMBED_CHARS) -> str:
    """
    Notionページのブロック内容を取得してプレーンテキストに変換する。
    max_chars 文字に切り詰める。エラー時は "" を返す（クラッシュしない）。
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
    return content[:max_chars] + "…" if len(content) > max_chars else content


def _build_embed_text(title: str, prop_texts: list, body: str) -> str:
    """
    セマンティック検索用の埋め込みテキストを構築する。
    タイトル + プロパティ(タグ/カテゴリー/キーワード等) + 本文を結合。
    """
    parts = [title] + prop_texts + ([body] if body else [])
    combined = "\n".join(filter(None, parts))
    return combined[:_MAX_EMBED_CHARS]


# ---------------------------------------------------------------------------
# Notion ページ一覧の取得
# ---------------------------------------------------------------------------

def _fetch_all_pages() -> list:
    """
    DBまたはワークスペース全体からNotionページを全件取得する。
    NOTION_KB_DATABASE_ID 設定時: そのDBをページネーション取得
    未設定時: /search でワークスペース全体を取得
    """
    if NOTION_KB_DATABASE_ID:
        url = f"{_BASE_URL}/databases/{NOTION_KB_DATABASE_ID}/query"
        all_pages: list = []
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
        return all_pages
    else:
        url = f"{_BASE_URL}/search"
        payload = {
            "query": "",
            "filter": {"value": "page", "property": "object"},
            "page_size": _MAX_DB_FETCH,
        }
        resp = requests.post(url, headers=_headers(), json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json().get("results", [])


# ---------------------------------------------------------------------------
# Semantic Search (OpenAI Embedding + Cosine Similarity)
# ---------------------------------------------------------------------------

def _embed_texts(texts: list) -> list:
    """
    OpenAI text-embedding-3-small でテキストリストをバッチ埋め込みする。
    戻り値: 埋め込みベクトルのリスト（texts と同じ順序）
    """
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(model=_EMBED_MODEL, input=texts)
    # レスポンスはインデックス順に並んでいるが明示的にソートして保証する
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


def _cosine_similarity(a: list, b: list) -> float:
    """2つのベクトルのコサイン類似度を返す（範囲: -1 〜 1）。"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_relevant_pages(theme: str, limit: int = MAX_KB_PAGES) -> list:
    """
    OpenAI Embedding（text-embedding-3-small）によるセマンティック検索で、
    テーマに意味的に近いNotionページを上位 limit 件返す。

    各ページの タイトル・本文(ブロック)・タグ・カテゴリー・キーワード を埋め込み対象にする。
    クエリと全ページを1回のEmbedding API呼び出しでバッチ処理。

    is_configured() が False の場合は [] を返す（サイレントスキップ）。
    Embedding API エラー時はDBの順序で先着 limit 件を返す（フォールバック）。

    戻り値: [{"title": str, "page_id": str, "content": str, "similarity": float}]
    """
    if not is_configured():
        return []

    try:
        raw_pages = _fetch_all_pages()
    except Exception as e:
        print(f"[NotionKB] ページ取得中にエラーが発生しました: {e}")
        return []

    if not raw_pages:
        return []

    # 各ページのコンテンツを構築（ブロック取得を含む）
    page_records = []
    for page in raw_pages:
        page_id = page.get("id", "")
        title = _get_page_title(page)
        prop_texts = _extract_property_texts(page)
        body = _get_page_content(page_id, max_chars=_MAX_EMBED_CHARS)
        embed_text = _build_embed_text(title, prop_texts, body)
        # プロンプト注入用は短く切り詰める
        inject_content = body[:_MAX_INJECT_CHARS] + "…" if len(body) > _MAX_INJECT_CHARS else body
        page_records.append({
            "page_id": page_id,
            "title": title,
            "content": inject_content,
            "embed_text": embed_text,
            "similarity": 0.0,
        })

    # Semantic Search: クエリ + 全ページを1回のAPI呼び出しで埋め込む
    try:
        all_texts = [theme] + [r["embed_text"] for r in page_records]
        embeddings = _embed_texts(all_texts)
        query_emb = embeddings[0]
        page_embs = embeddings[1:]

        for record, emb in zip(page_records, page_embs):
            record["similarity"] = _cosine_similarity(query_emb, emb)

        page_records.sort(key=lambda r: r["similarity"], reverse=True)

    except Exception as e:
        print(f"[NotionKB] Embedding APIエラー — DBの順序でフォールバック: {e}")

    # embed_text はプロンプトに不要なので除去
    for r in page_records:
        r.pop("embed_text", None)

    return page_records[:limit]


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
        sim = page.get("similarity", 0.0)
        sim_label = f"  (類似度: {sim:.2f})" if sim > 0.0 else ""
        lines.append(f"[KB-{i}] {page['title']}{sim_label}")
        if page.get("content"):
            lines.append(page["content"])
        lines.append("")

    return "\n".join(lines)


def log_kb_pages(pages: list, theme: str) -> None:
    """取得したNotionページをログ出力する。"""
    db_info = f" (DB: {NOTION_KB_DATABASE_ID[:8]}…)" if NOTION_KB_DATABASE_ID else " (workspace)"
    if not pages:
        print(f"[NotionKB] テーマ「{theme[:40]}」{db_info}: 関連ページなし")
        return
    sims = ", ".join(f"{p.get('similarity', 0.0):.2f}" for p in pages)
    print(f"[NotionKB] テーマ「{theme[:40]}」{db_info}: {len(pages)}件参照 (類似度: {sims})")
    for i, page in enumerate(pages, 1):
        pid_short = page["page_id"][:8] + "…" if len(page["page_id"]) > 8 else page["page_id"]
        sim = page.get("similarity", 0.0)
        print(f"  [{i}] {page['title']}  (id: {pid_short}, similarity: {sim:.2f})")
