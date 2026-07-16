"""
phase2/post_generator.py

CORE HARI FACE — OpenAI Responses API 呼び出し + 自動検証 + 保存

【2026-07-15(3回目): 全面書き直し。
  - OpenAI Responses API（client.responses.create）を使用
  - 20項目自動検証 + 1回だけ自動再生成
  - トークン使用量・推定費用ログ
  - outputs/instagram_post_*.md
  - outputs/inputs/instagram_input_*.md
  - outputs/validation/instagram_validation_*.json
  - outputs/latest_instagram_post.md（常に最新を上書き）
  - クリップボードコピー（pbcopy、失敗しても続行）
  - --dry-run モード対応（APIを呼ばずプロンプトと保存先のみ表示）
】
【2026-07-15(4回目): 検証精度改善。
  - カルーセル枚数: スライドN【 パターン（固有番号）で数える（Canva混入防止）
  - _strip_md: 見出し行・セクション番号行・文字数記載を除去（本文のみ計測）
  - Threads: 200〜400文字を厳密適用
  - 30秒台本: 150〜180文字を厳密適用
  - 60秒台本: 350〜400文字を厳密適用
  - Expert Angle判定: キーワード一致 → OpenAI APIで YES/PARTIAL/NO 3段階判定
  - CTA目的判定: 目的別キーワードを具体化
  - ハッシュタグ: カテゴリ別（3+5+5+3）に分けて判定
  - Hook回答: スライド2・3の本文量を厳密チェック
  - チェック形式: (label, ok, note) → (label, status, note) PASS/WARNING/FAIL
  - 品質スコア: ★★★★★ 表示を追加
  - 自己採点上限: 強化版ペナルティ
】
【2026-07-16(5回目): UX自動化対応。
  - Markdownを「今日使う部分」先頭構造に変更（reel-first）
  - outputs/latest_caption.txt, latest_reel_30sec.txt, latest_thumbnail.txt 自動保存
  - outputs/validation/latest_validation.json 自動保存
  - キャプションのみクリップボードへコピー（PASS/WARNING時のみ）
  - latest_instagram_post.md を macOS open で自動オープン
  - 完了音: afplay Glass.aiff（成功）/ Basso.aiff（失敗）
  - ターミナル表示を簡潔なサマリーに変更（全文非表示）
  - エラーメッセージを日本語・次のステップ付きに変更
  - 生成完了後に5ファイルの存在を検証
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
    all_markers = list("①②③④⑤⑥⑦⑧⑨⑩⑪⑫") + ["【リール優先サマリー】"]
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
    validation: dict,
    final_score: int,
    ts: str,
    post_path: str,
) -> dict:
    """
    reel_scripts シートへ保存する1行分のデータを構築する。
    """
    fail_count = len(validation.get("failed_items", []))
    warn_count = len(validation.get("warning_items", []))
    pass_count = len([s for _, s, _ in validation["checks"] if s == "PASS"])

    # ステータス（FAILが0かつWARNINGが0のみ「投稿可能」）
    if fail_count == 0 and warn_count == 0:
        status = "投稿可能"
    elif fail_count == 0:
        status = "要確認"
    else:
        status = "修正必要"

    reel_summary = _extract_section(content, "【リール優先サマリー】")
    thumb = _extract_thumbnail_fields(content)
    expert_angles = handoff.get("expert_angles", [])

    return {
        "generated_at":          datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "generation_id":         ts,
        "status":                status,
        "quality_score":         final_score,
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
        "validation_pass":       pass_count,
        "validation_warning":    warn_count,
        "validation_fail":       fail_count,
        "output_file":           os.path.basename(post_path) if post_path else "",
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


def _build_today_section(content: str, handoff: dict, final_score: int, ts: str) -> str:
    """
    Markdownの先頭に置く「✅ 今日使う部分」セクションを構築する。
    """
    hook      = handoff.get("hook", "")
    post_type = handoff.get("post_type", "")

    reel_summary = _extract_section(content, "【リール優先サマリー】")

    def field(keyword: str) -> str:
        v = _extract_reel_field(reel_summary, keyword)
        return v if v else "（AIが出力しませんでした）"

    s3 = _extract_section(content, "③")
    cta_text = re.sub(r"^.*③[^\n]*\n", "", s3, flags=re.MULTILINE).strip()

    lines = [
        "# ✅ 今日使う部分",
        "",
        f"> **Hook**: {hook}",
        f"> **投稿目的**: {post_type}",
        f"> **生成スコア**: {final_score}点  |  生成日時: {ts}",
        "",
        "---",
        "",
        "## おすすめ投稿形式",
        "",
        field("今回おすすめの投稿形式"),
        "",
        "## サムネイル",
        "",
        field("おすすめサムネイル詳細"),
        "",
        "## 冒頭3秒テロップ",
        "",
        field("冒頭3秒テロップ"),
        "",
        "## 30秒リール台本",
        "",
        field("30秒リール完成版"),
        "",
        "## 撮影構図",
        "",
        field("撮影構図"),
        "",
        "## 投稿キャプション",
        "",
        field("投稿キャプション"),
        "",
        "## CTA",
        "",
        cta_text,
        "",
        "## 撮影チェックリスト",
        "",
        field("撮影チェックリスト"),
        "",
        "---",
        "",
        "# 参考情報（全出力）",
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


# ── Expert Angle API判定 ──────────────────────────────────────────────────────

def _check_expert_angle_api(carousel_text: str, expert_angles: list, model: str) -> tuple[str, str]:
    """
    Expert Angleの反映度をOpenAI APIで3段階（YES/PARTIAL/NO）判定する。
    Returns: (status, reason_text)
    """
    if not expert_angles:
        return "YES", "Expert Angle未設定のためスキップ"

    ea_str = "\n".join(f"・{a}" for a in expert_angles)
    prompt = (
        "以下のInstagram投稿（カルーセル）は、ユーザーが選択したExpert Angleを"
        "十分反映していますか。\n\n"
        f"【Expert Angle】\n{ea_str}\n\n"
        f"【カルーセル本文】\n{carousel_text[:1500]}\n\n"
        "YES・PARTIAL・NOの3段階で評価し、理由を50文字以内で答えてください。\n"
        "形式（1行のみ）: YES: 理由 / PARTIAL: 理由 / NO: 理由"
    )
    try:
        from openai import OpenAI
        from config import OPENAI_API_KEY
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.responses.create(model=model, input=prompt)
        answer = (resp.output_text or "").strip().splitlines()[0]
        upper = answer.upper()
        if upper.startswith("YES"):
            return "YES", answer
        elif upper.startswith("PARTIAL"):
            return "PARTIAL", answer
        else:
            return "NO", answer
    except Exception as e:
        return "PARTIAL", f"API確認失敗（{str(e)[:40]}）"


# ── 検証ロジック ──────────────────────────────────────────────────────────────

def validate_output(content: str, handoff: dict, model: str = "gpt-4o-mini") -> dict:
    """
    生成テキストを検証する。

    checks の各要素: (label, status, note)
      status: "PASS" / "WARNING" / "FAIL"

    Returns:
        {
            "checks":       [(label, status, note), ...],
            "passed":       bool,      # FAILが0件ならTrue
            "failed_items": [label],
            "warning_items":[label],
        }
    """
    hook      = handoff.get("hook", "")
    post_type = handoff.get("post_type", "")
    ea_list   = handoff.get("expert_angles", [])

    checks: list[tuple[str, str, str]] = []

    def chk(label: str, ok: bool, note: str = ""):
        checks.append((label, "PASS" if ok else "FAIL", note))

    def chk3(label: str, status: str, note: str = ""):
        checks.append((label, status, note))

    # ── ① カルーセル7枚 ─────────────────────────────────────────────────
    s1 = _extract_section(content, "①")
    unique_slide_nums = set(re.findall(r"スライド(\d+)【", s1))
    slide_count = len(unique_slide_nums)
    chk("カルーセル7枚", slide_count == 7, f"{slide_count}枚")

    # ── ② スライド1がHookと完全一致 ────────────────────────────────────
    slide1_block = re.search(r"スライド1【[^】]*】[\s\S]*?(?=スライド2【|$)", s1)
    hook_in_slide1 = hook.strip() in (slide1_block.group(0) if slide1_block else s1[:400])
    chk("スライド1Hook完全一致", hook_in_slide1)

    # ── ③ Hookの答えをスライド2か3で回収 ───────────────────────────────
    slide2_block = re.search(r"スライド2【[\s\S]*?(?=スライド3【|$)", s1)
    slide3_block = re.search(r"スライド3【[\s\S]*?(?=スライド4【|$)", s1)
    s2_text = slide2_block.group(0) if slide2_block else ""
    s3_text = slide3_block.group(0) if slide3_block else ""
    hook_answered = _count_body(s2_text) > 30 or _count_body(s3_text) > 30
    chk("Hookの答えをスライド2か3で回収", hook_answered,
        f"スライド2:{_count_body(s2_text)}字 / スライド3:{_count_body(s3_text)}字")

    # ── ④ キャプション200〜300文字 ─────────────────────────────────────
    cap_body = _extract_section(content, "②")
    cap_len = _count_body(cap_body)
    chk("キャプション200〜300文字", 200 <= cap_len <= 300, f"{cap_len}文字")

    # ── ⑤ CTA 3案ある ──────────────────────────────────────────────────
    s3_sec = _extract_section(content, "③")
    cta_count = len(re.findall(r"^\d+\.", s3_sec, re.MULTILINE))
    if cta_count < 3:
        cta_count = len(re.findall(r"「.+?」", s3_sec))
    chk("CTA3案", cta_count >= 3, f"{cta_count}案")

    # ── ⑥ CTAが投稿目的と一致 ──────────────────────────────────────────
    purpose_key = post_type.replace("型", "").strip()
    pat = _CTA_PURPOSE_PATTERNS.get(purpose_key, "")
    cta_match = bool(re.search(pat, s3_sec)) if pat else True
    chk(f"CTA目的一致（{purpose_key}型）", cta_match)

    # ── ⑦ Threads 200〜400文字 ─────────────────────────────────────────
    s4_sec = _extract_section(content, "④")
    threads_body = re.sub(r"#\S+", "", s4_sec)
    thr_len = _count_body(threads_body)
    chk("Threads200〜400文字", 200 <= thr_len <= 400, f"{thr_len}文字")

    # ── ⑧ Threads末尾ハッシュタグ2〜3個 ───────────────────────────────
    ht_in_threads = re.findall(r"#\S+", s4_sec)
    chk("Threadsハッシュタグ2〜3個", 2 <= len(ht_in_threads) <= 3, f"{len(ht_in_threads)}個")

    # ── ⑨ X 140文字以内 ────────────────────────────────────────────────
    s5_sec = _extract_section(content, "⑤")
    x_len = _count_body(s5_sec)
    chk("X140文字以内", x_len <= 140, f"{x_len}文字")

    # ── ⑩ X末尾に文字数記載 ────────────────────────────────────────────
    x_has_count = bool(re.search(r"（\d+文字）", s5_sec))
    chk("X文字数記載あり", x_has_count)

    # ── ⑪ 30秒台本 150〜180文字（本文のみ） ────────────────────────────
    s6_sec = _extract_section(content, "⑥")
    r30_len = _count_body(s6_sec)
    chk("30秒台本150〜180文字", 150 <= r30_len <= 180, f"{r30_len}文字")

    # ── ⑫ 60秒台本 350〜400文字（本文のみ） ────────────────────────────
    s7_sec = _extract_section(content, "⑦")
    r60_len = _count_body(s7_sec)
    chk("60秒台本350〜400文字", 350 <= r60_len <= 400, f"{r60_len}文字")

    # ── ⑬ Canva 7枚分 ──────────────────────────────────────────────────
    s8_sec = _extract_section(content, "⑧")
    canva_count = len(re.findall(r"スライド\d+【", s8_sec))
    if canva_count == 0:
        canva_count = len(set(re.findall(r"スライド(\d+)", s8_sec)))
    chk("Canva7枚分", canva_count == 7, f"{canva_count}枚")

    # ── ⑭ タイトル5案 ──────────────────────────────────────────────────
    s9_sec = _extract_section(content, "⑨")
    title_count = len(re.findall(r"^\d+\.", s9_sec, re.MULTILINE))
    if title_count < 5:
        title_count = len(re.findall(r"「.+?」", s9_sec))
    chk("タイトル5案", title_count >= 5, f"{title_count}案")

    # ── ⑮ ハッシュタグ カテゴリ別（3+5+5+3=16個、重複なし） ────────────
    s10_sec = _extract_section(content, "⑩")
    all_tags = re.findall(r"#\S+", s10_sec)
    unique_tags = list(dict.fromkeys(all_tags))

    def _count_tags_in_block(text: str, label_pattern: str) -> int:
        m = re.search(label_pattern + r"[^\n]*\n([\s\S]*?)(?=大カテゴリ|中カテゴリ|小カテゴリ|CORE|$)",
                      text, re.IGNORECASE)
        if not m or m.lastindex is None:
            return -1
        block = m.group(1) or ""
        return len(re.findall(r"#\S+", block))

    cat_large = _count_tags_in_block(s10_sec, r"大カテゴリ")
    cat_mid   = _count_tags_in_block(s10_sec, r"中カテゴリ")
    cat_small = _count_tags_in_block(s10_sec, r"小カテゴリ")
    cat_brand = _count_tags_in_block(s10_sec, r"CORE\s*HARI|ブランド|専用")

    total_unique = len(unique_tags)
    tag_note_parts = [f"合計{total_unique}個"]
    if cat_large >= 0: tag_note_parts.append(f"大{cat_large}")
    if cat_mid   >= 0: tag_note_parts.append(f"中{cat_mid}")
    if cat_small >= 0: tag_note_parts.append(f"小{cat_small}")
    if cat_brand >= 0: tag_note_parts.append(f"ブランド{cat_brand}")
    tag_note = " / ".join(tag_note_parts)

    tag_ok = total_unique == 16
    if cat_large >= 0 and cat_mid >= 0 and cat_small >= 0 and cat_brand >= 0:
        tag_ok = tag_ok and (cat_large == 3 and cat_mid == 5 and cat_small == 5 and cat_brand == 3)
    chk("ハッシュタグ16個（3+5+5+3）", tag_ok, tag_note)

    chk("ハッシュタグ重複なし", len(all_tags) == total_unique,
        "" if len(all_tags) == total_unique else f"重複{len(all_tags) - total_unique}個")

    # ── ⑯ サムネイル3案 ────────────────────────────────────────────────
    s12_sec = _extract_section(content, "⑫")
    thumb_count = len(re.findall(r"\*\*案\d+", s12_sec))
    if thumb_count == 0:
        thumb_count = len(re.findall(r"案\d+[:：]", s12_sec))
    chk("サムネイル3案", thumb_count >= 3, f"{thumb_count}案")

    # ── ⑰ 禁止表現なし ─────────────────────────────────────────────────
    found_ng = [p for p in _FORBIDDEN_PHRASES if p in content]
    chk("禁止表現なし", len(found_ng) == 0, "、".join(found_ng) if found_ng else "")

    # ── ⑱ Expert Angle反映（OpenAI API 3段階判定） ──────────────────────
    if ea_list:
        ea_status, ea_reason = _check_expert_angle_api(s1, ea_list, model)
        if ea_status == "YES":
            chk3("Expert Angle反映", "PASS", ea_reason)
        elif ea_status == "PARTIAL":
            chk3("Expert Angle反映", "WARNING", ea_reason)
        else:
            chk3("Expert Angle反映", "FAIL", ea_reason)
    else:
        chk3("Expert Angle反映", "PASS", "Expert Angle未設定")

    # ── ⑲ リール優先サマリーあり ────────────────────────────────────────
    reel_summary = _extract_section(content, "【リール優先サマリー】")
    chk("リール優先サマリーあり", len(reel_summary) > 50)

    failed   = [label for label, status, _ in checks if status == "FAIL"]
    warnings = [label for label, status, _ in checks if status == "WARNING"]
    return {
        "checks":        checks,
        "passed":        len(failed) == 0,
        "failed_items":  failed,
        "warning_items": warnings,
    }


# ── AIスコア調整（強化版） ────────────────────────────────────────────────────

def _adjust_score(content: str, validation: dict) -> tuple[int, str]:
    """
    AIの自己採点スコアを取り出し、プログラム検証の違反に応じて上限を設定する。
    Returns: (final_score, explanation)
    """
    raw_match = re.search(r"合計点[^\d]*(\d+)点", content)
    ai_score = int(raw_match.group(1)) if raw_match else 0

    penalties = []
    cap = ai_score

    failed   = set(validation.get("failed_items", []))
    warnings = set(validation.get("warning_items", []))

    if failed and cap >= 95:
        cap = 94
        penalties.append("形式違反あり: 合計95点以上禁止 → 上限94点")

    if "Hookの答えをスライド2か3で回収" in failed:
        if cap > 80:
            cap = 80
        penalties.append("Hook未回収: Hook力最大12点 → 合計上限80点")

    if "Expert Angle反映" in failed:
        if cap > 80:
            cap = 80
        penalties.append("Expert Angle FAIL: CORE HARI最大10点 → 合計上限80点")
    elif "Expert Angle反映" in warnings:
        if cap > 88:
            cap = 88
        penalties.append("Expert Angle WARNING: CORE HARI最大15点 → 合計上限88点")

    if "Threads200〜400文字" in failed:
        if cap > 85:
            cap = 85
        penalties.append("Threads文字数FAIL: 共感最大10点 → 合計上限85点")

    if "60秒台本350〜400文字" in failed:
        if cap > 85:
            cap = 85
        penalties.append("60秒台本FAIL: セルフケア最大10点 → 合計上限85点")

    if "ハッシュタグ16個（3+5+5+3）" in failed:
        cap = max(0, cap - 5)
        penalties.append("ハッシュタグ不足: -5点")

    if "禁止表現なし" in failed:
        if cap > 70:
            cap = 70
        penalties.append("禁止表現あり: NG遵守最大5点 → 合計上限70点")

    if any("CTA目的" in f for f in failed):
        if cap > 75:
            cap = 75
        penalties.append("CTA不一致: 全体の一貫性最大5点 → 合計上限75点")

    explanation = "\n".join(penalties) if penalties else "プログラム検証の減点なし"
    return cap, explanation


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
    validation: dict,
    final_score: int,
    score_note: str,
    ts: str,
    base_dir: str,
) -> dict[str, str]:
    """
    タイムスタンプ付き3ファイル + 分割ファイルを保存してパスを返す。
    latest_instagram_post.md の書き込みは _update_latest() で行う。
    """
    out_dir  = os.path.join(base_dir, "outputs")
    inp_dir  = os.path.join(base_dir, "outputs", "inputs")
    val_dir  = os.path.join(base_dir, "outputs", "validation")
    for d in (out_dir, inp_dir, val_dir):
        os.makedirs(d, exist_ok=True)

    hook      = handoff.get("hook", "")
    post_type = handoff.get("post_type", "")

    # 1. 投稿全文（今日使う部分 → 参考情報 構造）
    today_section = _build_today_section(content, handoff, final_score, ts)
    post_path = os.path.join(out_dir, f"instagram_post_{ts}.md")
    with open(post_path, "w", encoding="utf-8") as f:
        f.write(today_section)
        f.write(content)
        f.write(f"\n\n---\n\n## プログラム検証メモ\n\n{score_note}\n")

    # 2. 入力情報
    inp_path = os.path.join(inp_dir, f"instagram_input_{ts}.md")
    with open(inp_path, "w", encoding="utf-8") as f:
        f.write(f"# CORE HARI FACE — 入力情報\n\n生成日時: {ts}\n\n")
        for k, v in handoff.items():
            if isinstance(v, list):
                v = "\n".join(f"  - {x}" for x in v)
            f.write(f"**{k}**:\n{v}\n\n")

    # 3. 検証結果JSON（タイムスタンプ付き）
    val_path = os.path.join(val_dir, f"instagram_validation_{ts}.json")
    val_data = {
        "timestamp": ts,
        "hook": hook,
        "post_type": post_type,
        "passed": validation["passed"],
        "final_score": final_score,
        "score_note": score_note,
        "checks": [
            {"label": label, "status": status, "note": note}
            for label, status, note in validation["checks"]
        ],
        "failed_items":  validation["failed_items"],
        "warning_items": validation.get("warning_items", []),
    }
    with open(val_path, "w", encoding="utf-8") as f:
        json.dump(val_data, f, ensure_ascii=False, indent=2)

    return {"post": post_path, "input": inp_path, "validation": val_path}


def _save_split_outputs(content: str, validation: dict, final_score: int, ts: str, base_dir: str) -> dict[str, str]:
    """
    キャプション・リール台本・サムネイルを個別ファイルへ保存する。
    validation/latest_validation.json も保存する。
    """
    out_dir = os.path.join(base_dir, "outputs")
    val_dir = os.path.join(base_dir, "outputs", "validation")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(val_dir, exist_ok=True)

    caption   = _extract_caption_plain(content)
    reel30    = _extract_reel_30sec_plain(content)
    thumbnail = _extract_thumbnail_plain(content)

    saved: dict[str, str] = {}
    for fname, text in [
        ("latest_caption.txt",     caption),
        ("latest_reel_30sec.txt",  reel30),
        ("latest_thumbnail.txt",   thumbnail),
    ]:
        path = os.path.join(out_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        saved[fname] = path

    # latest_validation.json
    val_src = os.path.join(val_dir, f"instagram_validation_{ts}.json")
    val_latest = os.path.join(val_dir, "latest_validation.json")
    if os.path.exists(val_src):
        with open(val_src, "r", encoding="utf-8") as f:
            val_content = f.read()
        with open(val_latest, "w", encoding="utf-8") as f:
            f.write(val_content)
        saved["latest_validation.json"] = val_latest

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
    5つのlatestファイルが存在するか確認する。
    存在しないファイル名のリストを返す。
    """
    out_dir = os.path.join(base_dir, "outputs")
    required = [
        os.path.join(out_dir, "latest_instagram_post.md"),
        os.path.join(out_dir, "latest_caption.txt"),
        os.path.join(out_dir, "latest_reel_30sec.txt"),
        os.path.join(out_dir, "latest_thumbnail.txt"),
        os.path.join(out_dir, "validation", "latest_validation.json"),
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


# ── 品質スコア ────────────────────────────────────────────────────────────────

def _quality_stars(fail_count: int, warn_count: int) -> tuple[str, str]:
    if fail_count == 0:
        return "★★★★★", "投稿OK"
    elif fail_count <= 2:
        return "★★★★☆", "軽微修正"
    elif fail_count <= 4:
        return "★★★☆☆", "再生成推奨"
    elif fail_count <= 6:
        return "★★☆☆☆", "再生成推奨"
    else:
        return "★☆☆☆☆", "再生成推奨"


# ── ターミナル表示 ────────────────────────────────────────────────────────────

def _print_validation(validation: dict, final_score: int, score_note: str) -> None:
    """詳細な検証結果を表示する（再生成判断用・生成中のみ表示）。"""
    sep = "-" * 50
    print()
    print(sep)
    print("  自動検証結果")
    print(sep)
    for label, status, note in validation["checks"]:
        line = f"  {status}: {label}"
        if note:
            line += f"  {note}"
        print(line)
    print(sep)

    fail_count = len(validation.get("failed_items", []))
    warn_count = len(validation.get("warning_items", []))
    stars, star_label = _quality_stars(fail_count, warn_count)

    print(f"  品質スコア: {stars}  {star_label}")
    print(f"  最終スコア: {final_score}点  (FAIL:{fail_count}件 / WARNING:{warn_count}件)")
    if score_note != "プログラム検証の減点なし":
        for line in score_note.split("\n"):
            print(f"    {line}")
    print(sep)
    print()


def _print_sheet_result(
    ok: bool,
    row: int,
    hook: str,
    status: str,
    reason: str,
    post_path: str,
) -> None:
    """Sheets 保存結果をターミナルへ表示する。"""
    if ok:
        row_disp = f"{row}行目" if row > 0 else "（スキップ: 重複）"
        hook_disp = hook[:30] + "..." if len(hook) > 30 else hook
        print(f"  Googleスプレッドシート保存：成功")
        print(f"  シート：reel_scripts  追加行：{row_disp}")
        print(f"  Hook：{hook_disp}  ステータス：{status}")
    else:
        post_basename = os.path.basename(post_path) if post_path else "（なし）"
        print(f"  Googleスプレッドシート保存：失敗")
        print(f"  Markdown保存：成功  ファイル：{post_basename}")
        print(f"  原因：{reason or '不明'}")
        if "GOOGLE_SHEET_ID" in reason or "設定されていません" in reason:
            print("  次にすること：.env の GOOGLE_SHEET_ID を確認してください。")
        elif "認証" in reason or "credential" in reason.lower():
            print("  次にすること：GOOGLE_SERVICE_ACCOUNT_JSON の設定を確認してください。")
        else:
            print("  次にすること：outputs/logs/error_*.log を確認してください。")
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
    validation: dict,
    final_score: int,
    regen_count: int,
    opened: bool,
    copied: bool,
    missing_files: list[str],
) -> None:
    """生成完了後のターミナル簡潔サマリーを表示する。"""
    hook      = handoff.get("hook", "")
    post_type = handoff.get("post_type", "")

    fail_count = len(validation.get("failed_items", []))
    warn_count = len(validation.get("warning_items", []))
    pass_count = len([s for _, s, _ in validation["checks"] if s == "PASS"])
    stars, _   = _quality_stars(fail_count, warn_count)

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
    print(f"  品質    : {stars}")
    stat_line = f"  PASS:{pass_count}"
    if warn_count:
        stat_line += f"  WARNING:{warn_count}"
    if fail_count:
        stat_line += f"  FAIL:{fail_count}"
    print(stat_line)

    if regen_count > 0:
        print(f"  ※ 自動再生成を1回実行しました")

    print()
    if fail_count == 0:
        print("  ✅ 投稿可能です")
    else:
        print("  ⚠️  投稿前に修正が必要です")
        for item in validation["failed_items"]:
            print(f"     ・{item}")

    if warn_count and fail_count == 0:
        for item in validation["warning_items"]:
            print(f"  ⚠️  WARNING: {item}")

    if opened:
        print("  ✅ 完成版を開きました")
    if copied:
        print("  ✅ キャプションをクリップボードへコピーしました")
    elif fail_count == 0 and not copied:
        print("  ※ クリップボードへのコピーに失敗しました")

    if missing_files:
        print()
        print(f"  ⚠️  ファイル未生成: {', '.join(missing_files)}")

    print()
    print(SEP)
    print("  次にすること：")
    print("  1. サムネイルを撮る（サムネイルガイド参照）")
    print("  2. 台本を見て撮影する")
    if fail_count == 0:
        print("  3. Instagramにキャプションを貼り付ける")
    else:
        print("  3. 完成版ファイルを開いてFAIL項目を修正する")
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
        print(f"  検証:     {out_dir}/validation/instagram_validation_{ts}.json")
        print(f"  最新:     {out_dir}/latest_instagram_post.md")
        print(SEP)
        print()
        return None

    # ── 初回生成 ────────────────────────────────────────────────────────
    print()
    print(SEP)
    print(f"  投稿生成を開始します（モデル: {OPENAI_MODEL}）")
    print(SEP)

    regen_count = 0
    content     = ""

    try:
        print("  [API] 生成中...")
        content, in_tok, out_tok = _call_api(prompt, OPENAI_MODEL)
        cost = estimate_cost(OPENAI_MODEL, in_tok, out_tok)
        print(f"  [API] 完了 — 入力:{in_tok}tok / 出力:{out_tok}tok / 推定費用:{cost}")
    except Exception as e:
        _user_friendly_error(e, base_dir)
        _play_sound(success=False)
        return None

    # ── 初回検証 ────────────────────────────────────────────────────────
    validation  = validate_output(content, handoff, model=OPENAI_MODEL)
    final_score, score_note = _adjust_score(content, validation)
    _print_validation(validation, final_score, score_note)

    # ── FAILがあれば1回だけ再生成 ──────────────────────────────────────
    if not validation["passed"]:
        failed_str = "\n".join(f"- {f}" for f in validation["failed_items"])
        retry_instruction = (
            f"\n\n---\n\n## 修正依頼\n\n"
            f"以下の項目が検証に不合格でした。修正して全出力を再生成してください。\n\n"
            f"{failed_str}\n\n"
            f"全出力（【リール優先サマリー】→①〜⑫）を省略せず再生成してください。"
        )
        print(f"  [再生成] FAIL項目があるため1回再生成します...")
        try:
            content2, in2, out2 = _call_api(prompt + retry_instruction, OPENAI_MODEL)
            cost2 = estimate_cost(OPENAI_MODEL, in2, out2)
            print(f"  [API] 再生成完了 — 入力:{in2}tok / 出力:{out2}tok / 推定費用:{cost2}")
            regen_count = 1
            content     = content2
            validation  = validate_output(content, handoff, model=OPENAI_MODEL)
            final_score, score_note = _adjust_score(content, validation)
            _print_validation(validation, final_score, score_note)
        except Exception as e:
            print(f"  [警告] 再生成中にエラー: {e}。初回生成結果を使用します。")

    # ── ファイル保存 ──────────────────────────────────────────────────
    paths: dict[str, str] = {}
    try:
        paths = _save_outputs(content, handoff, validation, final_score, score_note, ts, base_dir)
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

    # ── 分割ファイル保存（caption / reel / thumbnail / validation）──
    split_paths: dict[str, str] = {}
    if paths.get("post"):
        try:
            split_paths = _save_split_outputs(content, validation, final_score, ts, base_dir)
            for fname in split_paths:
                print(f"  ✔ 保存  {fname}")
        except Exception as e:
            print(f"  [警告] 分割ファイル保存に失敗しました: {e}")

    print()

    # ── 5ファイル存在確認 ────────────────────────────────────────────
    missing_files = _verify_latest_files(base_dir)

    # ── Google Sheets へ保存 ──────────────────────────────────────
    sheet_row  = 0
    sheet_ok   = False
    sheet_fail_reason = ""
    if paths.get("post"):
        try:
            from sheets_writer import save_reel_script
            sheet_entry = _build_reel_script_entry(
                content, handoff, validation, final_score, ts, paths["post"]
            )
            sheet_row = save_reel_script(sheet_entry)
            sheet_ok  = True
        except Exception as e:
            sheet_fail_reason = str(e)[:80]

    # ── キャプションをクリップボードへコピー（投稿可能のみ） ─────
    # 投稿可能 = FAIL 0 かつ WARNING 0
    copied = False
    fail_count = len(validation.get("failed_items", []))
    warn_count = len(validation.get("warning_items", []))
    if fail_count == 0 and warn_count == 0 and paths.get("post"):
        caption = _extract_caption_plain(content)
        copied  = _copy_caption_to_clipboard(caption)

    # ── ファイルを自動オープン ────────────────────────────────────────
    opened = False
    latest = paths.get("latest")
    if latest and os.path.exists(latest):
        opened = _open_markdown(latest)

    # ── Sheets 保存結果をターミナルへ表示 ────────────────────────────
    _print_sheet_result(
        ok=sheet_ok,
        row=sheet_row,
        hook=handoff.get("hook", ""),
        status=sheet_entry.get("status", "") if sheet_ok else "生成失敗",
        reason=sheet_fail_reason,
        post_path=paths.get("post", ""),
    )

    # ── Sheets の URL をブラウザで開く（保存成功時） ──────────────
    if sheet_ok and sheet_row > 0:
        _open_sheet_url()

    # ── 完了音 ────────────────────────────────────────────────────────
    _play_sound(success=(fail_count == 0))

    # ── 簡潔サマリー ─────────────────────────────────────────────────
    _print_concise_summary(
        handoff=handoff,
        validation=validation,
        final_score=final_score,
        regen_count=regen_count,
        opened=opened,
        copied=copied,
        missing_files=missing_files,
    )

    return {
        "content":     content,
        "validation":  validation,
        "final_score": final_score,
        "paths":       {**paths, **split_paths},
        "regen_count": regen_count,
    }
