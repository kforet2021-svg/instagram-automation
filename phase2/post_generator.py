"""
phase2/post_generator.py

CORE HARI FACE — Phase 2 投稿一式生成 + 自動検証

【2026-07-15(1回目): 新規作成。Phase2 投稿生成実行モジュール。】
【2026-07-15(2回目): 自動検証・再生成ロジック追加。
  - validate_output(): 16項目の形式チェック
  - 不合格時に一度だけ自動再生成
  - 禁止表現スキャン
  - 検証結果一覧を先頭に表示
】
"""

from __future__ import annotations

import datetime
import os
import re
from typing import Optional

# ── 禁止表現リスト ────────────────────────────────────────────────────────────

_FORBIDDEN_PHRASES = [
    "主要因です",
    "原因です",
    "のせいです",
    "を予防できます",
    "が解消します",
    "が改善します",
    "治ります",
    "これだけで変わります",
    "効果が長続きします",
]

# ── 投稿目的別 CTA キーワード ─────────────────────────────────────────────────
# 目的型を判定するためのキーワード（いずれか含む = その型）

_CTA_TYPE_KEYWORDS = {
    "保存": ["保存", "見返"],
    "共感": ["教えてください", "シェア", "同じ", "どちら"],
    "信頼": ["コメント", "質問", "気になること", "迷ったら"],
    "行動": ["やってみてください", "試してみてください", "今すぐ", "今日から"],
    "予約": ["施術", "プロの"],
}


# ── 検証ロジック ──────────────────────────────────────────────────────────────

def validate_output(content: str, handoff: dict) -> dict:
    """
    生成テキストを16項目でチェックし、検証結果を返す。

    Returns:
        {
            "checks": [(label, ok, note), ...],
            "passed": bool,            # 全チェック合格か
            "failed_items": [label],   # 不合格項目名リスト
        }
    """
    hook      = handoff.get("hook", "")
    post_type = handoff.get("post_type", "")
    expert_angles = handoff.get("expert_angles", [])

    checks: list[tuple[str, bool, str]] = []

    def add(label: str, ok: bool, note: str = "") -> None:
        checks.append((label, ok, note))

    # 1. カルーセルが7枚あるか
    slide_count = len(re.findall(r"スライド[1-7]", content))
    add("カルーセル7枚", slide_count >= 7, f"検出: {slide_count}枚")

    # 2. スライド1のHookが一字一句同じか
    hook_in_slide = hook in content
    add("スライド1 Hook一致", hook_in_slide, "" if hook_in_slide else f"Hook「{hook[:30]}」が見つかりません")

    # 3. CTAが投稿目的と一致しているか
    cta_keywords = _CTA_TYPE_KEYWORDS.get(post_type, [])
    cta_section = _extract_section(content, "③")
    cta_ok = any(kw in cta_section for kw in cta_keywords) if cta_section else False
    add(f"CTA（{post_type}型）一致", cta_ok, "" if cta_ok else f"期待キーワード: {cta_keywords}")

    # 4. キャプション文字数（200〜300文字）
    cap_section = _extract_section(content, "②")
    cap_len = _body_char_count(cap_section)
    add("キャプション200〜300文字", 150 <= cap_len <= 350,
        f"計測: 約{cap_len}文字（目安±50字で合否）")

    # 5. Threads本文が200〜400文字か
    thr_section = _extract_section(content, "④")
    thr_body = _remove_hashtags(thr_section)
    thr_len = len(thr_body.replace("\n", "").replace(" ", ""))
    add("Threads本文200〜400文字", 150 <= thr_len <= 450, f"計測: 約{thr_len}文字")

    # 6. Threadsにハッシュタグが2〜3個あるか
    thr_tags = re.findall(r"#\S+", thr_section)
    add("Threadsハッシュタグ2〜3個", 2 <= len(thr_tags) <= 3, f"検出: {len(thr_tags)}個")

    # 7. X本文が140文字以内か
    x_section = _extract_section(content, "⑤")
    x_text = re.sub(r"（\d+文字）", "", x_section).strip()
    x_len = len(x_text.replace("\n", ""))
    add("X本文140文字以内", x_len <= 150, f"計測: 約{x_len}文字（±10字で合否）")

    # 8. 30秒台本が150〜180文字程度か
    s30_section = _extract_section(content, "⑥")
    s30_len = _script_char_count(s30_section)
    add("30秒台本150〜180文字", 100 <= s30_len <= 250, f"計測: 約{s30_len}文字")

    # 9. 60秒台本が350〜400文字程度か
    s60_section = _extract_section(content, "⑦")
    s60_len = _script_char_count(s60_section)
    add("60秒台本350〜400文字", 250 <= s60_len <= 500, f"計測: 約{s60_len}文字")

    # 10. Canvaが7枚分あるか
    canva_section = _extract_section(content, "⑧")
    canva_count = len(re.findall(r"スライド[1-7]", canva_section))
    add("Canva7枚分", canva_count >= 7, f"検出: {canva_count}枚")

    # 11. タイトルが5案あるか
    title_section = _extract_section(content, "⑨")
    title_count = len(re.findall(r"[1-5][.．、]|「.{5,40}」", title_section))
    add("タイトル5案", title_count >= 4, f"検出: 約{title_count}案")

    # 12. ハッシュタグ16個あるか（重複除外）
    tag_section = _extract_section(content, "⑩")
    all_tags = re.findall(r"#\S+", tag_section)
    unique_tags = list(set(all_tags))
    add("ハッシュタグ16個（重複除外）",
        len(unique_tags) >= 15,
        f"検出ユニーク: {len(unique_tags)}個（合計{len(all_tags)}個）")

    # 13. 重複ハッシュタグなし
    has_dup = len(all_tags) != len(unique_tags)
    add("ハッシュタグ重複なし", not has_dup,
        "" if not has_dup else f"重複: {len(all_tags) - len(unique_tags)}個")

    # 14. 禁止表現がないか
    found_forbidden = [p for p in _FORBIDDEN_PHRASES if p in content]
    add("禁止表現なし", len(found_forbidden) == 0,
        "" if not found_forbidden else f"検出: {found_forbidden}")

    # 15. Expert Angleが主要出力に反映されているか（全Angleのキーワードベース）
    ea_reflected = False
    if expert_angles:
        # 全Expert Angleのキーワードを検索（いずれか1つが見つかればOK）
        for angle in expert_angles:
            words = [w for w in re.split(r"[、。・\s「」]", angle) if len(w) >= 2]
            for w in words:
                if w in content:
                    ea_reflected = True
                    break
            if ea_reflected:
                break
    else:
        ea_reflected = True
    add("Expert Angle反映", ea_reflected,
        "" if ea_reflected else f"Expert Angle群のキーワードが本文に見当たりません")

    # 16. Hookで提示した疑問が本文で回収されているか
    # Hookに「〜行動」「〜理由」「なぜ」「なに」等があれば回収チェック
    hook_is_question = any(kw in hook for kw in ["行動", "理由", "なぜ", "なに", "何", "どうして", "実は"])
    if hook_is_question:
        # スライド2・3セクションに何らかの答えがあるか
        slide23 = re.search(r"スライド2.{0,500}スライド4", content, re.DOTALL)
        hook_recovered = slide23 is not None and len(slide23.group()) > 50
        add("Hook回答を本文で回収", hook_recovered,
            "" if hook_recovered else "スライド2/3でHookへの答えが見当たりません")
    else:
        add("Hook回答を本文で回収", True, "（問いかけ型Hookではないためスキップ）")

    failed = [label for label, ok, _ in checks if not ok]
    return {
        "checks": checks,
        "passed": len(failed) == 0,
        "failed_items": failed,
    }


def _extract_section(content: str, marker: str) -> str:
    """①〜⑪のセクションテキストを抽出する。
    出力フォーマットは「### ① タイトル\n...」または「① タイトル\n...」のどちらでも対応。
    次のセクションマーカー（①〜⑪）または末尾で終了する。
    """
    # マーカーの位置を探す（行頭 or ### の後）
    start = content.find(marker)
    if start == -1:
        return ""
    # 次のセクションマーカーを探す（①〜⑪ の中で現在より後にあるもの）
    all_markers = "①②③④⑤⑥⑦⑧⑨⑩⑪"
    next_pos = len(content)
    for m in all_markers:
        if m == marker:
            continue
        pos = content.find(m, start + 1)
        if pos != -1 and pos < next_pos:
            next_pos = pos
    return content[start:next_pos]


def _body_char_count(text: str) -> int:
    """改行・空白・ハッシュタグを除いた本文文字数を返す。"""
    text = re.sub(r"#\S+", "", text)
    text = re.sub(r"（\d+文字）", "", text)
    text = re.sub(r"[\s\n]", "", text)
    return len(text)


def _remove_hashtags(text: str) -> str:
    return re.sub(r"#\S+", "", text)


def _script_char_count(text: str) -> int:
    """リール台本の台詞部分のみの文字数を概算する（時間注釈を除く）。"""
    text = re.sub(r"\d+〜\d+秒.*?:", "", text)
    text = re.sub(r"（台本全文\d+文字）", "", text)
    text = re.sub(r"[\s\n]", "", text)
    return len(text)


# ── 検証結果表示 ──────────────────────────────────────────────────────────────

def print_validation_result(result: dict) -> None:
    """検証結果をターミナルに表示する。"""
    print()
    print("=" * 60)
    print("  Phase 2 検証結果")
    print("=" * 60)
    all_pass = result["passed"]
    for label, ok, note in result["checks"]:
        mark = "○" if ok else "✗"
        line = f"  {mark} {label}"
        if note:
            line += f"  ← {note}"
        print(line)
    print()
    if all_pass:
        print("  ✅ 全チェック合格")
    else:
        print(f"  ⚠️  不合格: {', '.join(result['failed_items'])}")
    print("=" * 60)
    print()


# ── メイン生成関数 ────────────────────────────────────────────────────────────

def run_phase2(handoff: dict) -> Optional[str]:
    """
    ChatGPTプロンプトを OpenAI API に送信し、①〜⑪の投稿一式を生成する。
    生成後に検証を実行し、不合格なら一度だけ再生成する。

    Returns:
        最終的な生成テキスト（str）。失敗時は None。
    """
    try:
        from phase2.prompt_generator import build_prompt
    except ImportError:
        from prompt_generator import build_prompt

    try:
        from openai import OpenAI
        from config import OPENAI_API_KEY
    except ImportError as e:
        print(f"[Phase2] インポートエラー: {e}")
        return None

    if not OPENAI_API_KEY:
        print("[Phase2] OPENAI_API_KEY が設定されていません")
        return None

    def _call(attempt: int) -> Optional[str]:
        label = "初回" if attempt == 1 else "再生成（形式違反のため）"
        print()
        print("=" * 60)
        print(f"  Phase 2 — 投稿一式生成中 [{label}]（gpt-4o-mini）")
        print("  ① カルーセル7枚 ② キャプション ③ CTA ④ Threads")
        print("  ⑤ X版 ⑥ 30秒リール ⑦ 60秒リール ⑧ Canvaテキスト")
        print("  ⑨ タイトル5案 ⑩ ハッシュタグ16個 ⑪ AI自己採点")
        print("=" * 60)

        prompt = build_prompt(handoff)
        client = OpenAI(api_key=OPENAI_API_KEY)
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.75,
                timeout=120,
                max_tokens=4500,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"[Phase2] OpenAI APIエラー: {e}")
            return None

    # ── 初回生成 ─────────────────────────────────────────────────────────────
    content = _call(1)
    if not content or not content.strip():
        print("[Phase2] 生成結果が空でした")
        return None

    # ── 検証 ─────────────────────────────────────────────────────────────────
    validation = validate_output(content, handoff)
    print_validation_result(validation)

    # ── 不合格なら一度だけ再生成 ─────────────────────────────────────────────
    if not validation["passed"]:
        print(f"[Phase2] 不合格項目: {validation['failed_items']}")
        print("[Phase2] 自動再生成を実行します...")
        content2 = _call(2)
        if content2 and content2.strip():
            validation2 = validate_output(content2, handoff)
            print_validation_result(validation2)
            content = content2
            validation = validation2

    # ── ターミナル表示 ────────────────────────────────────────────────────────
    sep = "=" * 60
    print()
    print(sep)
    print("  Phase 2 生成結果")
    print(sep)
    print()
    print(content)
    print()
    print(sep)
    print()

    # ── ファイル保存 ──────────────────────────────────────────────────────────
    path = _save_to_file(content, handoff, validation)
    if path:
        print(f"  保存先: {path}")
        print()

    return content


def _save_to_file(content: str, handoff: dict, validation: dict) -> Optional[str]:
    """outputs/instagram_post_YYYYMMDD_HHMMSS.md に保存する。"""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out_dir = os.path.join(base_dir, "outputs")
        os.makedirs(out_dir, exist_ok=True)

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(out_dir, f"instagram_post_{ts}.md")

        hook      = handoff.get("hook", "")
        post_type = handoff.get("post_type", "")
        topic     = handoff.get("topic", "")

        # 検証サマリーを埋め込む
        check_lines = []
        for label, ok, note in validation["checks"]:
            mark = "○" if ok else "✗"
            line = f"- {mark} {label}"
            if note:
                line += f"  ← {note}"
            check_lines.append(line)
        check_md = "\n".join(check_lines)
        pass_label = "✅ 全合格" if validation["passed"] else f"⚠️ 不合格: {', '.join(validation['failed_items'])}"

        header = (
            f"# CORE HARI FACE — Instagram投稿一式\n\n"
            f"生成日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"**Hook**: {hook}\n\n"
            f"**投稿目的**: {post_type}\n\n"
            f"**Topic**: {topic}\n\n"
            f"## 検証結果 — {pass_label}\n\n"
            f"{check_md}\n\n"
            f"---\n\n"
        )

        with open(path, "w", encoding="utf-8") as f:
            f.write(header + content)

        return path
    except Exception as e:
        print(f"[Phase2] ファイル保存エラー: {e}")
        return None
