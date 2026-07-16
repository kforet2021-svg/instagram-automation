"""
phase2/post_generator.py

CORE HARI FACE — OpenAI Responses API 呼び出し + 保存

【2026-07-16(6回目): 「毎日10分以内に投稿できるシステム」へ刷新。
  - 判定を2種類のみに簡素化: 投稿OK / 要修正
  - 要修正 = APIエラー / 台本・キャプション・サムネイルが生成できない場合のみ
  - 文字数違反・各種FAIL/WARNING は投稿を止めない
  - スコア・品質星・自己採点・自動再生成を全廃
  - Markdown先頭を「# 今日使うもの」に変更
    順序: サムネイル→冒頭3秒→30秒台本→キャプション→CTA → 参考（Threads/X/カルーセル/ハッシュタグ）
  - 生成後にInstagram編集長レビューを1回送信して表示
  - キャプションは「投稿OK」のみクリップボードへコピー
】
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
from typing import Optional

# ── 禁止表現リスト ────────────────────────────────────────────────────────────

_FORBIDDEN_PHRASES = [
    "主要因です", "原因です", "のせいです",
    "を予防できます", "が解消します", "が改善します", "治ります",
    "これだけで変わります", "効果が長続きします",
    "夏だから筋肉が弱", "汗でむくみが悪化", "湿度でむくみが増",
]

# ── 投稿目的別 CTA 判定キーワード ─────────────────────────────────────────────

_CTA_PURPOSE_PATTERNS: dict[str, str] = {
    "保存": r"保存|見返",
    "共感": r"コメント|教えてください|シェア|同じ.*方|どちら",
    "信頼": r"コメント|質問|相談|気になること|迷ったら",
    "行動": r"やってみてください|試してみてください|今日から|今すぐ|実践",
    "予約": r"施術|プロの|まず.*自分",
}


# ── セクション抽出ヘルパー ────────────────────────────────────────────────────

def _extract_section(content: str, marker: str) -> str:
    """
    marker（例: "①"）から始まるセクションを次のセクションマーカー前まで返す。
    """
    start = content.find(marker)
    if start == -1:
        return ""
    all_markers = list("①②③④⑤⑥⑦⑧⑨⑩⑪⑫") + ["【リール優先サマリー】", "【編集メモ】"]
    next_pos = len(content)
    for m in all_markers:
        if m == marker:
            continue
        pos = content.find(m, start + 1)
        if 0 < pos < next_pos:
            next_pos = pos
    return content[start:next_pos]


def _extract_reel_field(reel_summary: str, keyword: str) -> str:
    """
    リール優先サマリーから **keyword...** ヘッダーの後ろのコンテンツを返す。
    次の **...:** ヘッダーまたは末尾まで取得する。
    """
    idx = reel_summary.find(f"**{keyword}")
    if idx == -1:
        return ""
    eol = reel_summary.find("\n", idx)
    if eol == -1:
        return ""
    next_header = reel_summary.find("\n**", eol)
    end = next_header if next_header != -1 else len(reel_summary)
    return reel_summary[eol:end].strip()


def _extract_editor_memo(content: str) -> dict:
    """
    【編集メモ】セクションからフィールドを抽出する。

    Returns dict with keys:
      theme, post_purpose, hook,
      ref_post_1/2/3, ref_type_1/2/3, ref_reason_1/2/3,
      corehari_changes, editor_comment
    """
    memo_text = _extract_section(content, "【編集メモ】")
    if not memo_text:
        return {}

    def _field(label: str) -> str:
        """**label:** の後ろのテキストを次の **...:** まで取得する。"""
        idx = memo_text.find(f"**{label}:")
        if idx == -1:
            idx = memo_text.find(f"**{label}**")
        if idx == -1:
            return ""
        eol = memo_text.find("\n", idx)
        if eol == -1:
            return ""
        # inline value（同一行に値がある場合）
        inline = memo_text[idx:eol].split(":", 1)
        inline_val = inline[1].strip().strip("*") if len(inline) > 1 else ""
        # multiline: 次の ** ヘッダーまで
        nxt = memo_text.find("\n**", eol)
        block = memo_text[eol: nxt if nxt != -1 else len(memo_text)].strip()
        return block if block else inline_val

    def _ref_block(n: int) -> tuple[str, str, str]:
        """参考Nブロックから URL / 参考にした部分 / 採用理由 を返す。"""
        tag = f"参考{n}:"
        idx = memo_text.find(tag)
        if idx == -1:
            return "", "", ""
        nxt_ref = len(memo_text)
        for nn in range(1, 4):
            if nn == n:
                continue
            p = memo_text.find(f"参考{nn}:", idx + 1)
            if 0 < p < nxt_ref:
                nxt_ref = p
        # also stop at 変更した点
        p2 = memo_text.find("**CORE HARI", idx + 1)
        if 0 < p2 < nxt_ref:
            nxt_ref = p2
        block = memo_text[idx:nxt_ref]

        def _line(label: str) -> str:
            m = re.search(rf"-\s*{re.escape(label)}[:：]\s*(.*)", block)
            return m.group(1).strip() if m else ""

        url    = _line("URL")
        rtype  = _line("参考にした部分")
        reason = _line("採用理由")
        if url in ("なし", "（なし）", ""):
            return "", rtype, reason
        return url, rtype, reason

    url1, type1, reason1 = _ref_block(1)
    url2, type2, reason2 = _ref_block(2)
    url3, type3, reason3 = _ref_block(3)

    # CORE HARI変更点
    changes_idx = memo_text.find("**CORE HARIへ変更した点")
    comment_idx = memo_text.find("**AI編集長コメント")
    if changes_idx != -1:
        changes_end = comment_idx if comment_idx > changes_idx else len(memo_text)
        changes_block = memo_text[changes_idx:changes_end]
        changes_block = re.sub(r"\*\*CORE HARIへ変更した点[^\n]*\n", "", changes_block)
        changes = changes_block.strip()
    else:
        changes = ""

    # AI編集長コメント
    if comment_idx != -1:
        comment_line = memo_text[comment_idx:]
        comment_line = re.sub(r"\*\*AI編集長コメント[^\n]*\n", "", comment_line)
        editor_comment = comment_line.strip()
    else:
        editor_comment = ""

    return {
        "theme":          _field("今日のテーマ"),
        "post_purpose":   _field("投稿目的"),
        "hook":           _field("選択Hook"),
        "ref_post_1":     url1,
        "ref_type_1":     type1,
        "ref_reason_1":   reason1,
        "ref_post_2":     url2,
        "ref_type_2":     type2,
        "ref_reason_2":   reason2,
        "ref_post_3":     url3,
        "ref_type_3":     type3,
        "ref_reason_3":   reason3,
        "corehari_changes": changes,
        "editor_comment":   editor_comment,
    }


def _build_editor_memo_md(content: str, handoff: dict) -> str:
    """
    Markdownに挿入する「編集メモ」ブロックを構築する。
    AIが【編集メモ】を出力していれば使い、なければhandoffから最低限の情報で組み立てる。
    """
    raw = _extract_section(content, "【編集メモ】")
    if raw and len(raw) > 100:
        # AIが出力した内容をそのまま使う（先頭の見出し行を含む）
        return raw.strip()

    # フォールバック: handoffから構築
    hook      = handoff.get("hook", "")
    post_type = handoff.get("post_type", "")
    topic     = handoff.get("topic", "")
    lines = [
        "【編集メモ】",
        "",
        f"**今日のテーマ:** {topic}",
        f"**投稿目的:** {post_type}",
        f"**選択Hook:** {hook}",
        "",
        "**参考投稿:** （AI出力なし）",
        "**CORE HARIへ変更した点:** （AI出力なし）",
        "**AI編集長コメント:** （AI出力なし）",
    ]
    return "\n".join(lines)


def _extract_caption_plain(content: str) -> str:
    """② キャプションセクションから本文のみを返す（Markdown・文字数記載を除去）。"""
    s2 = _extract_section(content, "②")
    # セクションヘッダー行を除去
    s2 = re.sub(r"^.*②[^\n]*\n", "", s2, flags=re.MULTILINE)
    # 引用符（「」）があれば中身だけ取り出す
    quoted = re.findall(r"「([\s\S]+?)」", s2)
    if quoted:
        return quoted[0].strip()
    # 文字数記載を除去して返す
    s2 = re.sub(r"（\d+文字）", "", s2)
    return s2.strip()


def _extract_reel_30sec_plain(content: str) -> str:
    """リール優先サマリーの 30秒リール完成版 フィールドを返す。"""
    reel_summary = _extract_section(content, "【リール優先サマリー】")
    text = _extract_reel_field(reel_summary, "30秒リール完成版")
    return text if text else _extract_section(content, "⑥").strip()


def _extract_thumbnail_plain(content: str) -> str:
    """リール優先サマリーの おすすめサムネイル詳細 フィールドを返す。"""
    reel_summary = _extract_section(content, "【リール優先サマリー】")
    return _extract_reel_field(reel_summary, "おすすめサムネイル詳細")


def _extract_60sec_reel_plain(content: str) -> str:
    """⑦ 60秒リール台本を抽出（セクションヘッダー・文字数注記を除去）。"""
    s7 = _extract_section(content, "⑦")
    s7 = re.sub(r"^.*⑦[^\n]*\n", "", s7, flags=re.MULTILINE)
    s7 = re.sub(r"（台本全文\d+文字）", "", s7)
    return s7.strip()


def _extract_hashtags_flat(content: str) -> str:
    """⑩ のハッシュタグを重複排除・半角スペース区切りで返す（コピペ用）。
    ### のような Markdown 記号は除外する。
    """
    s10 = _extract_section(content, "⑩")
    tags = re.findall(r"#\S+", s10)
    # 有効なハッシュタグ: # の次が # 以外の文字であること
    valid = [t for t in tags if re.match(r"^#[^#]", t)]
    return " ".join(dict.fromkeys(valid))


def _extract_cta_all(content: str) -> str:
    """③ CTA 3案全文を返す。"""
    s3 = _extract_section(content, "③")
    s3 = re.sub(r"^.*③[^\n]*\n", "", s3, flags=re.MULTILINE)
    return s3.strip()


def _extract_hook_answer(content: str) -> str:
    """カルーセルのスライド2（Hook回答）の本文を返す。"""
    s1 = _extract_section(content, "①")
    m = re.search(r"スライド2【[\s\S]*?(?=スライド3【|$)", s1)
    if not m:
        return ""
    text = re.sub(r"スライド2【[^】]*】[：:]?", "", m.group(0))
    return text.strip()


def _extract_thumbnail_fields(content: str) -> dict:
    """⑫ の案1 テキスト・補足テキスト・クリックされる理由を返す。"""
    s12 = _extract_section(content, "⑫")
    m = re.search(r"\*\*案1[^*]*\*\*[:\s]*([\s\S]*?)(?=\*\*案2|\Z)", s12)
    if not m:
        return {"main": "", "sub": "", "reason": ""}
    block = m.group(1)

    def _field(label: str) -> str:
        m2 = re.search(rf"[-・]?\s*{label}[:：]\s*(.+)", block)
        return m2.group(1).strip() if m2 else ""

    return {
        "main":   _field("テキスト"),
        "sub":    _field("補足テキスト"),
        "reason": _field("クリックされる理由"),
    }


def _build_reel_script_entry(
    content: str,
    handoff: dict,
    status: str,
    ts: str,
    post_path: str,
) -> dict:
    """
    reel_scripts シートへ保存する1行分のデータを構築する。
    status: "投稿OK" | "要修正"
    """
    reel_summary  = _extract_section(content, "【リール優先サマリー】")
    thumb         = _extract_thumbnail_fields(content)
    expert_angles = handoff.get("expert_angles", [])
    memo          = _extract_editor_memo(content)

    return {
        "generated_at":          datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "generation_id":         ts,
        "status":                status,
        "quality_score":         "",
        "post_format":           _extract_reel_field(reel_summary, "今回おすすめの投稿形式"),
        "post_purpose":          handoff.get("post_type", ""),
        "topic":                 handoff.get("topic", ""),
        "hook":                  handoff.get("hook", ""),
        "hook_answer":           _extract_hook_answer(content),
        "reality":               handoff.get("reality", ""),
        "expert_angle":          "\n".join(expert_angles),
        "thumbnail_main":        thumb["main"],
        "thumbnail_sub":         thumb["sub"],
        "thumbnail_reason":      thumb["reason"],
        "thumbnail_composition": _extract_reel_field(reel_summary, "おすすめサムネイル詳細"),
        "opening_3sec_text":     _extract_reel_field(reel_summary, "冒頭3秒テロップ"),
        "reel_30sec_script":     _extract_reel_field(reel_summary, "30秒リール完成版"),
        "reel_60sec_script":     _extract_60sec_reel_plain(content),
        "shooting_composition":  _extract_reel_field(reel_summary, "撮影構図"),
        "shooting_checklist":    _extract_reel_field(reel_summary, "撮影チェックリスト"),
        "caption":               _extract_caption_plain(content),
        "cta":                   _extract_cta_all(content),
        "hashtags":              _extract_hashtags_flat(content),
        "validation_pass":       "",
        "validation_warning":    "",
        "validation_fail":       "",
        "output_file":           os.path.basename(post_path) if post_path else "",
        "reference_post_1":      memo.get("ref_post_1", ""),
        "reference_type_1":      memo.get("ref_type_1", ""),
        "reference_reason_1":    memo.get("ref_reason_1", ""),
        "reference_post_2":      memo.get("ref_post_2", ""),
        "reference_type_2":      memo.get("ref_type_2", ""),
        "reference_reason_2":    memo.get("ref_reason_2", ""),
        "reference_post_3":      memo.get("ref_post_3", ""),
        "reference_type_3":      memo.get("ref_type_3", ""),
        "reference_reason_3":    memo.get("ref_reason_3", ""),
        "corehari_changes":      memo.get("corehari_changes", ""),
        "editor_comment":        memo.get("editor_comment", ""),
        "posted":                "未投稿",
        "posted_at":             "",
        "instagram_url":         "",
        "views":                 "",
        "likes":                 "",
        "comments":              "",
        "saves":                 "",
        "shares":                "",
        "follows":               "",
        "notes":                 "",
    }


def _build_today_section(content: str, handoff: dict, ts: str) -> str:
    """
    Markdownの先頭に置くセクションを構築する。

    構成:
      【編集メモ】（AIが生成した参考投稿・変更点・コメント）
      # 今日使うもの: サムネイル→冒頭3秒→30秒台本→キャプション→CTA
      参考: Threads / X / カルーセル / ハッシュタグ
    """
    hook      = handoff.get("hook", "")
    post_type = handoff.get("post_type", "")

    reel_summary = _extract_section(content, "【リール優先サマリー】")

    def field(keyword: str) -> str:
        v = _extract_reel_field(reel_summary, keyword)
        return v if v else "（AIが出力しませんでした）"

    s3 = _extract_section(content, "③")
    cta_text = re.sub(r"^.*③[^\n]*\n", "", s3, flags=re.MULTILINE).strip()

    # 参考セクション: Threads/X/カルーセル/ハッシュタグ
    threads_text  = re.sub(r"^.*④[^\n]*\n", "", _extract_section(content, "④"), flags=re.MULTILINE).strip()
    x_text        = re.sub(r"^.*⑤[^\n]*\n", "", _extract_section(content, "⑤"), flags=re.MULTILINE).strip()
    carousel_text = re.sub(r"^.*①[^\n]*\n", "", _extract_section(content, "①"), flags=re.MULTILINE).strip()
    hashtag_text  = re.sub(r"^.*⑩[^\n]*\n", "", _extract_section(content, "⑩"), flags=re.MULTILINE).strip()

    # 編集メモ
    editor_memo_md = _build_editor_memo_md(content, handoff)

    lines = [
        editor_memo_md,
        "",
        "---",
        "",
        "# 今日使うもの",
        "",
        f"> **Hook**: {hook}",
        f"> **投稿目的**: {post_type}  |  生成日時: {ts}",
        "",
        "---",
        "",
        "## ① サムネイル",
        "",
        field("おすすめサムネイル詳細"),
        "",
        "## ② 冒頭3秒テロップ",
        "",
        field("冒頭3秒テロップ"),
        "",
        "## ③ 30秒リール台本",
        "",
        field("30秒リール完成版"),
        "",
        "## ④ キャプション",
        "",
        field("投稿キャプション"),
        "",
        "## ⑤ CTA",
        "",
        cta_text,
        "",
        "---",
        "",
        "# 参考（Threads / X / カルーセル / ハッシュタグ）",
        "",
        "## Threads",
        "",
        threads_text,
        "",
        "## X",
        "",
        x_text,
        "",
        "## カルーセル",
        "",
        carousel_text,
        "",
        "## ハッシュタグ",
        "",
        hashtag_text,
        "",
        "---",
        "",
        "# 全出力（AI生成原文）",
        "",
    ]
    return "\n".join(lines)


def _strip_md(text: str) -> str:
    """
    本文文字数カウント専用。以下を除去してから空白をゼロに畳む。
    - Markdown見出し行（# ## ### ####）
    - セクション番号で始まる行（例: ⑥ 30秒リール台本）
    - 時間表記（0〜5秒: など）
    - Markdown記号（* _ ` ~）
    - 括弧内の文字数注記（（XX文字）など）
    ※ #ハッシュタグ は呼び出し元で先に除去すること
    """
    text = re.sub(r"^#{1,4}\s[^\n]*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫【][^\n]*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\d+〜\d+秒[:：]?\s*", "", text)
    text = re.sub(r"（\d+[文字秒][^）]*）", "", text)
    text = re.sub(r"[*_`~]", "", text)
    text = re.sub(r"\s+", "", text)
    return text


def _count_body(text: str) -> int:
    return len(_strip_md(text))


# ── 検証ロジック（簡易版） ───────────────────────────────────────────────────

def validate_output(content: str) -> dict:
    """
    生成テキストが最低限投稿できる状態かを確認する。

    要修正になる条件:
      - 30秒リール台本が生成されていない
      - キャプションが生成されていない
      - サムネイルが生成されていない
      - カルーセル本文が生成されていない

    文字数・形式の違反は投稿を止めない。

    Returns:
        {"status": "投稿OK" | "要修正", "failed_items": [str]}
    """
    failed = []

    # 30秒リール台本
    reel_summary = _extract_section(content, "【リール優先サマリー】")
    reel30 = _extract_reel_field(reel_summary, "30秒リール完成版")
    if len(reel30.strip()) < 20:
        failed.append("30秒リール台本が生成されていません")

    # キャプション
    caption = _extract_caption_plain(content)
    if len(caption.strip()) < 20:
        failed.append("キャプションが生成されていません")

    # サムネイル
    s12_sec = _extract_section(content, "⑫")
    has_thumb = bool(re.search(r"案\d+", s12_sec)) or len(reel_summary) > 50
    if not has_thumb:
        failed.append("サムネイルが生成されていません")

    # カルーセル本文
    s1 = _extract_section(content, "①")
    if len(s1.strip()) < 50:
        failed.append("投稿本文（カルーセル）が生成されていません")

    status = "投稿OK" if not failed else "要修正"
    return {"status": status, "failed_items": failed}


# ── 削除済み: _adjust_score / _quality_stars / _check_expert_angle_api ────────
# これらのスコア・品質星・Expert Angle API判定は廃止（2026-07-16）

# ── OpenAI Responses API 呼び出し ─────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "あなたはCORE HARI FACE（札幌の顔専門エステサロン）の"
    "Instagram投稿専門のコンテンツライターです。"
    "オーナー・森このみの一人称で、やさしく専門的なトーンで書いてください。"
    "指定された全出力を省略せず番号順に出力してください。"
)


def _call_api(prompt: str, model: str) -> tuple[str, int, int]:
    """
    Responses APIを呼び出し (content, input_tokens, output_tokens) を返す。
    """
    from openai import OpenAI, AuthenticationError, RateLimitError
    from config import OPENAI_API_KEY

    if not OPENAI_API_KEY:
        raise EnvironmentError("OPENAI_API_KEY が .env に設定されていません。")

    client = OpenAI(api_key=OPENAI_API_KEY)

    try:
        response = client.responses.create(
            model=model,
            instructions=_SYSTEM_PROMPT,
            input=prompt,
        )
    except AuthenticationError as e:
        raise RuntimeError(f"OpenAI 認証エラー: {e}") from e
    except RateLimitError as e:
        raise RuntimeError(f"OpenAI 利用上限エラー: {e}") from e
    except Exception as e:
        if "timeout" in str(e).lower():
            raise RuntimeError(f"OpenAI タイムアウト: {e}") from e
        raise

    content = response.output_text or ""
    usage   = response.usage
    return content, (usage.input_tokens if usage else 0), (usage.output_tokens if usage else 0)


# ── ファイル保存 ──────────────────────────────────────────────────────────────

def _save_outputs(
    content: str,
    handoff: dict,
    status: str,
    ts: str,
    base_dir: str,
) -> dict[str, str]:
    """
    タイムスタンプ付き2ファイルを保存してパスを返す。
    latest_instagram_post.md の書き込みは _update_latest() で行う。
    """
    out_dir = os.path.join(base_dir, "outputs")
    inp_dir = os.path.join(base_dir, "outputs", "inputs")
    for d in (out_dir, inp_dir):
        os.makedirs(d, exist_ok=True)

    # 1. 投稿全文（今日使うもの → 参考 → 全出力 構造）
    today_section = _build_today_section(content, handoff, ts)
    post_path = os.path.join(out_dir, f"instagram_post_{ts}.md")
    with open(post_path, "w", encoding="utf-8") as f:
        f.write(today_section)
        f.write(content)

    # 2. 入力情報
    inp_path = os.path.join(inp_dir, f"instagram_input_{ts}.md")
    with open(inp_path, "w", encoding="utf-8") as f:
        f.write(f"# CORE HARI FACE — 入力情報\n\n生成日時: {ts}\nステータス: {status}\n\n")
        for k, v in handoff.items():
            if isinstance(v, list):
                v = "\n".join(f"  - {x}" for x in v)
            f.write(f"**{k}**:\n{v}\n\n")

    return {"post": post_path, "input": inp_path}


def _save_split_outputs(content: str, ts: str, base_dir: str) -> dict[str, str]:
    """
    キャプション・リール台本・サムネイルを個別ファイルへ保存する。
    """
    out_dir = os.path.join(base_dir, "outputs")
    os.makedirs(out_dir, exist_ok=True)

    caption   = _extract_caption_plain(content)
    reel30    = _extract_reel_30sec_plain(content)
    thumbnail = _extract_thumbnail_plain(content)

    saved: dict[str, str] = {}
    for fname, text in [
        ("latest_caption.txt",    caption),
        ("latest_reel_30sec.txt", reel30),
        ("latest_thumbnail.txt",  thumbnail),
    ]:
        path = os.path.join(out_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        saved[fname] = path

    return saved


def _update_latest(post_path: str, base_dir: str) -> str:
    """
    post_path の内容を latest_instagram_post.md へ上書きコピーし、パスを返す。
    """
    out_dir     = os.path.join(base_dir, "outputs")
    latest_path = os.path.join(out_dir, "latest_instagram_post.md")
    with open(post_path, "r", encoding="utf-8") as src:
        data = src.read()
    with open(latest_path, "w", encoding="utf-8") as dst:
        dst.write(data)
    return latest_path


def _verify_latest_files(base_dir: str) -> list[str]:
    """
    必須4ファイルが存在するか確認する。存在しないファイル名のリストを返す。
    """
    out_dir = os.path.join(base_dir, "outputs")
    required = [
        os.path.join(out_dir, "latest_instagram_post.md"),
        os.path.join(out_dir, "latest_caption.txt"),
        os.path.join(out_dir, "latest_reel_30sec.txt"),
        os.path.join(out_dir, "latest_thumbnail.txt"),
    ]
    return [os.path.basename(p) for p in required if not os.path.exists(p)]


# ── OS連携ユーティリティ ──────────────────────────────────────────────────────

def _open_markdown(path: str) -> bool:
    """macOS で Markdown ファイルを開く。失敗してもFalseを返すだけ。"""
    try:
        subprocess.run(["open", path], check=True, timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        try:
            subprocess.run(["open", "-a", "TextEdit", path], check=True, timeout=5,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False


def _play_sound(success: bool) -> None:
    """afplay で完了音を再生（バックグラウンド）。失敗しても無視。"""
    sound = (
        "/System/Library/Sounds/Glass.aiff" if success
        else "/System/Library/Sounds/Basso.aiff"
    )
    try:
        subprocess.Popen(
            ["afplay", sound],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def _copy_caption_to_clipboard(caption: str) -> bool:
    """キャプション本文をクリップボードへコピー。失敗してもFalseを返すだけ。"""
    if not caption:
        return False
    try:
        subprocess.run(
            ["pbcopy"], input=caption.encode("utf-8"), check=True, timeout=5
        )
        return True
    except Exception:
        return False


def _log_error(error_text: str, base_dir: str) -> str:
    """エラー詳細をログファイルへ保存し、パスを返す。"""
    log_dir = os.path.join(base_dir, "outputs", "logs")
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"error_{ts}.log")
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(error_text)
    except Exception:
        pass
    return log_path


def _user_friendly_error(error: Exception, base_dir: str) -> None:
    """エラーを日本語・次のステップ付きで表示し、ログへ保存する。"""
    SEP = "━" * 44
    msg = str(error)

    print()
    print(SEP)
    print("  ❌ エラーが発生しました")
    print(SEP)
    print()

    if "OPENAI_API_KEY" in msg or "api_key" in msg.lower():
        print("  OpenAI APIキーが見つかりません。")
        print()
        print("  次にすること：")
        print("  1. プロジェクト内の .env ファイルを開く")
        print("  2. OPENAI_API_KEY=sk-... の形式でAPIキーを入力する")
        print("  3. 再度 ./run_instagram.sh を実行する")
    elif "認証エラー" in msg or "AuthenticationError" in msg:
        print("  OpenAI APIの認証に失敗しました。")
        print()
        print("  次にすること：")
        print("  1. .env の OPENAI_API_KEY が正しいか確認する")
        print("  2. https://platform.openai.com/api-keys でキーの有効期限を確認する")
        print("  3. 再度 ./run_instagram.sh を実行する")
    elif "利用上限" in msg or "RateLimitError" in msg:
        print("  OpenAI APIの利用上限に達しました。")
        print()
        print("  次にすること：")
        print("  1. しばらく待ってから再実行する（通常1〜5分後）")
        print("  2. https://platform.openai.com/usage で使用状況を確認する")
        print("  3. 問題が続く場合は、.env の OPENAI_MODEL を gpt-4o-mini に変更する")
    elif "タイムアウト" in msg or "timeout" in msg.lower():
        print("  OpenAI APIがタイムアウトしました。")
        print()
        print("  次にすること：")
        print("  1. ネット接続を確認する")
        print("  2. 再度 ./run_instagram.sh を実行する（通常は再実行で解決します）")
    else:
        print(f"  予期しないエラーが発生しました。")
        print()
        print("  次にすること：")
        print("  1. 下記のログファイルをClaude Codeに見せる")
        print("  2. 再度 ./run_instagram.sh を実行して再現するか確認する")

    import traceback
    log_text = f"Error: {msg}\n\nTraceback:\n{traceback.format_exc()}"
    log_path = _log_error(log_text, base_dir)
    print()
    print(f"  詳細ログ: {os.path.relpath(log_path)}")
    print(SEP)
    print()



# ── ターミナル表示 ────────────────────────────────────────────────────────────

def _print_sheet_result(
    ok: bool,
    row: int,
    hook: str,
    status: str,
    reason: str,
    post_path: str,
) -> None:
    """Sheets 保存結果をターミナルへ表示する。欠損値があっても例外を出さない。"""
    try:
        if ok:
            row_disp  = f"{row}行目" if row and row > 0 else "（スキップ: 重複）"
            hook_disp = (hook or "")[:30] + ("..." if len(hook or "") > 30 else "")
            print(f"  Googleスプレッドシート保存：成功")
            print(f"  シート：reel_scripts  追加行：{row_disp}")
            print(f"  Hook：{hook_disp}  ステータス：{status or ''}")
        else:
            post_basename = os.path.basename(post_path) if post_path else "（なし）"
            print(f"  Googleスプレッドシート保存：失敗")
            print(f"  Markdown保存：成功  ファイル：{post_basename}")
            print(f"  原因：{reason or '不明'}")
            if "GOOGLE_SHEET_ID" in (reason or "") or "設定されていません" in (reason or ""):
                print("  次にすること：.env の GOOGLE_SHEET_ID を確認してください。")
            elif "認証" in (reason or "") or "credential" in (reason or "").lower():
                print("  次にすること：GOOGLE_SERVICE_ACCOUNT_JSON の設定を確認してください。")
            else:
                print("  次にすること：outputs/logs/error_*.log を確認してください。")
    except Exception as e:
        print(f"  [WARNING] スプレッドシート保存結果の表示に失敗しました: {e}")
    print()


def _open_sheet_url() -> None:
    """GOOGLE_SHEET_ID をもとにブラウザでスプレッドシートを開く。失敗しても無視。"""
    try:
        from config import GOOGLE_SHEET_ID
        if not GOOGLE_SHEET_ID:
            return
        url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}"
        subprocess.Popen(
            ["open", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def _print_concise_summary(
    handoff: dict,
    status: str,
    editor_review: str,
    opened: bool,
    copied: bool,
    missing_files: list[str],
) -> None:
    """生成完了後のターミナル簡潔サマリーを表示する。"""
    hook      = handoff.get("hook", "")
    post_type = handoff.get("post_type", "")
    ok        = (status == "投稿OK")

    SEP = "━" * 44
    print()
    print(SEP)
    print("  Instagram投稿 生成完了")
    print(SEP)
    print()
    hook_disp = hook if len(hook) <= 36 else hook[:33] + "..."
    print(f"  Hook    : {hook_disp}")
    print(f"  投稿目的: {post_type}")
    print()

    if ok:
        print("  ✅ 投稿OK")
    else:
        print("  ⚠️  要修正")

    if editor_review:
        print()
        print("  ── Instagram編集長レビュー ──────────")
        for line in editor_review.splitlines():
            print(f"  {line}")
        print("  ─────────────────────────────────────")

    print()
    if opened:
        print("  ✅ 完成版を開きました")
    if copied:
        print("  ✅ キャプションをクリップボードへコピーしました")
    elif ok and not copied:
        print("  ※ クリップボードへのコピーに失敗しました")

    if missing_files:
        print()
        print(f"  ⚠️  ファイル未生成: {', '.join(missing_files)}")

    print()
    print(SEP)
    print("  次にすること：")
    print("  1. サムネイルを撮る（完成版参照）")
    print("  2. 30秒台本で撮影する")
    if ok:
        print("  3. キャプションを貼り付けて投稿")
    else:
        print("  3. 完成版ファイルを開いて修正する")
    print(SEP)
    print()



# ── メイン実行 ────────────────────────────────────────────────────────────────

def generate_post(handoff: dict, dry_run: bool = False) -> Optional[dict]:
    """
    handoff情報からOpenAI Responses APIで投稿一式を生成する。

    dry_run=True の場合: APIを呼ばずプロンプトと保存先のみ表示して返す。
    """
    from phase2.prompt_generator import build_prompt
    from phase2.model_pricing import estimate_cost
    from config import OPENAI_MODEL

    prompt   = build_prompt(handoff)
    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    SEP = "=" * 60

    # ── dry-run モード ──────────────────────────────────────────────────
    if dry_run:
        print()
        print(SEP)
        print("  [dry-run] APIは呼びません。送信予定プロンプトを表示します。")
        print(SEP)
        print()
        print(f"モデル: {OPENAI_MODEL}")
        print(f"Hook:   {handoff.get('hook', '')}")
        print(f"目的:   {handoff.get('post_type', '')}")
        print()
        print("── プロンプト先頭500文字 ──")
        print(prompt[:500])
        print("...")
        print()
        out_dir = os.path.join(base_dir, "outputs")
        print("── 保存先（実行時） ──")
        print(f"  投稿:     {out_dir}/instagram_post_{ts}.md")
        print(f"  入力:     {out_dir}/inputs/instagram_input_{ts}.md")
        print(f"  最新:     {out_dir}/latest_instagram_post.md")
        print(SEP)
        print()
        return None

    # ── 生成 ────────────────────────────────────────────────────────────
    print()
    print(SEP)
    print(f"  投稿生成を開始します（モデル: {OPENAI_MODEL}）")
    print(SEP)

    content = ""
    try:
        print("  [API] 生成中...")
        content, in_tok, out_tok = _call_api(prompt, OPENAI_MODEL)
        cost = estimate_cost(OPENAI_MODEL, in_tok, out_tok)
        print(f"  [API] 完了 — 入力:{in_tok}tok / 出力:{out_tok}tok / 推定費用:{cost}")
    except Exception as e:
        _user_friendly_error(e, base_dir)
        _play_sound(success=False)
        return None

    # ── 投稿OK / 要修正 判定 ──────────────────────────────────────────
    validation = validate_output(content)
    status     = validation["status"]

    # ── ファイル保存 ──────────────────────────────────────────────────
    paths: dict[str, str] = {}
    try:
        paths = _save_outputs(content, handoff, status, ts, base_dir)
        print(f"  ✔ 保存  {os.path.basename(paths['post'])}")
    except Exception as e:
        print(f"  [エラー] ファイル保存失敗: {e}")

    # ── latest_instagram_post.md へコピー ────────────────────────────
    if paths.get("post"):
        try:
            latest_path = _update_latest(paths["post"], base_dir)
            paths["latest"] = latest_path
            print(f"  ✔ 最新版更新  {os.path.basename(latest_path)}")
        except Exception as e:
            print(f"  [警告] latest の更新に失敗しました: {e}")

    # ── 分割ファイル保存（caption / reel / thumbnail）─────────────────
    split_paths: dict[str, str] = {}
    if paths.get("post"):
        try:
            split_paths = _save_split_outputs(content, ts, base_dir)
            for fname in split_paths:
                print(f"  ✔ 保存  {fname}")
        except Exception as e:
            print(f"  [警告] 分割ファイル保存に失敗しました: {e}")

    print()

    # ── ファイル存在確認 ─────────────────────────────────────────────
    missing_files = _verify_latest_files(base_dir)

    # ── Google Sheets へ保存 ──────────────────────────────────────
    sheet_row  = 0
    sheet_ok   = False
    sheet_fail_reason = ""
    sheet_entry: dict = {}
    if paths.get("post"):
        try:
            from sheets_writer import save_reel_script
            sheet_entry = _build_reel_script_entry(
                content, handoff, status, ts, paths["post"]
            )
            sheet_row = save_reel_script(sheet_entry)
            sheet_ok  = True
        except Exception as e:
            sheet_fail_reason = str(e)[:80]

    # ── キャプションをクリップボードへコピー（投稿OKのみ） ───────────
    copied = False
    if status == "投稿OK" and paths.get("post"):
        caption = _extract_caption_plain(content)
        copied  = _copy_caption_to_clipboard(caption)

    # ── ファイルを自動オープン ────────────────────────────────────────
    opened = False
    latest = paths.get("latest")
    if latest and os.path.exists(latest):
        opened = _open_markdown(latest)

    # ── Sheets 保存結果をターミナルへ表示 ────────────────────────────
    try:
        _print_sheet_result(
            ok=sheet_ok,
            row=sheet_row,
            hook=handoff.get("hook", ""),
            status=sheet_entry.get("status", "") if sheet_ok else "生成失敗",
            reason=sheet_fail_reason,
            post_path=paths.get("post", ""),
        )
    except Exception as e:
        print(f"  [WARNING] 保存結果表示エラー: {e}")
        print()

    # ── Sheets の URL をブラウザで開く（保存成功時） ──────────────
    if sheet_ok and sheet_row > 0:
        try:
            _open_sheet_url()
        except Exception:
            pass

    # ── Instagram編集長レビュー（1回のAPIコール）─────────────────────
    editor_review = ""
    print("  [編集長レビュー] 確認中...")
    try:
        from openai_analyzer import review_post_as_editor
        editor_review = review_post_as_editor(content, model=OPENAI_MODEL)
    except Exception as e:
        editor_review = f"（レビュー取得失敗: {str(e)[:50]}）"

    # ── 完了音 ────────────────────────────────────────────────────────
    _play_sound(success=(status == "投稿OK"))

    # ── 簡潔サマリー ─────────────────────────────────────────────────
    _print_concise_summary(
        handoff=handoff,
        status=status,
        editor_review=editor_review,
        opened=opened,
        copied=copied,
        missing_files=missing_files,
    )

    return {
        "content":  content,
        "status":   status,
        "paths":    {**paths, **split_paths},
    }
