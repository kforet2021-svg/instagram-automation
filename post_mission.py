"""
post_mission.py

POST MISSION FIRST
Creator Intelligence が投稿生成を開始する前に「この投稿の目的」を確定する。

ルール:
  - 投稿生成前に必ずMissionを1つ選択する
  - 投稿中にMissionを変更しない
  - 投稿完成後に Mission Achievement Check を実施する
  - Hook / CTA / 構成 / 内容 がすべてMissionと一致しているか確認する
  - 一致しない場合は自動で再生成する

【2026-07-03(1回目): 新規作成。POST MISSION FIRST実装。】
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ── Mission 定義 ─────────────────────────────────────────────────────────────

POST_MISSIONS = {
    "教育": {
        "label":   "教育「知らなかった、ためになった」",
        "purpose": "専門家の知識・観察を届け、読者が「知らなかった」と感じさせる",
        "kpi":     "保存・シェア",
        "hook_rule":    "「なぜ？」「どうして？」「実は〜」を入口にする",
        "cta_rule":     "保存CTAを入れる（「保存して、あとで読み返してください」）",
        "content_rule": "専門家の観察・Observationを具体的に見せる",
        "forbidden":    ["予約はこちら", "施術で解決", "料金"],
        "cta_keywords": ["保存", "あとで", "読み返"],
        "hook_keywords": ["知っていますか", "実は", "なぜ", "理由", "驚き"],
    },
    "共感": {
        "label":   "共感「これ私のことだ」",
        "purpose": "読者が「自分のことを言われている」と感じさせる",
        "kpi":     "コメント・フォロー",
        "hook_rule":    "読者の悩み・状況をそのまま言語化する",
        "cta_rule":     "フォローCTAまたはコメント促進を入れる",
        "content_rule": "「あなたも〜じゃないですか？」の視点で書く",
        "forbidden":    ["一般論", "全員に当てはまる", "〜という方法があります"],
        "cta_keywords": ["フォロー", "コメント", "教えて", "あなた"],
        "hook_keywords": ["方", "あなた", "感じる", "気になる", "ある"],
    },
    "信頼": {
        "label":   "信頼「この人はわかっている」",
        "purpose": "専門家としての観察・判断力を見せ、信頼を構築する",
        "kpi":     "フォロー・予約への橋渡し",
        "hook_rule":    "「私はまず〜を見ます」「私は〜から確認します」で始める",
        "cta_rule":     "フォローCTAまたはプロフィールへの誘導",
        "content_rule": "専門家の思考プロセス・判断軸を見せる。知識より「目線」を開示する",
        "forbidden":    ["一般的に", "と言われています", "研究によると"],
        "cta_keywords": ["フォロー", "プロフィール", "気になった方"],
        "hook_keywords": ["私は", "まず", "確認", "見ます", "わかります"],
    },
    "驚き": {
        "label":   "驚き「え、本当に？」",
        "purpose": "「そんなこと知らなかった」という発見・逆説でシェアを生む",
        "kpi":     "シェア・リポスト・引用",
        "hook_rule":    "逆説・意外な事実・「常識の嘘」で始める",
        "cta_rule":     "シェア促進（「これ、誰かに教えたくなりませんか？」）",
        "content_rule": "「実は〜」「多くの人が知らない〜」「逆に〜」の構造",
        "forbidden":    ["保存してください", "フォローしてください", "予約は"],
        "cta_keywords": ["シェア", "教えて", "知ってた", "送って"],
        "hook_keywords": ["実は", "意外", "知らない", "間違い", "逆に", "え"],
    },
    "行動": {
        "label":   "行動「今日からやってみよう」",
        "purpose": "読者が今日から実践できる具体的なアクションを提供する",
        "kpi":     "保存・予約・問い合わせ",
        "hook_rule":    "「今日から試せる〜」「○○するだけで〜」で具体性を見せる",
        "cta_rule":     "保存CTAまたは体験予約への誘導",
        "content_rule": "「やってみてください」で締める。ステップ・方法を具体的に",
        "forbidden":    ["難しい", "専門家でないとできない", "施術が必要"],
        "cta_keywords": ["保存", "試して", "やってみて", "予約", "体験"],
        "hook_keywords": ["今日", "今すぐ", "やってみる", "試す", "だけで"],
    },
    "予約": {
        "label":   "予約「体験してみたい」",
        "purpose": "体験・施術・相談の予約獲得に直結させる",
        "kpi":     "予約・問い合わせ",
        "hook_rule":    "読者の悩みを具体的に言語化してから「解決できます」を見せる",
        "cta_rule":     "予約・問い合わせCTAを明確に入れる",
        "content_rule": "ビフォーアフター・実績・体験談を入れる。施術内容は補足程度",
        "forbidden":    ["料金は〜円", "キャンペーン中", "期間限定"],
        "cta_keywords": ["予約", "体験", "ご相談", "お問い合わせ", "リンク"],
        "hook_keywords": ["悩み", "解決", "変わった", "効果", "体験"],
    },
}

# デフォルト Mission（CORE HARI はセルフケア教育が中心）
DEFAULT_MISSION = "教育"

# Mission ローテーション（毎日異なるMissionで発信するためのガイド）
MISSION_ROTATION = ["教育", "共感", "信頼", "驚き", "行動", "共感", "教育"]


# ── Mission 選択 ──────────────────────────────────────────────────────────────

def select_mission(
    today: str = "",
    vertical_goal: str = "セルフケア教育",
    auto_rotate: bool = True,
    skip_if_no_tty: bool = True,
) -> str:
    """
    今日の Post Mission を選択する。

    優先順位:
      1. ターミナルで対話的に選択（tty環境）
      2. 曜日ローテーション（auto_rotate=True）
      3. デフォルト（DEFAULT_MISSION）

    Args:
        today:        YYYY-MM-DD
        vertical_goal: アカウントの目的（"セルフケア教育" など）
        auto_rotate:  True なら曜日でローテーション
        skip_if_no_tty: 非対話環境では自動選択

    Returns:
        選択された Mission キー（"教育" / "共感" / "信頼" など）
    """
    import sys

    if not skip_if_no_tty or not sys.stdin.isatty():
        # 非対話環境: ローテーションまたはデフォルト
        return _auto_select_mission(today, vertical_goal, auto_rotate)

    # 対話的選択
    import datetime as _dt
    try:
        dow = _dt.date.fromisoformat(today).weekday()
    except Exception:
        dow = 0
    suggested = MISSION_ROTATION[dow % len(MISSION_ROTATION)]

    print()
    print("=" * 60)
    print("  🎯 POST MISSION を選択してください")
    print("=" * 60)
    print()
    for i, (key, m) in enumerate(POST_MISSIONS.items(), 1):
        mark = "★" if key == suggested else " "
        print(f"  {mark} {i}. {m['label']}")
        print(f"       KPI: {m['kpi']}")
    print()
    print(f"  Enterで推奨（{suggested}）を選択:")

    try:
        choice = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = ""

    if not choice:
        mission = suggested
    elif choice.isdigit():
        idx = int(choice) - 1
        keys = list(POST_MISSIONS.keys())
        mission = keys[idx] if 0 <= idx < len(keys) else suggested
    elif choice in POST_MISSIONS:
        mission = choice
    else:
        mission = suggested

    m = POST_MISSIONS[mission]
    print()
    print(f"  ✅ Mission: {m['label']}")
    print(f"     目的: {m['purpose']}")
    print(f"     KPI:  {m['kpi']}")
    print()

    return mission


def _auto_select_mission(today: str, vertical_goal: str, rotate: bool) -> str:
    """非対話環境での自動Mission選択。"""
    if not rotate:
        return DEFAULT_MISSION

    import datetime as _dt
    try:
        dow = _dt.date.fromisoformat(today).weekday()
    except Exception:
        dow = 0

    mission = MISSION_ROTATION[dow % len(MISSION_ROTATION)]
    print(f"  🎯 Post Mission（自動）: {POST_MISSIONS[mission]['label']}")
    return mission


# ── Mission Achievement Check（AIコストゼロ）────────────────────────────────

@dataclass
class MissionCheckResult:
    """Mission Achievement Check の結果。"""
    mission: str
    hook_pass:     bool
    cta_pass:      bool
    content_pass:  bool
    structure_pass: bool
    all_pass:      bool
    issues: list = field(default_factory=list)
    score: int = 0

    def summary_line(self) -> str:
        icon = "✅" if self.all_pass else "❌"
        return f"{icon} Mission Achievement: {self.score}/100点"


def check_mission_achievement(record: dict, mission: str) -> MissionCheckResult:
    """
    投稿が Mission と一致しているか検証する（AIコストゼロ）。

    Checks:
      - Hook   : フックがMissionのhook_ruleと一致するか
      - CTA    : CTAがMissionのcta_ruleと一致するか
      - Content: 本文にforbiddenが含まれないか
      - Structure: 全体の構成がMissionの目的と一致するか

    Returns:
        MissionCheckResult
    """
    m_def = POST_MISSIONS.get(mission, POST_MISSIONS[DEFAULT_MISSION])

    hook    = record.get("hook", "") + " " + record.get("hook_text", "")
    cta     = record.get("cta", "")
    script  = record.get("script_full", "")
    caption = record.get("caption", "")
    full_text = f"{hook} {cta} {script} {caption}"

    issues = []
    score  = 100

    # ── Hook チェック ───────────────────────────────────────────────
    hook_kws = m_def.get("hook_keywords", [])
    hook_pass = any(kw in hook for kw in hook_kws) if hook_kws else True
    if not hook_pass:
        issues.append(f"Hook: 「{m_def['hook_rule']}」になっていない")
        score -= 25

    # ── CTA チェック ────────────────────────────────────────────────
    cta_kws  = m_def.get("cta_keywords", [])
    cta_pass = any(kw in full_text for kw in cta_kws) if cta_kws else True
    if not cta_pass:
        issues.append(f"CTA: 「{m_def['cta_rule']}」になっていない")
        score -= 25

    # ── Content チェック（forbidden） ────────────────────────────────
    forbidden = m_def.get("forbidden", [])
    content_violations = [f for f in forbidden if f in full_text]
    content_pass = len(content_violations) == 0
    if not content_pass:
        issues.append(f"Content: 禁止表現が含まれている → {content_violations}")
        score -= 25

    # ── Structure チェック（content_rule のキーワード確認）──────────
    content_rule = m_def.get("content_rule", "")
    # content_rule から重要語を抽出して緩やかにチェック
    structure_pass = True
    if mission == "信頼":
        structure_pass = any(kw in full_text for kw in ["私は", "まず", "確認", "見ます"])
        if not structure_pass:
            issues.append("Structure: 専門家の思考（「私はまず〜を見ます」）が見えない")
            score -= 25
    elif mission == "行動":
        structure_pass = any(kw in full_text for kw in ["試して", "やってみて", "今日", "ください"])
        if not structure_pass:
            issues.append("Structure: 具体的なアクション指示がない")
            score -= 25
    elif mission == "共感":
        structure_pass = any(kw in full_text for kw in ["あなた", "方", "感じ", "ませんか"])
        if not structure_pass:
            issues.append("Structure: 読者への直接的な問いかけがない")
            score -= 25

    score = max(0, score)
    all_pass = len(issues) == 0

    return MissionCheckResult(
        mission=mission,
        hook_pass=hook_pass,
        cta_pass=cta_pass,
        content_pass=content_pass,
        structure_pass=structure_pass,
        all_pass=all_pass,
        issues=issues,
        score=score,
    )


def print_mission_achievement_check(result: MissionCheckResult, mission: str) -> None:
    """Mission Achievement Check 結果をターミナルに表示する。"""
    m_def = POST_MISSIONS.get(mission, {})
    W = 60

    print()
    print("=" * W)
    print("  MISSION ACHIEVEMENT CHECK")
    print("=" * W)
    print(f"  Mission: {m_def.get('label', mission)}")
    print(f"  KPI:     {m_def.get('kpi', '')}")
    print("-" * W)

    checks = [
        ("Hook    ", result.hook_pass,      m_def.get("hook_rule", "")),
        ("CTA     ", result.cta_pass,       m_def.get("cta_rule", "")),
        ("Content ", result.content_pass,   m_def.get("content_rule", "")),
        ("Structure", result.structure_pass, "全体の構成がMissionと一致"),
    ]

    for label, passed, rule in checks:
        icon = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {label}: {icon}")
        if rule and not passed:
            print(f"           → {rule}")

    print()
    if result.all_pass:
        print(f"  ✅ MISSION ACHIEVED（{result.score}/100点）")
    else:
        print(f"  ❌ MISSION NOT ACHIEVED（{result.score}/100点）")
        for issue in result.issues:
            print(f"     ・{issue}")
        print("  → 自動で再生成します")

    print("=" * W)
    print()


def apply_mission_to_record(record: dict, mission: str) -> dict:
    """
    record に Mission 情報を付加する。
    生成後のチェック・表示に使う。
    """
    record["_post_mission"] = mission
    record["_mission_def"]  = POST_MISSIONS.get(mission, {})
    return record


def get_mission_hint(mission: str) -> str:
    """
    プロンプト生成時に使う Mission ヒント文字列を返す。
    AI生成関数に渡してMission-Firstな投稿を作らせる。
    """
    m = POST_MISSIONS.get(mission, {})
    return (
        f"この投稿のMission: {m.get('label', mission)}\n"
        f"目的: {m.get('purpose', '')}\n"
        f"Hook のルール: {m.get('hook_rule', '')}\n"
        f"CTA のルール: {m.get('cta_rule', '')}\n"
        f"内容のルール: {m.get('content_rule', '')}\n"
        f"禁止: {', '.join(m.get('forbidden', []))}"
    )
