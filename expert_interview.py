"""
expert_interview.py

Creator Intelligence Platform — Expert Interview Engine.

専門家の思考を「インタビュー形式」で引き出すモジュール。
テーマから投稿を作るのではなく、専門家との会話から投稿を生成する。

Creator Intelligence は知識生成 AI ではなく専門家インタビュー AI です。

# 使い方
  from expert_interview import run_expert_interview
  result = run_expert_interview(theme="フェイスラインと姿勢", today="2026-07-02")
  # result: {"observation": ..., "question": ..., "perspective": ..., "speaker_words": ..., "raw_qa": [...]}

【2026-07-02(1回目): 新規作成。投稿生成前のインタビューフロー実装。】
"""

from __future__ import annotations

import sys
import textwrap
from typing import Optional


def run_expert_interview(
    theme: str,
    today: str = "",
    vertical_name: str = "専門家",
    skip_if_no_tty: bool = True,
) -> Optional[dict]:
    """
    インタビューを実行し、抽出した思考（Observation/Question/Perspective）を返す。

    Args:
        theme:          今日のテーマ（Editorial Meeting から渡す）
        today:          実行日（ログ用）
        vertical_name:  専門家の肩書き（表示用）
        skip_if_no_tty: 非対話環境（CI / cron）では自動スキップしてNoneを返す

    Returns:
        dict with keys: observation, question, perspective, speaker_words, raw_qa
        スキップ時は None
    """
    if skip_if_no_tty and not sys.stdin.isatty():
        print("  ℹ️  非対話環境のため Expert Interview をスキップします")
        return None

    from openai_analyzer import generate_interview_questions, extract_interview_insights

    print()
    print("=" * 60)
    print("   🎙️  EXPERT INTERVIEW")
    print("=" * 60)
    print(f"  テーマ: 「{theme}」")
    print(f"  日付:   {today}")
    print()
    print("  Conversation Interview: 専門家の「会話」を集めます。")
    print("  知識より口癖・感覚・現場の一言を聞かせてください。")
    print("  空Enterでスキップ（その質問は記録しません）")
    print("-" * 60)

    # Step 1: 質問生成（1 OpenAI call）
    print("  質問を生成中...")
    questions = generate_interview_questions(theme, vertical_name)

    # Step 2: インタラクティブ Q&A
    qa_pairs = []
    for i, question in enumerate(questions, 1):
        print()
        wrapped = textwrap.fill(question, width=54, subsequent_indent="     ")
        print(f"  Q{i:02d}. {wrapped}")
        try:
            answer = input("  A>  ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("  インタビューを中断しました。")
            break
        if answer:
            qa_pairs.append({"question": question, "answer": answer})

    answered = len(qa_pairs)
    print()
    print(f"  {answered}問 回答を受け取りました。")

    if answered == 0:
        print("  ⚠️  回答がありませんでした。Thought Libraryのみで投稿を生成します。")
        return None

    # Step 3: 思考抽出（1 OpenAI call）
    print("  思考を抽出中...")
    insights = extract_interview_insights(qa_pairs)

    # 結果サマリー表示
    print()
    print("-" * 60)
    print("  📋 抽出された思考")
    print("-" * 60)
    if insights.get("observation"):
        print(f"  [Observation] {insights['observation'][:80]}...")
    if insights.get("question"):
        print(f"  [Question]    {insights['question'][:80]}")
    if insights.get("perspective"):
        print(f"  [Perspective] {insights['perspective'][:80]}...")
    if insights.get("speaker_words"):
        first_line = insights["speaker_words"].split("\n")[0]
        print(f"  [台本冒頭]    {first_line[:80]}")
    print("=" * 60)
    print()

    return insights


def format_interview_for_display(insights: dict) -> str:
    """Creator Studio 出力用のインタビュー結果フォーマット。"""
    lines = ["【EXPERT INTERVIEW — 抽出思考】"]
    if insights.get("observation"):
        lines.append(f"  Observation : {insights['observation']}")
    if insights.get("question"):
        lines.append(f"  Question    : {insights['question']}")
    if insights.get("perspective"):
        lines.append(f"  Perspective : {insights['perspective']}")
    answered = len([p for p in insights.get("raw_qa", []) if p.get("answer")])
    lines.append(f"  （{answered}問のインタビューから抽出）")
    return "\n".join(lines)
