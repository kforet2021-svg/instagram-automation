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


# ── Observation ソース定義 ────────────────────────────────────────────────────

# (label, question)
OBSERVATION_SOURCES = [
    ("お客様との会話",   "今日のお客様で印象に残った悩みや言葉は？"),
    ("自分自身の気付き", "最近「これ、投稿したい」と思った自分の気付きは？"),
    ("SNSコメント",      "最近SNSのコメントで気になった言葉や反応は？"),
    ("DM",               "最近のDMで印象に残ったメッセージは？"),
    ("家族との会話",     "家族との会話で「これ、みんな知らないかも」と思ったことは？"),
    ("街で見たこと",     "最近、街や日常で気になった顔・表情・姿勢は？"),
    ("ニュース",         "最近のニュースで「顔・体・美容」に関係するものは？"),
    ("Instagram",        "最近Instagramで見て「これ投稿したい」と思った投稿や反応は？"),
    ("Threads",          "最近Threadsで気になった投稿や会話は？"),
    ("本・雑誌",         "最近読んで「これ面白い」と思ったことは？"),
    ("YouTube",          "最近YouTubeで見て気になった内容は？"),
    ("セミナー・勉強会", "最近のセミナーや勉強会で印象に残ったことは？"),
    ("失敗談",           "最近「あ、これ失敗した」と思ったことは？（顔・ケア・伝え方）"),
    ("成功事例",         "最近「これ効いた！」と思ったこと（施術・伝え方・投稿）は？"),
]

_SOURCE_LABELS = [s[0] for s in OBSERVATION_SOURCES]


def _select_source() -> tuple[str, str]:
    """
    「今日はどこからネタを探しますか？」を聞いてソースを選ぶ。

    Returns: (source_label, question_text)
    """
    print()
    print("  今日はどこからネタを探しますか？（番号で選択）")
    print()
    for i, (label, _) in enumerate(OBSERVATION_SOURCES, 1):
        print(f"    {i:2}. {label}")
    print()

    try:
        choice = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        return OBSERVATION_SOURCES[0]  # デフォルト: お客様

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(OBSERVATION_SOURCES):
            return OBSERVATION_SOURCES[idx]

    # テキスト部分一致
    for src in OBSERVATION_SOURCES:
        if choice in src[0]:
            return src

    return OBSERVATION_SOURCES[0]


# ── Observation 収集 ──────────────────────────────────────────────────────────

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


def _ask_one_observation(question: str, source_label: str, idx: int) -> Optional[dict]:
    """1問聞いて Observation dict を返す。スキップ or 空なら None。"""
    print()
    wrapped = textwrap.fill(question, width=52, subsequent_indent="      ")
    print(f"  Q{idx}. {wrapped}")
    try:
        answer = input("  >   ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not answer or _is_empty_observation(answer):
        return None
    obs_type = _classify_observation(answer)
    print(f"    → [{obs_type}] として保存しました")
    return {"type": obs_type, "content": answer, "source": source_label}


def collect_observations(
    world_ctx: dict,
    vertical_name: str = "専門家",
    skip_if_no_tty: bool = True,
) -> list:
    """
    「今日はどこからネタを探しますか？」→ ソース選択 → Observation収集。

    Observationが取れなければ別ソースに切り替えを促す。
    各Observationを 7分類（Pain/Misconception/…）に分類する（AIコストゼロ）。

    Returns:
        [{"type": "...", "content": "...", "source": "..."}, ...]
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
    print("  空Enterでスキップ")
    print("-" * 60)

    observations = []
    tried_sources: set[str] = set()

    while True:
        # ── ソース選択 ──
        source_label, main_question = _select_source()
        tried_sources.add(source_label)
        print(f"\n  ✏️  ソース: {source_label}")
        print("-" * 60)

        # ── メイン質問（ソース固有） ──
        obs = _ask_one_observation(main_question, source_label, 1)
        if obs:
            observations.append(obs)

        # ── 追加質問2問（汎用：なぜ気になった・どう使える） ──
        if obs:
            follow_ups = [
                "それを見たとき「なぜ？」と思ったことは？（空Enterでスキップ）",
                "これをお客様に伝えるとしたら、どんな言葉で伝えますか？（空Enterでスキップ）",
            ]
            for j, fq in enumerate(follow_ups, 2):
                fo = _ask_one_observation(fq, source_label, j)
                if fo:
                    observations.append(fo)

        # ── 収集できたか確認 ──
        if observations:
            break

        # ── 取れなかった → 別ソースへ誘導 ──
        print()
        print("  （このソースからはObservationを取得できませんでした）")
        remaining = [s[0] for s in OBSERVATION_SOURCES if s[0] not in tried_sources]
        if not remaining:
            print("  すべてのソースを試しました。Observationなしで続行します。")
            break
        print("  別のソースに変更しますか？（Enter で続ける / n で終了）")
        try:
            cont = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if cont == "n":
            break
        # ループして再度ソース選択

    print()
    if observations:
        print(f"  ✅ {len(observations)}件のObservationを収集しました")
        for o in observations:
            src = o.get("source", "")
            print(f"    [{o['type']}|{src}] {o['content'][:40]}")
    else:
        print("  （Observationなし）")
    print("=" * 60)

    return observations


# ── Hook候補生成 ─────────────────────────────────────────────────────────────

_SKIP_PHRASES = {"特になし", "なし", "特に無し", "なし。", "ない", ""}


def _is_empty_observation(content: str) -> bool:
    return content.strip() in _SKIP_PHRASES


def generate_topic_candidates(
    world_ctx: dict,
    observations: list = None,
    vertical_name: str = "専門家",
    brand_domain: str = "",
    off_brand_topics: list = None,
    past_obs_library: str = "",
    skip_if_no_tty: bool = True,
) -> list:
    """
    Instagram/Threadsトレンド × World Context → Hook候補10案（AI 1コール）。

    Observationは任意（リアリティ補強として参照するが、なくても生成する）。
    past_obs_library: 過去Observationの要約テキスト（任意）。
    """
    region = world_ctx.get("region", "")
    obs = [o for o in (observations or []) if not _is_empty_observation(o.get("content", ""))]

    try:
        from openai_analyzer import generate_topic_candidates_ai
        return generate_topic_candidates_ai(
            world_ctx=world_ctx,
            observations=obs,
            vertical_name=vertical_name,
            region=region,
            brand_domain=brand_domain,
            off_brand_topics=off_brand_topics or [],
            past_obs_library=past_obs_library,
        )
    except Exception as e:
        print(f"  ⚠️ Hook候補生成失敗: {e}")
        return []


# ── Hook選択後のリアリティ追加 ───────────────────────────────────────────────

def ask_hook_reality(
    selected: dict,
    skip_if_no_tty: bool = True,
) -> Optional[dict]:
    """
    Hookを選んだ後に「リアリティを加える実例」を任意で聞く。

    Observationの役割: テーマ探しではなく投稿にリアリティを加えること。
    回答がなくても投稿は作れる（完全任意）。

    Returns:
        {"content": "...", "source": "...", "type": "..."} | None
    """
    if skip_if_no_tty and not sys.stdin.isatty():
        return None

    hook = selected.get("hook") or selected.get("theme", "")
    print()
    print("  ──────────────────────────────────────────────────────────")
    print("  このHookに関係する最近の出来事や実例があれば教えてください。")
    print(f"  （「{hook}」）")
    print()
    print("  例: お客様の言葉・自分の体験・SNSで見たこと・本で読んだこと")
    print("  空Enterでスキップ（なくても投稿できます）")
    print()

    try:
        answer = input("  >   ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    if not answer or _is_empty_observation(answer):
        print("  （スキップ — リアリティなしで続行します）")
        print("  ──────────────────────────────────────────────────────────")
        return None

    obs_type = _classify_observation(answer)
    print(f"    → [{obs_type}] として保存しました")
    print("  ──────────────────────────────────────────────────────────")
    return {"type": obs_type, "content": answer, "source": "hook_reality"}


# ── 表示 ─────────────────────────────────────────────────────────────────────

_POST_TYPE_ICON = {
    "保存":    "📌 保存",
    "共感":    "💬 共感",
    "信頼":    "🔍 信頼",
    "行動":    "✋ 行動",
    "Threads": "🧵 Threads",
}


def print_topic_candidates(candidates: list) -> None:
    """Phase 1 出力。毎朝3分で「今日はこれにしよう」と選べる表示。"""
    W = 60

    print()
    print("=" * W)
    print("  今日のHook候補")
    print("  ─ Instagram 1枚目 / Threads 1行目 ─")
    print("=" * W)

    if not candidates:
        print("\n  （Hook候補を生成できませんでした）")
        print()
        return

    for i, c in enumerate(candidates, 1):
        hook      = c.get("hook") or c.get("theme", "")
        perspective = c.get("perspective", "")
        angle       = c.get("angle", "")
        post_type   = c.get("post_type", "共感")
        icon        = _POST_TYPE_ICON.get(post_type, post_type)
        reason      = c.get("reason", "")
        print()
        tags = "  ".join(filter(None, [
            f"[{perspective}]" if perspective else "",
            f"[{angle}]"       if angle       else "",
        ]))
        print(f"  [{i:2}]  {icon}  {tags}")
        print(f"        「{hook}」")
        if reason:
            import textwrap as _tw
            for line in _tw.wrap(reason, width=46):
                print(f"         {line}")

    print()
    print("=" * W)
    print(f"  番号を入力して「今日のHook」を選んでください")
    print("=" * W)
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
        hook = selected.get("hook") or selected.get("theme", "")
        print()
        print(f"  ✅ 選択: 「{hook}」")
        print()
        return selected

    print(f"  ⚠️ 「{choice}」は認識できませんでした。スキップします。")
    return None
