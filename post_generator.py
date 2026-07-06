"""
post_generator.py

Phase 2 — 投稿生成エンジン

フロー:
  Phase 1 で選んだ Hook
  ↓
  投稿目的を選択（保存・共感・信頼・行動・予約）
  ↓
  投稿を生成（Instagram スライド + キャプション）

設計方針:
  ・セルフケア中心。施術を前提とした構成は禁止。
  ・読んだ人が「今日からやってみよう」と思える内容を優先。
  ・信頼を積み重ねた結果として予約につながる設計。
  ・森このみ本人が話しているような自然な言葉。
  ・CORE HARI 独自の視点・現場の観察を必ず反映。

【2026-07-06(1回目): 新規作成。Phase 2 投稿生成。】
"""

from __future__ import annotations

import sys
from typing import Optional

# ── 投稿タイプ定義 ────────────────────────────────────────────────────────────

POST_TYPES = [
    ("保存",  "役立つ情報・セルフケア手順・リスト（保存して何度も見返せる）"),
    ("共感",  "「わかる」「これ私だ」と感じる悩み・あるある・観察"),
    ("信頼",  "専門家だから見える事実・現場の観察・CORE HARI 独自の視点"),
    ("行動",  "今すぐやってみたくなるセルフケア・チェック（今日から始められる）"),
    ("予約",  "信頼の積み重ねから自然に予約を促す（押しつけなし）"),
]


def select_post_type(skip_if_no_tty: bool = True) -> Optional[str]:
    """
    投稿目的をユーザーが選択する。

    Returns: "保存" / "共感" / "信頼" / "行動" / "予約" / None
    """
    if skip_if_no_tty and not sys.stdin.isatty():
        return None

    print()
    print("=" * 60)
    print("  Phase 2 — 投稿生成")
    print("  投稿の目的を選んでください")
    print("=" * 60)
    print()
    for i, (name, desc) in enumerate(POST_TYPES, 1):
        print(f"  [{i}] {name}")
        print(f"       {desc}")
        print()
    print("  Enter でスキップ（投稿生成なし）")
    print("-" * 60)

    try:
        choice = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        return None

    if not choice:
        return None

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(POST_TYPES):
            return POST_TYPES[idx][0]

    for name, _ in POST_TYPES:
        if choice == name or choice in name:
            return name

    return None


def generate_post(
    hook_dict: dict,
    post_type: str,
    world_ctx: dict,
    reality: Optional[dict] = None,
    vertical_name: str = "専門家",
    skip_if_no_tty: bool = True,
) -> Optional[dict]:
    """
    選んだ Hook × 投稿目的 → Instagram 投稿を生成する（AI 1コール）。

    Returns:
        {
          "hook":      選択したHook文,
          "post_type": 投稿目的,
          "slides":    [{"slide": 1, "text": "..."}, ...],
          "caption":   キャプション文,
          "notes":     投稿時の注意点（任意）,
        }
        失敗時は None
    """
    hook = hook_dict.get("hook") or hook_dict.get("theme", "")
    perspective = hook_dict.get("perspective", "")
    angle = hook_dict.get("angle", "")

    reality_text = ""
    if reality:
        reality_text = (
            f"【リアリティ補強（実際の観察・体験）】\n"
            f"  [{reality.get('type', '')}] {reality.get('content', '')}\n\n"
        )

    print()
    print(f"  投稿を生成中... （{post_type}型）")

    try:
        from openai_analyzer import generate_phase2_post
        result = generate_phase2_post(
            hook=hook,
            perspective=perspective,
            angle=angle,
            post_type=post_type,
            world_ctx=world_ctx,
            reality_text=reality_text,
            vertical_name=vertical_name,
        )
        result["hook"]      = hook
        result["post_type"] = post_type
        return result
    except Exception as e:
        print(f"  ⚠️ 投稿生成失敗: {e}")
        return None


def print_post(post: dict) -> None:
    """生成された投稿を表示する。"""
    if not post:
        print("  （投稿なし）")
        return

    W = 60
    print()
    print("=" * W)
    print(f"  Phase 2 — 生成された投稿（{post.get('post_type', '')}型）")
    print("=" * W)
    print(f"\n  Hook: 「{post.get('hook', '')}」")
    print()

    slides = post.get("slides", [])
    if slides:
        print("  ─── スライド ───────────────────────────────────────")
        for s in slides:
            n    = s.get("slide", "")
            text = s.get("text", "")
            print()
            print(f"  【スライド {n}】")
            for line in text.splitlines():
                print(f"    {line}")

    caption = post.get("caption", "")
    if caption:
        print()
        print("  ─── キャプション ──────────────────────────────────")
        print()
        for line in caption.splitlines():
            print(f"  {line}")

    notes = post.get("notes", "")
    if notes:
        print()
        print("  ─── 投稿メモ ──────────────────────────────────────")
        print(f"  {notes}")

    print()
    print("=" * W)
    print()
