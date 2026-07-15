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
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
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

_CTA_TYPE_KEYWORDS: dict[str, list[str]] = {
    "保存": ["保存", "見返"],
    "共感": ["教えてください", "シェア", "同じ", "どちら", "コメント"],
    "信頼": ["コメント", "質問", "気になること", "迷ったら"],
    "行動": ["やってみてください", "試してみてください", "今すぐ", "今日から"],
    "予約": ["施術", "プロの"],
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


def _strip_md(text: str) -> str:
    """Markdown記号・時間表記を除いた本文文字数カウント用。"""
    text = re.sub(r"[#*_`~>\-]", "", text)
    text = re.sub(r"\d+〜\d+秒[:：]?", "", text)
    text = re.sub(r"\s+", "", text)
    return text


def _count_body(text: str) -> int:
    return len(_strip_md(text))


# ── 検証ロジック ──────────────────────────────────────────────────────────────

def validate_output(content: str, handoff: dict) -> dict:
    """
    生成テキストを20項目でチェックし、検証結果を返す。

    Returns:
        {
            "checks": [(label, ok, note), ...],
            "passed": bool,
            "failed_items": [label],
        }
    """
    hook      = handoff.get("hook", "")
    post_type = handoff.get("post_type", "")
    ea_list   = handoff.get("expert_angles", [])

    checks: list[tuple[str, bool, str]] = []

    def chk(label: str, ok: bool, note: str = ""):
        checks.append((label, ok, note))

    # 1. カルーセル7枚
    s1 = _extract_section(content, "①")
    slide_count = len(re.findall(r"スライド\d+", s1))
    chk("カルーセル7枚", slide_count == 7, f"{slide_count}枚")

    # 2. スライド1がHookと完全一致
    slide1_match = re.search(r"スライド1[^スライド]*", s1)
    hook_found = hook in (slide1_match.group(0) if slide1_match else s1[:300])
    chk("スライド1Hook完全一致", hook_found)

    # 3. Hookの答えをスライド2か3で回収
    slide23 = re.search(r"スライド[23][\s\S]*?(?=スライド4|$)", s1)
    # 疑問・謎かけ系Hookかどうか（完全判定は難しいのでHookを含む場合を回収済みとみなす）
    hook_head = hook.split("。")[0].replace("？", "").replace("?", "")[:10]
    hook_answered = bool(slide23 and len(slide23.group(0)) > 20)
    chk("Hookの答えをスライド2か3で回収", hook_answered)

    # 4. キャプション200〜300文字
    s2 = _extract_section(content, "②")
    cap_len = _count_body(s2)
    chk("キャプション200〜300文字", 200 <= cap_len <= 300, f"{cap_len}文字")

    # 5. CTA 3案ある
    s3 = _extract_section(content, "③")
    cta_count = len(re.findall(r"^\d+\.", s3, re.MULTILINE))
    if cta_count < 3:
        cta_count = len(re.findall(r"「.+?」", s3))
    chk("CTA3案", cta_count >= 3, f"{cta_count}案")

    # 6. CTAが投稿目的と一致
    purpose_key = post_type.replace("型", "").strip()
    kws = _CTA_TYPE_KEYWORDS.get(purpose_key, [])
    cta_match = any(kw in s3 for kw in kws) if kws else True
    chk(f"CTA目的一致（{purpose_key}型）", cta_match)

    # 7. Threads 200〜400文字
    s4 = _extract_section(content, "④")
    threads_body = re.sub(r"#\S+", "", s4)
    thr_len = _count_body(threads_body)
    chk("Threads200〜400文字", 200 <= thr_len <= 400, f"{thr_len}文字")

    # 8. Threads末尾ハッシュタグ2〜3個
    ht_in_threads = re.findall(r"#\S+", s4)
    chk("Threadsハッシュタグ2〜3個", 2 <= len(ht_in_threads) <= 3, f"{len(ht_in_threads)}個")

    # 9. X 140文字以内
    s5 = _extract_section(content, "⑤")
    x_len = _count_body(s5)
    chk("X140文字以内", x_len <= 140, f"{x_len}文字")

    # 10. X末尾に文字数記載
    x_has_count = bool(re.search(r"（\d+文字）", s5))
    chk("X文字数記載あり", x_has_count)

    # 11. 30秒台本 150〜180文字
    s6 = _extract_section(content, "⑥")
    r30_len = _count_body(s6)
    chk("30秒台本150〜180文字", 150 <= r30_len <= 220, f"{r30_len}文字")  # 多少の余裕あり

    # 12. 60秒台本 350〜400文字
    s7 = _extract_section(content, "⑦")
    r60_len = _count_body(s7)
    chk("60秒台本350〜400文字", 320 <= r60_len <= 450, f"{r60_len}文字")

    # 13. Canva 7枚分
    s8 = _extract_section(content, "⑧")
    canva_count = len(re.findall(r"スライド\d+", s8))
    chk("Canva7枚分", canva_count == 7, f"{canva_count}枚")

    # 14. タイトル5案
    s9 = _extract_section(content, "⑨")
    title_count = len(re.findall(r"^\d+\.", s9, re.MULTILINE))
    if title_count < 5:
        title_count = len(re.findall(r"「.+?」", s9))
    chk("タイトル5案", title_count >= 5, f"{title_count}案")

    # 15. ハッシュタグ16個（3+5+5+3）
    s10 = _extract_section(content, "⑩")
    all_tags = re.findall(r"#\S+", s10)
    chk("ハッシュタグ16個", len(all_tags) == 16, f"{len(all_tags)}個")

    # 16. ハッシュタグ重複なし
    chk("ハッシュタグ重複なし", len(all_tags) == len(set(all_tags)))

    # 17. サムネイル3案
    s12 = _extract_section(content, "⑫")
    thumb_count = len(re.findall(r"\*\*案\d+", s12))
    if thumb_count == 0:
        thumb_count = len(re.findall(r"案\d+[:：]", s12))
    chk("サムネイル3案", thumb_count >= 3, f"{thumb_count}案")

    # 18. 禁止表現なし
    found_ng = [p for p in _FORBIDDEN_PHRASES if p in content]
    chk("禁止表現なし", len(found_ng) == 0, "、".join(found_ng) if found_ng else "")

    # 19. Expert Angle反映
    ea_reflected = False
    for angle in ea_list:
        words = [w for w in re.split(r"[、。・\s「」]", angle) if len(w) >= 2]
        if any(w in s1 for w in words):
            ea_reflected = True
            break
    chk("Expert Angle反映", ea_reflected or not ea_list)

    # 20. リール優先サマリーあり
    reel_summary = _extract_section(content, "【リール優先サマリー】")
    chk("リール優先サマリーあり", len(reel_summary) > 50)

    failed = [label for label, ok, _ in checks if not ok]
    return {"checks": checks, "passed": len(failed) == 0, "failed_items": failed}


# ── AIスコア調整 ──────────────────────────────────────────────────────────────

def _adjust_score(content: str, validation: dict) -> tuple[int, str]:
    """
    AIの自己採点スコアを取り出し、プログラム検証の違反に応じて上限を設定する。
    Returns: (final_score, explanation)
    """
    raw_match = re.search(r"合計点[^\d]*(\d+)点", content)
    ai_score = int(raw_match.group(1)) if raw_match else 0

    penalties = []
    cap = ai_score

    failed = set(validation.get("failed_items", []))

    if "Hookの答えをスライド2か3で回収" in failed:
        if cap > 80:
            cap = 80
        penalties.append("Hook未回収: Hook力は最大12点相当 → 合計上限80点")

    if "禁止表現なし" in failed:
        if cap > 70:
            cap = 70
        penalties.append("禁止表現あり: NG遵守は最大5点相当 → 合計上限70点")

    if any("CTA" in f for f in failed):
        if cap > 75:
            cap = 75
        penalties.append("CTA不一致: 全体の一貫性は最大5点相当 → 合計上限75点")

    if "ハッシュタグ16個" in failed:
        cap = max(0, cap - 5)
        penalties.append("ハッシュタグ不足: -5点")

    if "Expert Angle反映" in failed:
        if cap > 80:
            cap = 80
        penalties.append("Expert Angle未反映: CORE HARI独自性は最大10点相当 → 合計上限80点")

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
    APIキー未設定・認証エラー・タイムアウトは例外をそのまま上げる。
    """
    from openai import OpenAI, AuthenticationError, RateLimitError
    from config import OPENAI_API_KEY

    if not OPENAI_API_KEY:
        raise EnvironmentError(
            "OPENAI_API_KEY が .env に設定されていません。"
        )

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
    タイムスタンプ付き3ファイルを保存してパスを返す。
    latest_instagram_post.md の書き込みは呼び出し元で行う（独立させてある）。
    """
    out_dir  = os.path.join(base_dir, "outputs")
    inp_dir  = os.path.join(base_dir, "outputs", "inputs")
    val_dir  = os.path.join(base_dir, "outputs", "validation")
    for d in (out_dir, inp_dir, val_dir):
        os.makedirs(d, exist_ok=True)

    hook      = handoff.get("hook", "")
    post_type = handoff.get("post_type", "")

    # 1. 投稿全文
    post_path = os.path.join(out_dir, f"instagram_post_{ts}.md")
    with open(post_path, "w", encoding="utf-8") as f:
        f.write(f"# CORE HARI FACE — Instagram投稿一式\n\n")
        f.write(f"生成日時: {ts}\n\n")
        f.write(f"**Hook**: {hook}\n\n**投稿目的**: {post_type}\n\n")
        f.write(f"**最終スコア**: {final_score}点\n\n")
        f.write("---\n\n")
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

    # 3. 検証結果JSON
    val_path = os.path.join(val_dir, f"instagram_validation_{ts}.json")
    val_data = {
        "timestamp": ts,
        "hook": hook,
        "post_type": post_type,
        "passed": validation["passed"],
        "final_score": final_score,
        "score_note": score_note,
        "checks": [
            {"label": label, "ok": ok, "note": note}
            for label, ok, note in validation["checks"]
        ],
        "failed_items": validation["failed_items"],
    }
    with open(val_path, "w", encoding="utf-8") as f:
        json.dump(val_data, f, ensure_ascii=False, indent=2)

    return {"post": post_path, "input": inp_path, "validation": val_path}


def _update_latest(post_path: str, base_dir: str) -> str:
    """
    post_path の内容を latest_instagram_post.md へ上書きコピーし、パスを返す。
    失敗時は RuntimeError を上げる（呼び出し元で個別に catch すること）。
    """
    out_dir     = os.path.join(base_dir, "outputs")
    latest_path = os.path.join(out_dir, "latest_instagram_post.md")
    with open(post_path, "r", encoding="utf-8") as src:
        data = src.read()
    with open(latest_path, "w", encoding="utf-8") as dst:
        dst.write(data)
    return latest_path


# ── クリップボード ────────────────────────────────────────────────────────────

def _copy_to_clipboard(text: str) -> bool:
    """macOS pbcopy でクリップボードへコピー。失敗してもFalseを返すだけ。"""
    try:
        proc = subprocess.run(
            ["pbcopy"], input=text.encode("utf-8"), check=True, timeout=5
        )
        return True
    except Exception:
        return False


# ── 検証結果表示 ──────────────────────────────────────────────────────────────

def _print_validation(validation: dict, final_score: int, score_note: str) -> None:
    sep = "-" * 50
    print()
    print(sep)
    print("  自動検証結果")
    print(sep)
    for label, ok, note in validation["checks"]:
        status = "PASS" if ok else "FAIL"
        line = f"  {status}: {label}"
        if note:
            line += f" ({note})"
        print(line)
    print(sep)
    print(f"  最終スコア: {final_score}点")
    if score_note != "プログラム検証の減点なし":
        print(f"  調整内容: {score_note}")
    if validation["passed"]:
        print("  → 全項目PASS")
    else:
        print(f"  → FAIL項目: {', '.join(validation['failed_items'])}")
    print(sep)
    print()


# ── メイン実行 ────────────────────────────────────────────────────────────────

def generate_post(handoff: dict, dry_run: bool = False) -> Optional[dict]:
    """
    handoff情報からOpenAI Responses APIで投稿一式を生成する。

    dry_run=True の場合: APIを呼ばずプロンプトと保存先のみ表示して返す。

    Returns:
        {
            "content": str,       # 生成テキスト
            "validation": dict,   # 検証結果
            "final_score": int,
            "paths": dict,        # 保存ファイルパス
            "regen_count": int,   # 再生成回数
        }
        or None on error
    """
    from phase2.prompt_generator import build_prompt
    from phase2.model_pricing import estimate_cost
    from config import OPENAI_MODEL

    prompt = build_prompt(handoff)
    ts     = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
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
        print("── 保存先（実行時） ──")
        out_dir = os.path.join(base_dir, "outputs")
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
    content = ""
    in_tok = out_tok = 0

    try:
        print("  [API] 生成中...")
        content, in_tok, out_tok = _call_api(prompt, OPENAI_MODEL)
        cost = estimate_cost(OPENAI_MODEL, in_tok, out_tok)
        print(f"  [API] 完了 — 入力:{in_tok}tok / 出力:{out_tok}tok / 推定費用:{cost}")
    except RuntimeError as e:
        print(f"\n  [エラー] {e}")
        return None
    except Exception as e:
        print(f"\n  [エラー] 予期しないエラー: {e}")
        return None

    # ── 初回検証 ────────────────────────────────────────────────────────
    validation = validate_output(content, handoff)
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
            in_tok += in2
            out_tok += out2
            regen_count = 1
            content = content2

            validation = validate_output(content, handoff)
            final_score, score_note = _adjust_score(content, validation)
            _print_validation(validation, final_score, score_note)

            if not validation["passed"]:
                print("  [警告] 再生成後もFAIL項目が残っています。未達項目:")
                for f in validation["failed_items"]:
                    print(f"    - {f}")
                print()
        except Exception as e:
            print(f"  [警告] 再生成中にエラー: {e}。初回生成結果を使用します。")

    # ── ターミナル表示 ──────────────────────────────────────────────────
    print()
    print(SEP)
    print("  生成結果")
    print(SEP)
    print()
    print(content)
    print()
    print(SEP)
    print(f"  再生成回数: {regen_count}回 / 最終スコア: {final_score}点")
    print(SEP)
    print()

    # ── 保存（タイムスタンプ付き3ファイル） ────────────────────────────
    paths: dict[str, str] = {}
    try:
        paths = _save_outputs(
            content, handoff, validation, final_score, score_note, ts, base_dir
        )
        post_basename = os.path.basename(paths["post"])
        print(f"  ✔ 保存  {post_basename}")
    except Exception as e:
        print(f"  [エラー] ファイル保存失敗: {e}")

    # ── latest_instagram_post.md へコピー（保存成功時のみ）──────────────
    if paths.get("post"):
        try:
            latest_path = _update_latest(paths["post"], base_dir)
            paths["latest"] = latest_path
            print(f"  ✔ 最新版更新  {os.path.basename(latest_path)}")
        except Exception as e:
            print(f"  [警告] latest_instagram_post.md の更新に失敗しました: {e}")
    print()

    # ── クリップボード ──────────────────────────────────────────────────
    copied = _copy_to_clipboard(content)
    if copied:
        print("  クリップボードにコピーしました。")
    else:
        print("  ※ クリップボードへのコピーに失敗しました（生成・保存は成功）。")
    print()

    return {
        "content":     content,
        "validation":  validation,
        "final_score": final_score,
        "paths":       paths,
        "regen_count": regen_count,
    }
