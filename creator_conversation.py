"""
creator_conversation.py

Creator Conversation Engine
専門家とAIが「雑談」する。インタビューではない。

AIは質問しない。会話する。
目的は「知識を集めること」ではなく「専門家の観察・感覚・口ぐせを引き出すこと」。

収集優先順位:
  1位 Observation  — 専門家が繰り返し気づいていること（最も価値ある資産）
  2位 口ぐせ       — 専門家が自然に使う言葉
  3位 思い込み     — クライアントがよく持つ誤解
  4位 Expert Thinking — 専門家がどう考えるか

禁止事項:
  ✗ 「○○とは？」「○○について教えてください」（教科書質問）
  ✗ 知識・理論を問う質問
  ✗ 「はい/いいえ」で答えられる質問
  → 専門家がお客様に話しかけるように質問する

【2026-07-03(1回目): 新規作成。Expert Interview 廃止 → Creator Conversation。】
"""

from __future__ import annotations

import sys
import textwrap
from typing import Optional


def run_creator_conversation(
    world_context: dict,
    today: str = "",
    vertical_name: str = "専門家",
    skip_if_no_tty: bool = True,
) -> Optional[dict]:
    """
    Creator Conversation を実行する。

    World Context（季節・社会状況）を踏まえた会話質問で
    専門家の「今のObservation」を引き出す。

    Args:
        world_context:  world_context.get_world_context() の出力
        today:          実行日（YYYY-MM-DD）
        vertical_name:  専門家の肩書き（表示用）
        skip_if_no_tty: 非対話環境では自動スキップしてNoneを返す

    Returns:
        dict with keys: observations, 口ぐせ, 思い込み, expert_thinking,
                        speaker_words, raw_qa
        スキップ時は None
    """
    if skip_if_no_tty and not sys.stdin.isatty():
        print("  ℹ️  非対話環境のため Creator Conversation をスキップします")
        return None

    from openai_analyzer import generate_conversation_questions, extract_conversation_insights

    season    = world_context.get("season", "")
    hot_topic = world_context.get("hot_tension", "")

    print()
    print("=" * 60)
    print("   💬  CREATOR CONVERSATION")
    print("=" * 60)
    print(f"  {vertical_name}と雑談します。")
    print(f"  今の季節: {season}  / 注目: {hot_topic[:30] if hot_topic else '（なし）'}")
    print()
    print("  知識より「最近気づいたこと」「よく言う言葉」を教えてください。")
    print("  空Enterでスキップ（その質問は記録しません）")
    print("-" * 60)

    # Step 1: World Context を踏まえた会話質問を生成（1 OpenAI call）
    print("  質問を準備中...")
    questions = generate_conversation_questions(world_context, vertical_name)

    # Step 2: 会話
    qa_pairs = []
    for i, question in enumerate(questions, 1):
        print()
        wrapped = textwrap.fill(question, width=54, subsequent_indent="      ")
        print(f"  Q{i:02d}. {wrapped}")
        try:
            answer = input("  >   ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("  会話を終了しました。")
            break
        if answer:
            qa_pairs.append({"question": question, "answer": answer})

    answered = len(qa_pairs)
    print()
    print(f"  {answered}問 回答を受け取りました。")

    if answered == 0:
        print("  ⚠️  回答なし。Thought Libraryのみで生成します。")
        return None

    # Step 3: Observation・思考を抽出（1 OpenAI call）
    print("  Observationを抽出中...")
    insights = extract_conversation_insights(qa_pairs)

    # 結果サマリー
    print()
    print("-" * 60)
    print("  📋 収集した専門家の思考")
    print("-" * 60)

    obs_list = insights.get("observations", [])
    if obs_list:
        print(f"  [Observation × {len(obs_list)}件]")
        for obs in obs_list[:3]:
            print(f"    ・{obs[:70]}")

    if insights.get("口ぐせ"):
        print(f"  [口ぐせ] {insights['口ぐせ'][:60]}")

    if insights.get("思い込み"):
        print(f"  [思い込み] {insights['思い込み'][:60]}")

    if insights.get("expert_thinking"):
        print(f"  [専門家の思考] {insights['expert_thinking'][:60]}")

    print("=" * 60)
    print()

    return insights


def format_conversation_for_display(insights: dict) -> str:
    """Creator Studio 出力用フォーマット。"""
    lines = ["【CREATOR CONVERSATION — 専門家の思考】"]

    obs_list = insights.get("observations", [])
    if obs_list:
        lines.append(f"  Observation（{len(obs_list)}件）:")
        for obs in obs_list:
            lines.append(f"    ・{obs}")

    if insights.get("口ぐせ"):
        lines.append(f"  口ぐせ    : {insights['口ぐせ']}")

    if insights.get("思い込み"):
        lines.append(f"  思い込み  : {insights['思い込み']}")

    if insights.get("expert_thinking"):
        lines.append(f"  専門家の思考: {insights['expert_thinking']}")

    answered = len([p for p in insights.get("raw_qa", []) if p.get("answer")])
    lines.append(f"  （{answered}問の会話から収集）")
    return "\n".join(lines)
