"""
topic_intelligence.py

Topic Intelligence Engine — Phase 1 コア

毎朝「今日はこれ話したら面白そう」と思えるテーマを提案する。

フロー:
  ① World Context（別モジュール）
  ↓
  ② Observation収集（このモジュール: 現場の気づきを3問で収集）
  ↓
  ③ Topic Candidates生成（このモジュール: World Context × Observation → 5〜8案）
  ↓
  STOP — ユーザーが選択

禁止事項:
  ✗ 投稿文・台本・キャプションを生成する
  ✗ Topic選択前にConversationを開始する
  ✗ 1投稿に複数テーマを混ぜる（Single Story Rule）

残りの未使用テーマは次回のTopic候補として保存される（将来実装）。

【2026-07-03(1回目): 新規作成。Phase1 Goal — Topic Candidates まで生成してSTOP。】
"""

from __future__ import annotations

import sys
import textwrap
from typing import Optional


# ── Phase 1 Observation収集（AIコストゼロ: 固定3問）──────────────────────────

_PHASE1_QUESTIONS = [
    "最近、現場で気になったこと・変わったな、と思ったことは？",
    "最近、お客様に言ったら「え、そうなんですか！」と驚かれたことは？",
    "最近、お客様が誤解していると感じることは？",
]


def collect_observations(
    world_ctx: dict,
    vertical_name: str = "専門家",
    skip_if_no_tty: bool = True,
) -> list:
    """
    専門家から「最近の気づき」を収集する（AIコストゼロ）。

    固定3問を聞く。テーマは決まっていない。自由回答。
    答えた分だけ Observation として保存する。

    Returns:
        [{"type": "Observation"|"Discovery"|"ExpertView", "content": "..."}, ...]
    """
    if skip_if_no_tty and not sys.stdin.isatty():
        return []

    season = world_ctx.get("season", "")
    region = world_ctx.get("region", "")

    print()
    print("=" * 60)
    print("  📝  OBSERVATION — 今日の気づきを聞かせてください")
    print("=" * 60)
    if season:
        loc = f"（{region}・{season}）" if region else f"（{season}）"
        print(f"  {loc}")
    print()
    print("  空Enterでスキップ")
    print("-" * 60)

    observations = []
    type_map = ["Observation", "Discovery", "ExpertView"]

    for i, question in enumerate(_PHASE1_QUESTIONS):
        print()
        wrapped = textwrap.fill(question, width=54, subsequent_indent="      ")
        print(f"  Q{i+1}. {wrapped}")
        try:
            answer = input("  >   ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if answer:
            observations.append({
                "type":    type_map[i],
                "content": answer,
            })

    print()
    if observations:
        print(f"  ✅ {len(observations)}件のObservationを収集しました")
    else:
        print("  （Observationなし — World Contextのみでテーマを生成します）")
    print("=" * 60)

    return observations


# ── Topic Candidates 生成 ─────────────────────────────────────────────────────

def generate_topic_candidates(
    world_ctx: dict,
    observations: list,
    vertical_name: str = "専門家",
) -> list:
    """
    World Context × Observation から Topic候補を生成する（AI 1コール）。

    Returns:
        [{"theme": "...", "stars": 5, "why_now": "...", "who": "...", "why_expert": "..."}, ...]
        失敗時は空リスト。
    """
    region = world_ctx.get("region", "")

    try:
        from openai_analyzer import generate_topic_candidates_ai
        return generate_topic_candidates_ai(
            world_ctx=world_ctx,
            observations=observations,
            vertical_name=vertical_name,
            region=region,
        )
    except Exception as e:
        print(f"  ⚠️ Topic候補生成失敗: {e}")
        return []


# ── 表示 ─────────────────────────────────────────────────────────────────────

def print_topic_candidates(candidates: list) -> None:
    """Topic候補を ★★★★★ 形式で表示する。"""
    W = 60
    THICK = "=" * W
    THIN  = "-" * W

    print()
    print(THICK)
    print("  ③ TOPIC CANDIDATES — 今日話したいテーマ候補")
    print(THICK)

    if not candidates:
        print("\n  （Topic候補を生成できませんでした）")
        print()
        return

    for i, c in enumerate(candidates, 1):
        stars = "★" * c.get("stars", 3) + "☆" * (5 - c.get("stars", 3))
        print()
        print(f"  [{i}] {stars}")
        print(f"      {c['theme']}")
        if c.get("why_now"):
            print(f"      なぜ今: {c['why_now']}")
        if c.get("who"):
            print(f"      誰に:   {c['who']}")
        if c.get("why_expert"):
            print(f"      専門家: {c['why_expert']}")

    print()
    print(THIN)
    print(f"  {len(candidates)}案のテーマ候補を生成しました。")
    print()


# ── ユーザー選択 ─────────────────────────────────────────────────────────────

def select_topic_interactive(
    candidates: list,
    skip_if_no_tty: bool = True,
) -> Optional[dict]:
    """
    ユーザーが Topic候補を選択する。

    非対話環境では None を返す（選択なし = Phase 1完了で終了）。

    Returns:
        選択された候補 dict、またはスキップ時 None
    """
    if not candidates:
        return None

    if skip_if_no_tty and not sys.stdin.isatty():
        return None

    print()
    print("  ① 〜 ⑧ でテーマを選んでください。")
    print("  Enterでスキップ（今日は選択しない）:")

    try:
        choice = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = ""

    if not choice:
        print("  （スキップしました）")
        return None

    # 数字 or 丸数字に対応
    digit = None
    if choice.isdigit():
        digit = int(choice) - 1
    else:
        circled = "①②③④⑤⑥⑦⑧⑨⑩"
        if choice in circled:
            digit = circled.index(choice)

    if digit is not None and 0 <= digit < len(candidates):
        selected = candidates[digit]
        print()
        print(f"  ✅ 選択: 「{selected['theme']}」")
        print()
        return selected

    print(f"  ⚠️ 「{choice}」は認識できませんでした。スキップします。")
    return None
