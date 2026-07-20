"""
claims_check.py
===============
投稿本文中の主張（Claim）を FACT / INSIGHT / HYPOTHESIS に分類し、
根拠なし因果表現の検出・言い換え提案を行う。

主な公開API:
  run_claims_check(record, data_mode) -> dict
  format_claims_report(result) -> str

data_mode:
  "LIVE_INSTAGRAM"      — 今日のInstagram取得データあり
  "PAST_INSTAGRAM"      — 過去取得データを参照
  "FALLBACK_NO_INSTAGRAM" — Instagram取得0件（因果表現の根拠制限が最も厳しい）

分類:
  FACT        — Evidence Registryまたは生理学的定説で裏付けあり
  INSIGHT     — 専門家の観察・解釈として妥当、断定ではない
  HYPOTHESIS  — 根拠が確認できない推論・因果断定（投稿では観察表現へ弱める）

【2026-07-21: 新規作成】
"""

from __future__ import annotations
import re
from typing import NamedTuple

# ── FACT として認められる主張パターン ─────────────────────────────────────────
# 生理学的に広く認められており、投稿で断定してよい内容。
# (keyword_pattern, evidence_id, description, scope_note)
_FACT_PATTERNS: list[tuple[str, str, str, str]] = [
    ("表情筋.*約60", "PHYS-001", "顔の表情筋は約60種類以上存在する", "解剖学的定説"),
    ("咬筋.*左右差|左右差.*咬筋", "PHYS-002", "咬筋の左右差は視覚的に確認できる観察事実", "臨床観察"),
    ("舌.*上あご|上あご.*舌", "PHYS-003", "舌の理想的な安静位は上あごへの接触", "口腔生理学"),
    ("リンパ.*流|リンパ液", "PHYS-004", "リンパ液の流れは筋肉の収縮により促進される", "生理学定説"),
    ("表情.*筋肉|顔.*筋肉", "PHYS-005", "顔の表情は筋肉の収縮・弛緩によって作られる", "解剖学的定説"),
]

# ── HYPOTHESIS（根拠なし因果断定）として検出するパターン ──────────────────────
# これが投稿中で「〜です」「〜になります」と断定された場合は要修正。
# (pattern_regex, claim_label, suggested_rewrite)
_HYPOTHESIS_CAUSAL_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"口呼吸.{0,20}(むくみ|たるみ|原因|なる|なります)",
        "口呼吸がむくみ・たるみの原因である",
        "「口が開きやすい方は、口元や呼吸の癖も一緒に確認してみてください」",
    ),
    (
        r"冷房.{0,20}(顔|むくみ|たるみ|原因|なる)",
        "冷房が顔をむくませる",
        "「冷房環境では、顔まわりの緊張を感じる方が多いです」",
    ),
    (
        r"浅い呼吸.{0,20}(交感神経|緊張|優位|原因)",
        "浅い呼吸で交感神経が優位になる",
        "「浅い呼吸が続くと、顔や首まわりの緊張を感じやすくなる傾向があります」",
    ),
    (
        r"腹式呼吸.{0,20}(表情筋|ゆるむ|ほぐれ|リラックス|原因)",
        "腹式呼吸で表情筋がゆるむ",
        "「腹式呼吸を意識すると、顔まわりの力が抜けやすくなると感じています」",
    ),
    (
        r"咬筋.{0,20}(むくみ|原因|始まる|引き起こ)",
        "咬筋の硬さからむくみが始まる",
        "「咬筋が硬くなっている方は、顔まわりのむくみを感じやすい傾向があります」",
    ),
    (
        r"(食いしばり|歯ぎしり).{0,20}(たるみ|むくみ|左右差|原因|引き起こ)",
        "食いしばり・歯ぎしりがたるみ・左右差を引き起こす",
        "「食いしばりの習慣がある方は、左右差や顔のコリを感じやすい傾向があります」",
    ),
    (
        r"姿勢.{0,20}(顔|たるみ|老け|原因|影響)",
        "姿勢が顔のたるみ・老け見えの原因になる",
        "「姿勢と顔の状態は関係していると感じることが多いです。一緒に確認してみてください」",
    ),
    (
        r"(ストレス|睡眠不足).{0,20}(顔|むくみ|たるみ|老け|原因)",
        "ストレス・睡眠不足が顔の変化を引き起こす",
        "「ストレスや睡眠の質が気になる方は、顔まわりの状態と合わせて確認することをお勧めします」",
    ),
]

# ── Instagramデータに言及する表現（FALLBACK時に禁止）────────────────────────
_INSTAGRAM_TREND_PATTERNS: list[tuple[str, str]] = [
    (r"Instagram(で|に)(話題|トレンド|バズ)", "「Instagramで話題」という表現"),
    (r"(話題|トレンド|バズ).{0,10}(Instagram|インスタ)", "Instagramトレンドへの言及"),
    (r"再生数.{0,10}(万|千|百)", "再生数を根拠にした表現"),
    (r"いいね数.{0,10}(万|千|百)", "いいね数を根拠にした表現"),
    (r"複数媒体で話題", "「複数媒体で話題」という表現"),
    (r"(今|最近).{0,10}(注目|話題|トレンド)", "「最近話題」系の表現"),
]

# ── Reality なし断定表現 ──────────────────────────────────────────────────
_REALITY_CLAIM_PATTERNS: list[tuple[str, str]] = [
    (r"実際に(お客様|患者|来院).{0,20}(変わ|改善|効果)", "実際の施術体験を示唆する表現"),
    (r"(多くの|たくさんの)お客様.{0,20}(悩|困|感じ)", "施術経験を根拠にした一般化"),
    (r"(施術|ケア)で.{0,20}(変わ|改善|解決)できます", "施術効果の断定"),
]


class ClaimItem(NamedTuple):
    classification: str      # "FACT" / "INSIGHT" / "HYPOTHESIS"
    claim_label: str         # 主張の短い説明
    evidence_id: str         # 根拠ID（FACTのみ）
    suggested_rewrite: str   # HYPOTHESISの場合の言い換え案


def _scan_text(text: str, patterns: list[tuple]) -> list[tuple[str, ...]]:
    """正規表現パターンリストでテキストをスキャンしヒットしたものを返す。"""
    hits = []
    for entry in patterns:
        pattern = entry[0]
        rest = entry[1:]
        if re.search(pattern, text, re.IGNORECASE):
            hits.append((pattern,) + rest)
    return hits


def run_claims_check(record: dict, data_mode: str) -> dict:
    """
    投稿レコードの主張を分類し、問題のある表現を報告する。

    Returns:
      {
        "data_mode": str,
        "claims": [ClaimItem, ...],
        "instagram_violations": [(pattern, label), ...],
        "reality_violations": [(pattern, label), ...],
        "hypothesis_count": int,
        "fact_count": int,
        "insight_count": int,
        "all_pass": bool,
        "blocking_issues": [str, ...],
      }
    """
    is_fallback = (data_mode == "FALLBACK_NO_INSTAGRAM")
    has_reality = bool(record.get("_reality") or record.get("reality_text", "").strip())

    combined = " ".join([
        record.get("hook", ""),
        record.get("script_full", ""),
        record.get("caption", ""),
    ])

    claims: list[ClaimItem] = []

    # FACT パターンをスキャン
    for pat, ev_id, desc, _scope in _FACT_PATTERNS:
        if re.search(pat, combined, re.IGNORECASE):
            claims.append(ClaimItem("FACT", desc, ev_id, ""))

    # HYPOTHESIS（根拠なし因果断定）をスキャン
    hyp_hits = _scan_text(combined, _HYPOTHESIS_CAUSAL_PATTERNS)
    for _, label, rewrite in hyp_hits:
        claims.append(ClaimItem("HYPOTHESIS", label, "", rewrite))

    # Instagram 禁止表現（FALLBACKモード時）
    instagram_violations: list[tuple[str, str]] = []
    if is_fallback:
        ig_hits = _scan_text(combined, _INSTAGRAM_TREND_PATTERNS)
        instagram_violations = [(p, lbl) for p, lbl in ig_hits]

    # Reality なし体験談（Reality 入力なしの場合）
    reality_violations: list[tuple[str, str]] = []
    if not has_reality:
        rv_hits = _scan_text(combined, _REALITY_CLAIM_PATTERNS)
        reality_violations = [(p, lbl) for p, lbl in rv_hits]

    # 残りをINSIGHTとして分類（専門家の見解・観察として）
    has_specialist_observation = any(w in combined for w in [
        "傾向があります", "感じています", "感じることが多い", "一緒に確認",
        "見てきた", "施術していて", "場合が多い", "可能性があります",
    ])
    if has_specialist_observation and not any(c.classification == "HYPOTHESIS" for c in claims):
        claims.append(ClaimItem("INSIGHT", "専門家の観察・傾向の共有", "", ""))

    # blocking_issues 集約
    blocking_issues: list[str] = []
    if instagram_violations:
        for _, lbl in instagram_violations:
            blocking_issues.append(f"FALLBACKモードでInstagram根拠表現: {lbl}")
    if reality_violations:
        for _, lbl in reality_violations:
            blocking_issues.append(f"Reality未入力なのに体験談表現: {lbl}")
    for c in claims:
        if c.classification == "HYPOTHESIS":
            blocking_issues.append(
                f"根拠なし因果断定: 「{c.claim_label}」"
                f" → {c.suggested_rewrite}"
            )

    hypothesis_count = sum(1 for c in claims if c.classification == "HYPOTHESIS")
    fact_count       = sum(1 for c in claims if c.classification == "FACT")
    insight_count    = sum(1 for c in claims if c.classification == "INSIGHT")

    all_pass = (
        len(blocking_issues) == 0
        and hypothesis_count == 0
    )

    return {
        "data_mode":            data_mode,
        "claims":               [c._asdict() for c in claims],
        "instagram_violations": instagram_violations,
        "reality_violations":   reality_violations,
        "hypothesis_count":     hypothesis_count,
        "fact_count":           fact_count,
        "insight_count":        insight_count,
        "all_pass":             all_pass,
        "blocking_issues":      blocking_issues,
    }


def format_claims_report(result: dict) -> str:
    """
    Claims Check 結果をターミナル表示用テキストに整形する。
    """
    lines = []
    data_mode = result.get("data_mode", "UNKNOWN")
    all_pass  = result.get("all_pass", False)
    blocking  = result.get("blocking_issues", [])
    claims    = result.get("claims", [])

    verdict_icon = "✅" if all_pass else "❌"
    lines.append(f"  Claims Check: {verdict_icon} {'PASS' if all_pass else 'FAIL'}")
    lines.append(f"  データモード: {data_mode}")
    lines.append(
        f"  分類内訳: FACT={result['fact_count']} "
        f"INSIGHT={result['insight_count']} "
        f"HYPOTHESIS={result['hypothesis_count']}"
    )

    if claims:
        lines.append("")
        lines.append("  【主張分類】")
        for c in claims:
            icon = {"FACT": "✅", "INSIGHT": "💡", "HYPOTHESIS": "⚠️"}.get(c["classification"], "?")
            ev   = f" [{c['evidence_id']}]" if c.get("evidence_id") else ""
            lines.append(f"    {icon} {c['classification']}{ev}: {c['claim_label']}")
            if c.get("suggested_rewrite"):
                lines.append(f"         言い換え案: {c['suggested_rewrite']}")

    if blocking:
        lines.append("")
        lines.append("  【要修正 — 投稿不可】")
        for b in blocking:
            lines.append(f"    ・{b}")

    return "\n".join(lines)
