"""
notion_kb.py
CORE HARI Knowledge Base RAG — CORE HARI Methodology 親ページを起点に
配下のデータベース・子ページを再帰探索し、意味検索でブランド知識をプロンプトへ注入する。

【設計方針: 2026-07-31 v3 — 階層探索 + Semantic Search】

探索構造:
  NOTION_METHODOLOGY_PAGE_ID (親ページ)
  ├ Knowledge Base    (child_page または child_database)
  ├ Reasoning Engine  (child_page または child_database)
  ├ Principles        (child_page または child_database)
  └ Operations        (child_page または child_database)

処理フロー:
  1. 親ページを起点に child_page / child_database を再帰探索 (最大深度 _MAX_DEPTH)
  2. 各ページの タイトル・本文(ブロック)・タグ・カテゴリー・キーワード を収集
  3. OpenAI text-embedding-3-small でクエリ + 全ページを一括埋め込み
  4. コサイン類似度ランキングで上位 limit 件を返す
  5. セクション名（Knowledge Base / Reasoning Engine 等）もログに出力

環境変数:
  NOTION_API_KEY              : Notion Integration Token (必須)
  NOTION_METHODOLOGY_PAGE_ID  : CORE HARI Methodology 親ページのID (必須)

Notion API レート制限 (3 req/sec) に対してリトライ対応。
Embedding API エラー時は探索順で先着 limit 件をフォールバック返却。

【2026-07-31 v3: v2(単一DB)からv3(親ページ起点の再帰探索)へ全面改訂】
"""

import math
import time
import requests
from openai import OpenAI

from config import NOTION_API_KEY, NOTION_METHODOLOGY_PAGE_ID, OPENAI_API_KEY

_NOTION_VERSION = "2022-06-28"
_BASE_URL = "https://api.notion.com/v1"
_EMBED_MODEL = "text-embedding-3-small"

MAX_KB_PAGES = 5              # 意味検索で返す最大ページ数
_MAX_DEPTH = 4                # 再帰探索の最大深度（ルートページ = depth 0）
_MAX_TRAVERSE_PAGES = 200     # 探索の総ページ数上限（無限ループ防止）
_MAX_EMBED_CHARS = 2000       # 埋め込み用最大文字数/ページ
_MAX_INJECT_CHARS = 500       # プロンプト注入用最大文字数/ページ

# コンテンツとして抽出するブロック型（child_page / child_database は除く）
_CONTENT_BLOCK_TYPES = frozenset({
    "paragraph", "heading_1", "heading_2", "heading_3",
    "bulleted_list_item", "numbered_list_item", "to_do",
    "toggle", "code", "quote", "callout",
})


def is_configured() -> bool:
    """NOTION_API_KEY と NOTION_METHODOLOGY_PAGE_ID の両方が設定されているか。"""
    return bool(NOTION_API_KEY and NOTION_METHODOLOGY_PAGE_ID)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Notion API ヘルパー（429 リトライ付き）
# ---------------------------------------------------------------------------

def _notion_get(url: str, **kwargs) -> dict:
    """GET リクエスト。403/404 は分かりやすいエラー、429 はリトライ（最大3回）。"""
    for _ in range(3):
        resp = requests.get(url, headers=_headers(), timeout=20, **kwargs)
        if resp.status_code == 403:
            raise PermissionError(
                "[NotionKB] 403 アクセス拒否: Integration にこのページへのアクセス権がありません。\n"
                f"  URL: {url}\n"
                "  Notion ページを開き「接続済みのインテグレーション」にこの Integration を追加してください。\n"
                "  親ページ (NOTION_METHODOLOGY_PAGE_ID) だけでなく、配下のページ・DBにも権限が必要です。"
            )
        if resp.status_code == 404:
            raise FileNotFoundError(
                "[NotionKB] 404 ページ未検出: NOTION_METHODOLOGY_PAGE_ID のページが見つかりません。\n"
                f"  URL: {url}\n"
                "  .env / GitHub Secrets の NOTION_METHODOLOGY_PAGE_ID が正しいか確認してください。\n"
                "  Notion ページ URL の末尾32文字（ハイフンなし）がページIDです。"
            )
        if resp.status_code == 429:
            wait = max(int(resp.headers.get("Retry-After", "2")), 1)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise requests.HTTPError(f"429 rate limit after retries: {url}")


def _notion_post(url: str, payload: dict, **kwargs) -> dict:
    """POST リクエスト。403/404 は分かりやすいエラー、429 はリトライ（最大3回）。"""
    for _ in range(3):
        resp = requests.post(url, headers=_headers(), json=payload, timeout=20, **kwargs)
        if resp.status_code == 403:
            raise PermissionError(
                "[NotionKB] 403 アクセス拒否: Integration にこのデータベースへのアクセス権がありません。\n"
                f"  URL: {url}\n"
                "  Notion ページを開き「接続済みのインテグレーション」にこの Integration を追加してください。"
            )
        if resp.status_code == 404:
            raise FileNotFoundError(
                "[NotionKB] 404 DB未検出: データベースが見つかりません。\n"
                f"  URL: {url}"
            )
        if resp.status_code == 429:
            wait = max(int(resp.headers.get("Retry-After", "2")), 1)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise requests.HTTPError(f"429 rate limit after retries: {url}")


# ---------------------------------------------------------------------------
# ページブロック・プロパティの取得
# ---------------------------------------------------------------------------

def _get_blocks(page_id: str) -> list:
    """ページの全ブロックをページネーション付きで取得する。"""
    url = f"{_BASE_URL}/blocks/{page_id}/children"
    all_blocks: list = []
    next_cursor = None
    while True:
        params: dict = {"page_size": 100}
        if next_cursor:
            params["start_cursor"] = next_cursor
        data = _notion_get(url, params=params)
        all_blocks.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        next_cursor = data.get("next_cursor")
    return all_blocks


def _extract_content_from_blocks(blocks: list, max_chars: int = _MAX_EMBED_CHARS) -> str:
    """
    ブロックリストからコンテンツテキストを抽出する。
    _CONTENT_BLOCK_TYPES に含まれるブロック型のみを対象にする。
    """
    lines = []
    for block in blocks:
        btype = block.get("type", "")
        if btype not in _CONTENT_BLOCK_TYPES:
            continue
        bdata = block.get(btype) or {}
        text = "".join(
            t.get("plain_text", "") for t in (bdata.get("rich_text") or [])
        ).strip()
        if text:
            lines.append(text)
    content = "\n".join(lines)
    return content[:max_chars] + "…" if len(content) > max_chars else content


def _get_page_title(page: dict) -> str:
    """Notionページオブジェクトの title プロパティからタイトルを抽出する。"""
    for prop in (page.get("properties") or {}).values():
        if prop.get("type") == "title":
            return "".join(
                t.get("plain_text", "") for t in (prop.get("title") or [])
            ).strip()
    return ""


def _extract_property_texts(page: dict) -> list:
    """
    タイトル以外の全プロパティから「プロパティ名: 値」テキストを抽出する。
    対象: select（カテゴリー）/ multi_select（タグ）/ rich_text（キーワード等）/ date
    プロパティ名に依存せず全プロパティを抽出することで、Notionのカラム名を問わず対応。
    """
    texts = []
    for prop_name, prop_data in (page.get("properties") or {}).items():
        ptype = prop_data.get("type", "")
        if ptype == "title":
            continue
        if ptype == "select":
            val = (prop_data.get("select") or {}).get("name", "")
            if val:
                texts.append(f"{prop_name}: {val}")
        elif ptype == "multi_select":
            vals = [
                item.get("name", "")
                for item in (prop_data.get("multi_select") or [])
                if item.get("name")
            ]
            if vals:
                texts.append(f"{prop_name}: {', '.join(vals)}")
        elif ptype == "rich_text":
            val = "".join(
                t.get("plain_text", "") for t in (prop_data.get("rich_text") or [])
            ).strip()
            if val:
                texts.append(f"{prop_name}: {val}")
        elif ptype == "date":
            val = (prop_data.get("date") or {}).get("start", "")
            if val:
                texts.append(f"{prop_name}: {val}")
    return texts


# ---------------------------------------------------------------------------
# レコード生成ヘルパー
# ---------------------------------------------------------------------------

def _build_embed_text(title: str, prop_texts: list, body: str) -> str:
    """セマンティック検索用の埋め込みテキスト（タイトル+プロパティ+本文）を構築する。"""
    parts = [title] + prop_texts + ([body] if body else [])
    combined = "\n".join(filter(None, parts))
    return combined[:_MAX_EMBED_CHARS]


def _make_record(
    page_id: str, title: str, section: str, prop_texts: list, body: str
) -> dict:
    """ページレコードを生成する。content はプロンプト注入用に切り詰める。"""
    inject_content = body[:_MAX_INJECT_CHARS] + "…" if len(body) > _MAX_INJECT_CHARS else body
    return {
        "page_id": page_id,
        "title": title,
        "section": section,
        "content": inject_content,
        "embed_text": _build_embed_text(title, prop_texts, body),
        "similarity": 0.0,
    }


# ---------------------------------------------------------------------------
# 再帰探索
# ---------------------------------------------------------------------------

def _collect_database_pages(db_id: str, section: str, visited: set) -> list:
    """
    データベースの全ページを収集する。
    各ページについて:
      - プロパティ（タグ / カテゴリー / キーワード等）
      - 本文（ブロック）
    を取得してページレコードのリストを返す。
    """
    url = f"{_BASE_URL}/databases/{db_id}/query"
    raw_pages: list = []
    next_cursor = None
    while len(raw_pages) < _MAX_TRAVERSE_PAGES:
        payload: dict = {"page_size": min(100, _MAX_TRAVERSE_PAGES - len(raw_pages))}
        if next_cursor:
            payload["start_cursor"] = next_cursor
        data = _notion_post(url, payload)
        raw_pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        next_cursor = data.get("next_cursor")

    records = []
    for page in raw_pages:
        page_id = page.get("id", "")
        if not page_id or page_id in visited:
            continue
        visited.add(page_id)

        title = _get_page_title(page)
        prop_texts = _extract_property_texts(page)

        try:
            blocks = _get_blocks(page_id)
            body = _extract_content_from_blocks(blocks, _MAX_EMBED_CHARS)
        except Exception as e:
            label = title or page_id[:8]
            print(f"[NotionKB] コンテンツ取得エラー「{label}」: {e}")
            body = ""

        records.append(_make_record(page_id, title, section, prop_texts, body))

    return records


def _traverse_page(
    page_id: str,
    title: str,
    section: str,
    depth: int,
    visited: set,
    counter: dict,
) -> list:
    """
    ページを起点に再帰的に探索し、全子孫ページのレコードリストを返す。

    depth=0 : CORE HARI Methodology ルート（このページ自体はレコード化しない）
    depth=1 : セクション直下（Knowledge Base / Reasoning Engine 等）
              → そのタイトルが以降の子孫の section 名になる
    depth=2+: 実コンテンツページ → テキストがあればレコード化する

    child_page       → _traverse_page() を再帰呼び出し
    child_database   → _collect_database_pages() で全ページを収集
    counter          : {"pages": N, "dbs": M} — 呼び出し元で集計用
    """
    if page_id in visited or depth > _MAX_DEPTH:
        return []
    visited.add(page_id)
    counter["pages"] = counter.get("pages", 0) + 1

    try:
        blocks = _get_blocks(page_id)
    except Exception as e:
        print(f"[NotionKB] ブロック取得エラー「{title or page_id[:8]}」: {e}")
        return []

    content_lines: list = []
    descendant_records: list = []

    for block in blocks:
        btype = block.get("type", "")

        if btype in _CONTENT_BLOCK_TYPES:
            bdata = block.get(btype) or {}
            text = "".join(
                t.get("plain_text", "") for t in (bdata.get("rich_text") or [])
            ).strip()
            if text:
                content_lines.append(text)

        elif btype == "child_page":
            child_id = block.get("id", "")
            child_title = (block.get("child_page") or {}).get("title", "")
            # depth=0 直下の子タイトルがセクション名になる
            child_section = child_title if depth == 0 else section
            sub = _traverse_page(child_id, child_title, child_section, depth + 1, visited, counter)
            descendant_records.extend(sub)

        elif btype == "child_database":
            db_id = block.get("id", "")
            db_title = (block.get("child_database") or {}).get("title", "")
            db_section = db_title if depth == 0 else section
            counter["dbs"] = counter.get("dbs", 0) + 1
            try:
                db_records = _collect_database_pages(db_id, db_section, visited)
                descendant_records.extend(db_records)
            except Exception as e:
                print(f"[NotionKB] DB収集エラー「{db_title or db_id[:8]}」: {e}")

    # このページ自体のコンテンツをレコード化（depth=0 のルートは除外）
    this_records: list = []
    if depth > 0 and content_lines:
        body = "\n".join(content_lines)
        if len(body) > _MAX_EMBED_CHARS:
            body = body[:_MAX_EMBED_CHARS]
        this_records.append(_make_record(page_id, title, section, [], body))

    return this_records + descendant_records


def _fetch_all_pages() -> tuple:
    """
    NOTION_METHODOLOGY_PAGE_ID を起点に全子孫ページ・DBページを再帰収集する。
    戻り値: (records: list, stats: dict{"pages_traversed", "dbs_found", "docs_retrieved"})
    """
    visited: set = set()
    counter: dict = {"pages": 0, "dbs": 0}
    records = _traverse_page(
        NOTION_METHODOLOGY_PAGE_ID,
        title="CORE HARI Methodology",
        section="",
        depth=0,
        visited=visited,
        counter=counter,
    )
    stats = {
        "pages_traversed": counter.get("pages", 0),
        "dbs_found": counter.get("dbs", 0),
        "docs_retrieved": len(records),
    }
    return records, stats


# ---------------------------------------------------------------------------
# Semantic Search（OpenAI Embedding + コサイン類似度）
# ---------------------------------------------------------------------------

def _embed_texts(texts: list) -> list:
    """OpenAI text-embedding-3-small で一括埋め込みする。"""
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(model=_EMBED_MODEL, input=texts)
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


def _cosine_similarity(a: list, b: list) -> float:
    """コサイン類似度を計算する（-1 〜 1）。"""
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
    CORE HARI Methodology 配下のページ群からテーマに意味的に近いページを返す。

    1. NOTION_METHODOLOGY_PAGE_ID を起点に child_page / child_database を再帰探索
    2. タイトル・本文・タグ・カテゴリー・キーワードを埋め込みテキストとして結合
    3. OpenAI Embedding でクエリ + 全ページを一括ベクトル化
    4. コサイン類似度ランキングで上位 limit 件を返す

    is_configured() が False の場合は [] を返す（サイレントスキップ）。
    Embedding API エラー時は探索順で先着 limit 件をフォールバック返却。

    戻り値: [{"title", "page_id", "section", "content", "similarity"}]
    """
    if not is_configured():
        return []

    root_short = (
        NOTION_METHODOLOGY_PAGE_ID[:8] + "…"
        if len(NOTION_METHODOLOGY_PAGE_ID) > 8
        else NOTION_METHODOLOGY_PAGE_ID
    )
    print(f"[NotionKB] ルートページID: {root_short}")
    print(f"[NotionKB] テーマ「{theme[:60]}」でKB探索中...")

    try:
        page_records, stats = _fetch_all_pages()
    except Exception as e:
        print(f"[NotionKB] ⚠ 再帰探索エラー: {e}")
        return []

    print(
        f"[NotionKB] 探索結果: ページ{stats['pages_traversed']}件 / "
        f"DB{stats['dbs_found']}件 / 文書{stats['docs_retrieved']}件取得"
    )

    if not page_records:
        print("[NotionKB] ⚠ 警告: Notion KBから文書が取得できませんでした")
        print("[NotionKB]   → Integration がルートページ・配下ページ・DBにアクセス可能か確認してください")
        print("[NotionKB]   → CORE HARIブランドルールなしで投稿を生成します（一般的な美容投稿になる可能性があります）")
        return []

    print(f"[NotionKB] {len(page_records)}件 → セマンティック検索中...")

    try:
        all_texts = [theme] + [r["embed_text"] for r in page_records]
        embeddings = _embed_texts(all_texts)
        query_emb = embeddings[0]
        page_embs = embeddings[1:]

        for record, emb in zip(page_records, page_embs):
            record["similarity"] = _cosine_similarity(query_emb, emb)

        page_records.sort(key=lambda r: r["similarity"], reverse=True)

    except Exception as e:
        print(f"[NotionKB] Embedding APIエラー — 探索順でフォールバック: {e}")

    for r in page_records:
        r.pop("embed_text", None)

    return page_records[:limit]


def format_kb_context(pages: list) -> str:
    """取得したNotionページをプロンプト注入用テキストにフォーマットする。"""
    if not pages:
        return ""

    lines = [
        "【最優先ルール — CORE HARI ブランド知識 (Notion Knowledge Base)】",
        "以下はNotionから取得したCORE HARIのブランドルール・専門知識です。",
        "このルールはInstagramの投稿分析結果（フック・構成・CTAの「型」）より必ず優先してください。",
        "一般的な美容表現は使わず、CORE HARIの独自視点・専門用語・考え方を必ず使ってください。",
        "",
    ]
    for i, page in enumerate(pages, 1):
        sim = page.get("similarity", 0.0)
        section = page.get("section", "")
        section_label = f"[{section}] " if section else ""
        sim_label = f"  (類似度: {sim:.2f})" if sim > 0.0 else ""
        lines.append(f"[KB-{i}] {section_label}{page['title']}{sim_label}")
        if page.get("content"):
            lines.append(page["content"])
        lines.append("")

    return "\n".join(lines)


def log_kb_pages(pages: list, theme: str) -> None:
    """取得したNotionページをセクション・類似度付きでログ出力する。"""
    root_label = (
        f" (root: {NOTION_METHODOLOGY_PAGE_ID[:8]}…)"
        if NOTION_METHODOLOGY_PAGE_ID else ""
    )
    if not pages:
        print(f"[NotionKB] テーマ「{theme[:40]}」{root_label}: 関連ページなし")
        return
    sims = ", ".join(f"{p.get('similarity', 0.0):.2f}" for p in pages)
    print(
        f"[NotionKB] テーマ「{theme[:40]}」{root_label}: "
        f"{len(pages)}件参照 (類似度: {sims})"
    )
    for i, page in enumerate(pages, 1):
        pid_short = page["page_id"][:8] + "…" if len(page["page_id"]) > 8 else page["page_id"]
        sim = page.get("similarity", 0.0)
        section = page.get("section", "")
        section_label = f"[{section}] " if section else ""
        print(
            f"  [{i}] {section_label}{page['title']}"
            f"  (id: {pid_short}, similarity: {sim:.2f})"
        )
