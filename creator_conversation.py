"""
creator_conversation.py

Creator Conversation Engine

Topicが選ばれてから開始する。

ルール:
  ・質問は3〜5問だけ
  ・回答形式は「選択肢 + 一言入力」を基本にする
  ・30秒以内で答えられる質問だけ
  ・抽象的な質問は禁止
  ・専門家が言っていないことをAIが勝手に作らない（No Hallucination）
  ・情報が足りない場合は追加質問する（投稿を書かない）

禁止:
  ✗ 「最近気になることは？」（抽象すぎる）
  ✗ 「最近驚いたことは？」（抽象すぎる）
  ✗ 「最近増えた相談は？」（抽象すぎる）
  ✗ 専門家が言っていないことを補完・想像して使う

良い質問:
  ○ 「今日最後のお客様は何に悩んでいましたか？」
  ○ 「今日一番多かった悩みは？（選択肢付き）」
  ○ 「今日一番言った言葉は？」
  ○ 「最近『それ違いますよ』と伝えたことは？」
  ○ 「今日なら何をセルフケアとして伝えますか？」

Observation収集はPhase1のtopic_intelligence.pyで完了している。
このConversationはTopicを深掘りする質問（Phase1以降）。

【2026-07-03(1回目): 新規作成。Expert Interview 廃止 → Creator Conversation。】
【2026-07-03(2回目): Observation抽出のみに特化。投稿生成から完全分離。】
【2026-07-04(3回目): Topic選択後の具体質問に完全刷新。選択肢+一言入力方式。】
"""

from __future__ import annotations

import sys
import textwrap
from typing import Optional


def run_creator_conversation(
    selected_topic: dict,
    world_context: dict,
    today: str = "",
    vertical_name: str = "専門家",
    skip_if_no_tty: bool = True,
) -> Optional[dict]:
    """
    Creator Conversation を実行する（Topic選択後）。

    3〜5問の具体的な質問で、専門家の現場経験を深掘りする。
    回答形式: 選択肢 + 一言入力（30秒以内）。

    AIが専門家の発言を補完・想像することは禁止。
    情報が足りない場合は追加質問する。

    Args:
        selected_topic: Topic Candidatesから選ばれたdict（theme/stars/reason等）
        world_context:  今日のWorld Context
        today:          YYYY-MM-DD
        vertical_name:  専門家の表示名

    Returns:
        {
          "topic":        選択テーマ,
          "observations": [{"type": ..., "content": ...}, ...],
          "raw_qa":       [{question, answer, choices_shown}, ...],
          "needs_more":   True/False（情報不足で追加質問が必要か）,
          "date":         today,
        }
        スキップ時は None
    """
    if skip_if_no_tty and not sys.stdin.isatty():
        return None

    theme = selected_topic.get("theme", "（テーマ未設定）")

    from openai_analyzer import generate_topic_deep_questions, extract_observations_only

    print()
    print("=" * 60)
    print("  💬  CREATOR CONVERSATION")
    print("=" * 60)
    print(f"  テーマ: 「{theme}」")
    print()
    print("  このテーマについて3〜5問聞きます。")
    print("  30秒で答えられる質問だけです。")
    print("  空Enterでスキップ（その質問は記録しません）")
    print("-" * 60)

    # Step 1: テーマに沿った具体的な質問を生成（1 OpenAI call）
    print("  質問を準備中...")
    questions = generate_topic_deep_questions(
        topic=selected_topic,
        world_context=world_context,
        vertical_name=vertical_name,
    )

    # Step 2: 選択肢 + 一言入力で会話
    qa_pairs = []
    for i, q_item in enumerate(questions, 1):
        print()
        question = q_item.get("question", "")
        choices  = q_item.get("choices", [])

        wrapped = textwrap.fill(question, width=52, subsequent_indent="      ")
        print(f"  Q{i}. {wrapped}")

        if choices:
            for j, c in enumerate(choices, 1):
                print(f"      {j}. {c}")
            print("      （番号 or 自由入力）")

        try:
            answer = input("  >   ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("  会話を終了しました。")
            break

        if not answer:
            continue

        # 番号入力の場合は選択肢テキストに変換
        display_answer = answer
        if choices and answer.isdigit():
            idx = int(answer) - 1
            if 0 <= idx < len(choices):
                display_answer = choices[idx]

        qa_pairs.append({
            "question":      question,
            "answer":        display_answer,
            "choices_shown": choices,
        })

    answered = len(qa_pairs)
    print()
    print(f"  {answered}問 回答を受け取りました。")

    if answered == 0:
        print("  ⚠️  回答なし。Conversationをスキップします。")
        return None

    # Step 3: ObservationをConversationから抽出（1 OpenAI call）
    # 専門家が言っていないことは絶対に作らない
    print("  Observationを整理中...")
    result = extract_observations_only(qa_pairs)

    obs_list    = result.get("observations", [])
    needs_more  = len(obs_list) == 0 or any(
        o.get("content", "") == "" for o in obs_list
    )

    # 結果表示
    print()
    print("-" * 60)
    print(f"  📍 OBSERVATION — 「{theme}」より")
    print("-" * 60)

    if obs_list:
        for i, obs in enumerate(obs_list, 1):
            t = obs.get("type", "Observation")
            c = obs.get("content", "")
            print(f"\n  [{i}] {t}")
            print(f"    {c}")
    else:
        print("  （Observationが抽出されませんでした — 追加質問が必要です）")

    if needs_more:
        print()
        print("  ⚠️  情報が不足しています。")
        print("  AIは専門家が言っていないことを補完しません。")
        print("  追加情報を教えてください（Enterでスキップ）:")
        try:
            extra = input("  >   ").strip()
            if extra:
                qa_pairs.append({"question": "（追加情報）", "answer": extra, "choices_shown": []})
                result = extract_observations_only(qa_pairs)
                obs_list = result.get("observations", [])
                needs_more = False
        except (EOFError, KeyboardInterrupt):
            pass

    print()
    print("  ✅ Conversation完了。")
    print("=" * 60)
    print()

    return {
        "topic":        theme,
        "observations": obs_list,
        "raw_qa":       qa_pairs,
        "needs_more":   needs_more,
        "date":         today,
    }


def format_observations_for_display(result: dict) -> str:
    """Creator Studio 出力用フォーマット。"""
    if not result:
        return "（Conversation なし）"

    topic    = result.get("topic", "")
    obs_list = result.get("observations", [])

    if not obs_list:
        return f"【CREATOR CONVERSATION「{topic}」— Observation なし】"

    lines = [f"【CREATOR CONVERSATION「{topic}」— Observation × {len(obs_list)}件】"]
    for obs in obs_list:
        t = obs.get("type", "Observation")
        c = obs.get("content", "")
        lines.append(f"  [{t}] {c}")

    qa_count = len([p for p in result.get("raw_qa", []) if p.get("answer")])
    lines.append(f"  （{qa_count}問の会話から収集）")
    return "\n".join(lines)
