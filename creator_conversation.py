"""
creator_conversation.py

Creator Conversation Engine
専門家とAIが「雑談」する。インタビューではない。

Conversation終了後は投稿を生成しない。
Observationだけを抽出して保存する。

Observationとは:
  ・専門家が最近気付いたこと
  ・専門家が最近驚いたこと
  ・専門家だけが見ていること

Conversationで出てきた内容を元テーマへ戻さない。
Conversationの内容が最優先。
投稿生成はObservation完成後、別Engineで行う。

禁止事項:
  ✗ 「○○とは？」「○○について教えてください」（教科書質問）
  ✗ 知識・理論を問う質問
  ✗ 「はい/いいえ」で答えられる質問
  ✗ Conversationの内容を元テーマへ引き戻す
  ✗ Conversationの出力からspeaker_wordsや投稿台本を生成する

【2026-07-03(1回目): 新規作成。Expert Interview 廃止 → Creator Conversation。】
【2026-07-03(2回目): Observation抽出のみに特化。投稿生成から完全分離。】
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

    Conversation終了後はObservationのみを抽出して返す。
    投稿は生成しない。

    Returns:
        {
          "observations": ["...", "..."],   # 専門家の気づき（最重要・複数）
          "raw_qa": [...],                  # 元のQ&A（保存用）
          "date": today,
        }
        スキップ時は None
    """
    if skip_if_no_tty and not sys.stdin.isatty():
        print("  ℹ️  非対話環境のため Creator Conversation をスキップします")
        return None

    from openai_analyzer import generate_conversation_questions, extract_observations_only

    season    = world_context.get("season", "")
    hot_topic = world_context.get("hot_tension", "")

    print()
    print("=" * 60)
    print("   💬  CREATOR CONVERSATION")
    print("=" * 60)
    print(f"  {vertical_name}と雑談します。")
    if season:
        print(f"  今の季節: {season}" + (f"  / {hot_topic[:30]}" if hot_topic else ""))
    print()
    print("  最近気づいたこと・驚いたこと・あなただけが見ていること")
    print("  を教えてください。")
    print("  空Enterでスキップ（その質問は記録しません）")
    print("-" * 60)

    # Step 1: 会話質問を生成（1 OpenAI call）
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
        print("  ⚠️  回答なし。Conversationをスキップします。")
        return None

    # Step 3: Observationだけを抽出（1 OpenAI call）
    # 投稿台本・テーマへの引き戻しは行わない
    print("  Observationを抽出中...")
    result = extract_observations_only(qa_pairs)

    # 結果表示
    print()
    print("-" * 60)
    print("  📍 OBSERVATION（専門家の気づき）")
    print("-" * 60)

    obs_list = result.get("observations", [])
    if obs_list:
        for i, obs in enumerate(obs_list, 1):
            obs_type = obs.get("type", "気づき")
            content  = obs.get("content", "")
            print(f"\n  [{i}] {obs_type}")
            print(f"    {content}")
    else:
        print("  （Observationが抽出されませんでした）")

    print()
    print("  ✅ Observation収集完了。投稿生成は別Engineで行います。")
    print("=" * 60)
    print()

    return {
        "observations": obs_list,
        "raw_qa":       qa_pairs,
        "date":         today,
    }


def format_observations_for_display(result: dict) -> str:
    """Creator Studio 出力用フォーマット。"""
    obs_list = result.get("observations", [])
    if not obs_list:
        return "（Observation なし）"

    lines = [f"【CREATOR CONVERSATION — Observation × {len(obs_list)}件】"]
    for obs in obs_list:
        obs_type = obs.get("type", "気づき")
        content  = obs.get("content", "")
        lines.append(f"  [{obs_type}] {content}")

    qa_count = len([p for p in result.get("raw_qa", []) if p.get("answer")])
    lines.append(f"  （{qa_count}問の会話から収集）")
    return "\n".join(lines)
