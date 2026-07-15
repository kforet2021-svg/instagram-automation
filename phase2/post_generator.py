"""
phase2/post_generator.py

CORE HARI FACE — Phase 2 投稿一式生成

prompt_generator.py が組み立てたプロンプトを OpenAI API に投げ、
①〜⑪の全出力をターミナル表示 + Markdownファイル保存する。

使い方（creator_studio.py から呼ばれる）:
    from phase2.post_generator import run_phase2
    run_phase2(handoff)

【2026-07-15(1回目): 新規作成。Phase2 投稿生成実行モジュール。】
"""

from __future__ import annotations

import datetime
import os
import sys
from typing import Optional


def run_phase2(handoff: dict) -> Optional[str]:
    """
    ChatGPTプロンプトを OpenAI API に送信し、①〜⑪の投稿一式を生成する。

    Args:
        handoff: handoff_to_dict() が返す dict
            {hook, post_type, reality, world_context, topic,
             expert_angles, ref_instagrams}

    Returns:
        生成テキスト（str）。失敗時は None。
        ターミナルへの表示 + outputs/ へのファイル保存も行う。
    """
    # ── プロンプト組み立て ──────────────────────────────────────────────────
    try:
        from phase2.prompt_generator import build_prompt
    except ImportError:
        from prompt_generator import build_prompt

    prompt = build_prompt(handoff)

    # ── OpenAI API 呼び出し ─────────────────────────────────────────────────
    try:
        from openai import OpenAI
        from config import OPENAI_API_KEY
    except ImportError as e:
        print(f"[Phase2] インポートエラー: {e}")
        return None

    if not OPENAI_API_KEY:
        print("[Phase2] OPENAI_API_KEY が設定されていません")
        return None

    print()
    print("=" * 60)
    print("  Phase 2 — 投稿一式生成中（gpt-4o-mini）...")
    print("  ① カルーセル7枚 ② キャプション ③ CTA ④ Threads")
    print("  ⑤ X版 ⑥ 30秒リール ⑦ 60秒リール ⑧ Canvaテキスト")
    print("  ⑨ タイトル5案 ⑩ ハッシュタグ ⑪ AI自己採点")
    print("=" * 60)

    client = OpenAI(api_key=OPENAI_API_KEY)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            timeout=120,
            max_tokens=4000,
        )
        content = response.choices[0].message.content or ""
    except Exception as e:
        print(f"[Phase2] OpenAI APIエラー: {e}")
        return None

    if not content.strip():
        print("[Phase2] 生成結果が空でした")
        return None

    # ── ターミナル表示 ──────────────────────────────────────────────────────
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

    # ── Markdownファイル保存 ────────────────────────────────────────────────
    path = _save_to_file(content, handoff)
    if path:
        print(f"  保存先: {path}")
        print()

    return content


def _save_to_file(content: str, handoff: dict) -> Optional[str]:
    """outputs/instagram_post_YYYYMMDD_HHMMSS.md に保存する。"""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out_dir = os.path.join(base_dir, "outputs")
        os.makedirs(out_dir, exist_ok=True)

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"instagram_post_{ts}.md"
        path = os.path.join(out_dir, filename)

        hook = handoff.get("hook", "")
        post_type = handoff.get("post_type", "")
        topic = handoff.get("topic", "")

        header = (
            f"# CORE HARI FACE — Instagram投稿一式\n\n"
            f"生成日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"**Hook**: {hook}\n\n"
            f"**投稿目的**: {post_type}\n\n"
            f"**Topic**: {topic}\n\n"
            f"---\n\n"
        )

        with open(path, "w", encoding="utf-8") as f:
            f.write(header + content)

        return path
    except Exception as e:
        print(f"[Phase2] ファイル保存エラー: {e}")
        return None
