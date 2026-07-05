"""
topic_intelligence.py

Topic Intelligence Engine — Phase 1 コア

毎朝「今日はこれ話したら面白そう」と思えるテーマを提案する。

フロー:
  ① World Context（別モジュール）
  ↓
  ② Observation収集（このモジュール: 現場の気づきを7分類で収集）
  ↓
  ③ Topic Candidates生成（World Context × Observation × Brand Domain → 5〜10案）
  ↓
  STOP — ユーザーが①〜⑩で選択
  ↓
  Creator Conversation（Topic選択後に開始）

Observation優先比率: Observation 70% / World Context 20% / SNSトレンド 10%

禁止:
  ✗ 投稿文・台本・キャプションを生成する
  ✗ Topic選択前にConversationを開始する
  ✗ 1投稿に複数テーマを混ぜる（Single Story Rule）
  ✗ 他の健康アカウントでも話せるTopicを出す（Brand Filter）

残りの未使用テーマは次回のTopic候補として保存（将来実装）。

【2026-07-03(1回目): 新規作成。Phase1 Goal — Topic Candidates まで生成してSTOP。】
【2026-07-04(2回目): Observation 7分類・Topic reason フィールド・Brand Filter 強化。】
"""

from __future__ import annotations

import sys
import textwrap
from typing import Optional


# ── Observation 7分類 ──────────────────────────────────────────────────────────

OBSERVATION_TYPES = {
    "Pain":          "痛み・悩み（お客様が抱えている悩み・不満）",
    "Misconception": "思い込み（お客様の誤解・間違った認識）",
    "Observation":   "現場の事実（専門家が現場で見た・気づいたこと）",
    "Result":        "変化・結果（施術・セルフケア後の変化）",
    "Method":        "セルフケア（自分でできるケア・方法）",
    "Product":       "商品・道具（使っているもの・おすすめ）",
    "Trend":         "世界の流れ（業界・社会のトレンド）",
}

_TYPE_LABELS = list(OBSERVATION_TYPES.keys())  # 選択番号の順番
_TYPE_DISPLAY = {k: f"{k}（{v.split('（')[0].rstrip('（')}）" for k, v in OBSERVATION_TYPES.items()}


# ── Observation 収集（固定3問 + 分類）────────────────────────────────────────

_PHASE1_QUESTIONS = [
    "今日、印象に残ったお客様の悩みや言葉は？",
    "最近「それ違いますよ」と伝えたことは？",
    "今日なら何をセルフケアとして伝えますか？",
]


def _classify_observation(content: str) -> str:
    """
    Observationを7分類に分類する（AIコストゼロ: ユーザーが選択）。

    Returns: Pain / Misconception / Observation / Result / Method / Product / Trend
    """
    print()
    print("    これはどの分類に近いですか？（Enter でスキップ→Observation）")
    for i, key in enumerate(_TYPE_LABELS, 1):
        desc = OBSERVATION_TYPES[key]
        print(f"      {i}. {key} — {desc}")
    print()

    try:
        choice = input("    > ").strip()
    except (EOFError, KeyboardInterrupt):
        return "Observation"

    if not choice:
        return "Observation"

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(_TYPE_LABELS):
            return _TYPE_LABELS[idx]

    # テキストで入力された場合
    for key in _TYPE_LABELS:
        if choice.lower() in key.lower():
            return key

    return "Observation"


def collect_observations(
    world_ctx: dict,
    vertical_name: str = "専門家",
    skip_if_no_tty: bool = True,
) -> list:
    """
    専門家から「今日の気づき」を収集し、7分類で分類する（AIコストゼロ）。

    3問を聞き、各回答を Pain/Misconception/Observation/Result/Method/Product/Trend に分類。
    分類不明の場合はユーザーが選択。

    Returns:
        [{"type": "Pain|Misconception|...", "content": "..."}, ...]
    """
    if skip_if_no_tty and not sys.stdin.isatty():
        return []

    season = world_ctx.get("season", "")
    region = world_ctx.get("region", "")

    print()
    print("=" * 60)
    print("  📝  OBSERVATION ENGINE")
    print("=" * 60)
    if season or region:
        loc = f"{region}・{season}" if region and season else (region or season)
        print(f"  {loc}")
    print()
    print("  今日の気づきを教えてください。")
    print("  空Enterでスキップ")
    print("-" * 60)

    observations = []

    for i, question in enumerate(_PHASE1_QUESTIONS):
        print()
        wrapped = textwrap.fill(question, width=52, subsequent_indent="      ")
        print(f"  Q{i+1}. {wrapped}")
        try:
            answer = input("  >   ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not answer:
            continue

        # 分類
        obs_type = _classify_observation(answer)
        observations.append({
            "type":    obs_type,
            "content": answer,
        })
        print(f"    → [{obs_type}] として保存しました")

    print()
    if observations:
        print(f"  ✅ {len(observations)}件のObservationを収集しました")
        for o in observations:
            print(f"    [{o['type']}] {o['content'][:40]}")
    else:
        print("  （Observationなし — World Contextのみでテーマを生成します）")
    print("=" * 60)

    return observations


# ── Topic Candidates 生成 ─────────────────────────────────────────────────────

def generate_topic_candidates(
    world_ctx: dict,
    observations: list,
    vertical_name: str = "専門家",
    brand_domain: str = "",
    off_brand_topics: list = None,
) -> list:
    """
    World Context × Observation × Brand Domain から Topic候補を生成する（AI 1コール）。

    優先比率: Observation 70% / World Context 20% / SNSトレンド 10%
    Brand Filter: 他の健康アカウントでも話せる内容は却下。

    Returns:
        [{"theme": "...", "stars": 5, "reason": "X×Y", "why_now": "...",
          "who": "...", "why_expert": "..."}, ...]
    """
    region = world_ctx.get("region", "")

    try:
        from openai_analyzer import generate_topic_candidates_ai
        return generate_topic_candidates_ai(
            world_ctx=world_ctx,
            observations=observations,
            vertical_name=vertical_name,
            region=region,
            brand_domain=brand_domain,
            off_brand_topics=off_brand_topics or [],
        )
    except Exception as e:
        print(f"  ⚠️ Topic候補生成失敗: {e}")
        return []


# ── 表示 ─────────────────────────────────────────────────────────────────────

def print_topic_candidates(candidates: list) -> None:
    """Topic候補を ★★★★★ + 理由（X×Y）形式で表示する。"""
    W = 60

    print()
    print("=" * W)
    print("  ③ TOPIC CANDIDATES — 今日話したいテーマ候補")
    print("=" * W)

    if not candidates:
        print("\n  （Topic候補を生成できませんでした）")
        print()
        return

    for i, c in enumerate(candidates, 1):
        stars_n = c.get("stars", 3)
        stars   = "★" * stars_n + "☆" * (5 - stars_n)
        print()
        print(f"  [{i}] {stars}")
        print(f"      {c['theme']}")
        if c.get("reason"):
            print(f"      理由: {c['reason']}")
        if c.get("why_now"):
            print(f"      なぜ今: {c['why_now']}")
        if c.get("who"):
            print(f"      誰に:   {c['who']}")
        if c.get("why_expert"):
            print(f"      専門家: {c['why_expert']}")

    print()
    print("-" * W)
    print(f"  {len(candidates)}案のテーマ候補を生成しました。")
    print()


# ── ユーザー選択 ─────────────────────────────────────────────────────────────

def select_topic_interactive(
    candidates: list,
    skip_if_no_tty: bool = True,
) -> Optional[dict]:
    """
    ユーザーが Topic候補を選択する。

    数字（1〜10）または丸数字（①〜⑩）で入力。
    Enterでスキップ。

    Returns:
        選択された候補 dict、またはスキップ時 None
    """
    if not candidates:
        return None

    if skip_if_no_tty and not sys.stdin.isatty():
        return None

    print()
    print("  番号でテーマを選んでください（Enter でスキップ）:")

    try:
        choice = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = ""

    if not choice:
        print("  （スキップしました — 今日はここまで）")
        return None

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
        if selected.get("reason"):
            print(f"     理由: {selected['reason']}")
        print()
        print("  次: Creator Conversation（3〜5問）を開始します")
        print()
        return selected

    print(f"  ⚠️ 「{choice}」は認識できませんでした。スキップします。")
    return None
