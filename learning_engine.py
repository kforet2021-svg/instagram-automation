"""
learning_engine.py
【2026-07-01: Sprint2 Learning Engine — 初回実装】
【2026-07-01(Sprint3): Evidence Layer 追加 — evidence_registry/evidence_links登録・Evidenceベースconfidence再計算】

Creator Intelligenceを「Learning Company」として機能させるためのコアエンジン。
Collect → Discover の次のステップ: Learn → Predict の土台を担う。

目的:
  毎日のAI分析結果(success_factors / post_analysis)から、再利用可能な「知識単位
  (KnowledgeUnit)」を抽出し、knowledge_unitsシートに蓄積する。
  同じパターンが再発見されるたびにevidence_countを増やし、3以上でVALIDATEDへ昇格
  させることで、「実績に裏付けられた知識だけを信頼度高く扱う」仕組みを実現する。

このファイルがやること:
  1. entries(main.py._score_and_analyze_postsが生成する投稿分析結果リスト)から、
     9次元のうち現在データがある4次元(Hook/Structure/Psychology/CTA)の
     KnowledgeUnitを抽出する。
  2. knowledge_unitsシートを読み込み、unit_id(dimension:pattern_name)で重複判定する。
  3. 初回発見 → BORN(confidence=0.3, evidence_count=1)として追加。
  4. 再発見 → evidence_count++、confidence再計算、evidence_count>=3でVALIDATED昇格。
  5. 抽出・保存できた件数をコンソールに出力する。

このファイルがやらないこと:
  - 新しいOpenAI呼び出しは一切行わない(コストゼロ)。
  - 既存のknowledge_library / knowledge_registryには一切手を入れない。
  - Prediction Engine全体の実装(Pattern Forecastの土台のみ = knowledge_unitsの蓄積)。

【9次元とデータソース対応】
  ① Hook         : success_factors["冒頭3秒のフック"] から抽出
  ② Structure    : success_factors["構成"] から抽出
  ③ Psychology   : success_factors["心理トリガー"] から既知トリガー名を抽出
  ④ Visual       : success_factors["顔出し有無"] + ["Before→After"] から抽出
  ⑤ CTA         : success_factors["CTA"] から既知CTA種別を抽出
  ⑥ Brand       : 現時点ではデータ不足のため未実装(将来)
  ⑦ Context     : 現時点ではデータ不足のため未実装(将来)
  ⑧ Timing      : 現時点ではデータ不足のため未実装(将来)
  ⑨ Reproducibility: knowledge_units蓄積が十分になってから実装(将来)

【KnowledgeUnitのunit_idについて】
  unit_id = f"{dimension}:{pattern_name}"
  patternの正規化は決定論的(OpenAIに判断させない)。同じ入力なら常に同じunit_idになる。
  これにより重複判定が安定し、OpenAIの出力揺れに左右されない。

【Confidence Scoreの計算式】
  confidence = (
      0.40 * min(evidence_count / 10.0, 1.0)         # 証拠の量(10件で満点)
    + 0.30 * _recency_score(last_seen_at)             # 新しさ(7日以内=1.0, 180日以上=0.1)
    + 0.30 * (success_rate if success_rate > 0 else 0.5)  # 成功率(未計測は0.5で仮置き)
  )
  success_rateはフィードバックループ(CORE HARIの実投稿結果)が実装されるまで0.0のまま。
  0.0の間はconfidence計算で0.5として扱い、極端に低くならないようにする。
"""

import datetime
import hashlib
import re
from typing import Optional

import sheets_writer

# ────────────────────────────────────────────
# 定数
# ────────────────────────────────────────────

DIMENSION_HOOK = "Hook"
DIMENSION_STRUCTURE = "Structure"
DIMENSION_PSYCHOLOGY = "Psychology"
DIMENSION_VISUAL = "Visual"
DIMENSION_CTA = "CTA"

STATUS_BORN = "BORN"
STATUS_VALIDATED = "VALIDATED"
STATUS_ACTIVE = "ACTIVE"
STATUS_STALE = "STALE"
STATUS_EVOLVED = "EVOLVED"

VALIDATED_THRESHOLD = 3  # evidence_countがこの値以上でVALIDATEDへ昇格

# Stale判定: 最終確認からこの日数を超えたらSTALE
STALE_DAYS = 30

# ────────────────────────────────────────────
# Evidence Layer 定数 (2026-07-01 Sprint3)
# ────────────────────────────────────────────

EVIDENCE_TYPE_WEIGHTS = {
    "core_hari_result": 1.0,
    "instagram_post":   0.5,
    "comment_signal":   0.4,
    "paper":            0.4,
    "article":          0.3,
    "x_post":           0.3,
    "note":             0.3,
    "ir":               0.2,
    "news":             0.1,
}

# instagram_post の信頼性スコア(Bright Dataで取得した実測値なので0.8)
_INSTAGRAM_POST_RELIABILITY = 0.8
# 1投稿からの各unit支持強度(デフォルト)
_DEFAULT_SUPPORT_STRENGTH = 0.7

# 既知の心理トリガー(knowledge_registry._KNOWN_PSYCHOLOGY_TRIGGERSと同じリスト)
_KNOWN_PSYCHOLOGY_TRIGGERS = [
    "社会的証明",
    "限定性",
    "緊急性",
    "権威",
    "ザイガニク効果",
    "FOMO",
    "損失回避",
    "共感",
    "ビフォーアフター",
]

# 既知のCTA種別
_KNOWN_CTA_TYPES = [
    "保存",
    "コメント",
    "フォロー",
    "プロフィール誘導",
    "予約",
    "シェア",
    "いいね",
    "DM",
    "URL誘導",
]

# Visual判定ラベル
_VISUAL_FACE_LABELS = {"あり": "顔出しあり", "なし": "顔出しなし", "不明": "顔出し不明"}
_VISUAL_BA_LABEL = "Before→After使用"


# ────────────────────────────────────────────
# KnowledgeUnitデータクラス(相当)
# ────────────────────────────────────────────

def _make_unit(
    dimension: str,
    pattern_name: str,
    description: str,
    evidence_count: int,
    evidence_url: str,
    today: str,
) -> dict:
    """
    新規KnowledgeUnitのdictを生成する。
    statusはevidence_countに応じて自動決定するが、新規作成時は常に1なのでBORN。
    """
    confidence = _calc_confidence(evidence_count, today, today, 0.0)
    return {
        "unit_id": _make_unit_id(dimension, pattern_name),
        "dimension": dimension,
        "pattern_name": pattern_name,
        "description": description,
        "status": STATUS_BORN,
        "version": 1,
        "confidence": round(confidence, 3),
        "evidence_count": evidence_count,
        "reproduced_count": 0,
        "success_rate": 0.0,
        "last_seen_at": today,
        "first_seen_at": today,
        "evidence_urls": evidence_url,
    }


def _make_unit_id(dimension: str, pattern_name: str) -> str:
    return f"{dimension}:{pattern_name}"


# ────────────────────────────────────────────
# Confidence Score計算
# ────────────────────────────────────────────

def _recency_score(last_seen_at: str, today_str: str) -> float:
    """
    最終確認日から今日までの経過日数で鮮度スコアを返す。
    7日以内=1.0、30日=0.7、90日=0.3、180日以上=0.1
    """
    try:
        last = datetime.date.fromisoformat(last_seen_at)
        today = datetime.date.fromisoformat(today_str)
        days = (today - last).days
    except (ValueError, TypeError):
        return 0.5

    if days <= 7:
        return 1.0
    if days <= 30:
        return 0.7
    if days <= 90:
        return 0.3
    return 0.1


def _calc_confidence(
    evidence_count: int,
    last_seen_at: str,
    today_str: str,
    success_rate: float,
) -> float:
    """
    Confidence Score(0.0〜1.0)を計算する。

    confidence = 0.40 * evidence_weight
               + 0.30 * recency_weight
               + 0.30 * success_weight

    success_rateが0.0(未計測)の場合は0.5で仮置きする。
    """
    evidence_weight = min(evidence_count / 10.0, 1.0)
    recency_weight = _recency_score(last_seen_at, today_str)
    effective_success = success_rate if success_rate > 0.0 else 0.5
    return 0.40 * evidence_weight + 0.30 * recency_weight + 0.30 * effective_success


def _determine_status(evidence_count: int, current_status: str, last_seen_at: str, today_str: str) -> str:
    """
    evidence_count と 最終確認日からstatusを決定する。
    - STALEからの遷移: 新しい証拠が来たら再びVALIDATEDに戻す
    - EVOLVEDは外部から明示的に設定するもので、ここでは変更しない
    """
    if current_status == STATUS_EVOLVED:
        return STATUS_EVOLVED

    try:
        last = datetime.date.fromisoformat(last_seen_at)
        today = datetime.date.fromisoformat(today_str)
        days_stale = (today - last).days
    except (ValueError, TypeError):
        days_stale = 0

    # 新しい証拠が来たので STALE は解除
    if current_status == STATUS_STALE:
        if evidence_count >= VALIDATED_THRESHOLD:
            return STATUS_VALIDATED
        return STATUS_BORN

    if evidence_count >= VALIDATED_THRESHOLD:
        return STATUS_VALIDATED

    return STATUS_BORN


# ────────────────────────────────────────────
# パターン名の正規化(決定論的)
# ────────────────────────────────────────────

def _normalize_text_to_pattern(text: str, max_len: int = 30) -> str:
    """
    AIが生成したテキストから、重複判定キーとして使える短い正規化文字列を作る。
    - 先頭max_len文字を取り、句読点・記号を除去する
    - 空なら"不明"を返す
    """
    text = (text or "").strip()
    if not text:
        return "不明"
    # 「→」「:」「。」「、」などで分割して最初のフレーズを取る
    first = re.split(r"[→。、：:\n]", text)[0].strip()
    # 記号を除去
    first = re.sub(r"[^\w\s　-鿿＀-￯]", "", first)
    first = first.strip()[:max_len]
    return first if first else "不明"


def _extract_psychology_pattern(trigger_text: str) -> str:
    """
    心理トリガーテキストから既知トリガー名を検出し、パターン名を作る。
    例: "社会的証明・FOMO" → "社会的証明・FOMO"
    """
    found = [t for t in _KNOWN_PSYCHOLOGY_TRIGGERS if t in (trigger_text or "")]
    if not found:
        return _normalize_text_to_pattern(trigger_text, 30)
    return "・".join(found)


def _extract_cta_pattern(cta_text: str) -> str:
    """
    CTAテキストから既知CTA種別を検出し、パターン名を作る。
    例: "プロフィールのURLから予約をクリック" → "プロフィール誘導・予約"
    """
    found = [t for t in _KNOWN_CTA_TYPES if t in (cta_text or "")]
    if not found:
        return _normalize_text_to_pattern(cta_text, 30)
    return "・".join(found)


def _extract_visual_pattern(face_text: str, ba_text: str) -> str:
    """
    顔出し有無 + Before→After使用有無からVisualパターン名を作る。
    """
    face_normalized = face_text.strip() if face_text else ""
    face_label = _VISUAL_FACE_LABELS.get(face_normalized[:2], "顔出し不明")

    ba_text_lower = (ba_text or "").strip()
    uses_ba = ba_text_lower and "使用なし" not in ba_text_lower and "不明" not in ba_text_lower and len(ba_text_lower) > 5

    parts = [face_label]
    if uses_ba:
        parts.append(_VISUAL_BA_LABEL)
    return "・".join(parts)


# ────────────────────────────────────────────
# エントリ → KnowledgeUnit群 の抽出
# ────────────────────────────────────────────

def extract_units_from_entry(entry: dict) -> list:
    """
    1件のentry(main.pyのentriesリストの要素)から、最大5件のKnowledgeUnitを抽出する。
    各dimensionについて、パターンが抽出できた場合のみunitを返す。

    entry = {
        "post": {...},
        "analysis": {POST_ANALYSIS_TEXT_KEYS},
        "success_factors": {SUCCESS_FACTOR_TEXT_KEYS},
        "idea": {CORE_HARI_IDEA_TEXT_KEYS},
        ...
    }
    """
    entry = entry or {}
    sf = entry.get("success_factors") or {}
    post = entry.get("post") or {}
    today = datetime.date.today().isoformat()
    url = post.get("url", "")

    units = []

    # ① Hook
    hook_text = sf.get("冒頭3秒のフック", "")
    if hook_text and hook_text not in ("", "テキスト情報からは判断不可"):
        pattern = _normalize_text_to_pattern(hook_text, 30)
        if pattern != "不明":
            units.append(_make_unit(
                dimension=DIMENSION_HOOK,
                pattern_name=pattern,
                description=hook_text[:200],
                evidence_count=1,
                evidence_url=url,
                today=today,
            ))

    # ② Structure
    struct_text = sf.get("構成", "")
    if struct_text and struct_text not in ("", "テキスト情報からは判断不可"):
        pattern = _normalize_text_to_pattern(struct_text, 30)
        if pattern != "不明":
            units.append(_make_unit(
                dimension=DIMENSION_STRUCTURE,
                pattern_name=pattern,
                description=struct_text[:200],
                evidence_count=1,
                evidence_url=url,
                today=today,
            ))

    # ③ Psychology
    trigger_text = sf.get("心理トリガー", "")
    if trigger_text:
        pattern = _extract_psychology_pattern(trigger_text)
        if pattern != "不明":
            units.append(_make_unit(
                dimension=DIMENSION_PSYCHOLOGY,
                pattern_name=pattern,
                description=trigger_text[:200],
                evidence_count=1,
                evidence_url=url,
                today=today,
            ))

    # ④ Visual
    face_text = sf.get("顔出し有無", "")
    ba_text = sf.get("Before→After", "")
    if face_text or ba_text:
        pattern = _extract_visual_pattern(face_text, ba_text)
        if pattern:
            desc_parts = []
            if face_text:
                desc_parts.append(f"顔出し: {face_text[:50]}")
            if ba_text:
                desc_parts.append(f"Before→After: {ba_text[:100]}")
            units.append(_make_unit(
                dimension=DIMENSION_VISUAL,
                pattern_name=pattern,
                description=" / ".join(desc_parts),
                evidence_count=1,
                evidence_url=url,
                today=today,
            ))

    # ⑤ CTA
    cta_text = sf.get("CTA", "")
    if cta_text and cta_text not in ("", "テキスト情報からは判断不可"):
        pattern = _extract_cta_pattern(cta_text)
        if pattern != "不明":
            units.append(_make_unit(
                dimension=DIMENSION_CTA,
                pattern_name=pattern,
                description=cta_text[:200],
                evidence_count=1,
                evidence_url=url,
                today=today,
            ))

    return units


# ────────────────────────────────────────────
# Sheets との同期(upsert)
# ────────────────────────────────────────────

def _load_existing_units() -> dict:
    """
    knowledge_unitsシートから全行を読み込み、unit_id → {"row": 行番号, "values": dict}
    のdictにして返す。読み込み失敗時は空dictを返す。
    """
    try:
        rows = sheets_writer.get_knowledge_units()
        return {r["values"].get("unit_id", ""): r for r in rows if r["values"].get("unit_id")}
    except Exception as e:
        print(f"  ⚠️ knowledge_units読み込み失敗: {e}")
        return {}


def _upsert_unit(unit: dict, existing: dict, today: str) -> str:
    """
    1件のKnowledgeUnitをupsertする。
    戻り値: "added" | "updated" | "skipped"
    """
    uid = unit["unit_id"]

    if uid not in existing:
        # 初回発見 → BORN として追加
        try:
            sheets_writer.append_knowledge_unit(unit)
            return "added"
        except Exception as e:
            print(f"  ⚠️ knowledge_unit追加失敗({uid}): {e}")
            return "skipped"

    # 再発見 → evidence_count++、confidence再計算、status昇格判定
    existing_row = existing[uid]
    row_id = existing_row["row"]
    # row_id < 1 は「同一実行内で追加済み・行番号不明」のセンチネル。
    # Sheets 更新は行わずスキップ（二重追加を防ぐだけで十分）。
    if row_id < 1:
        return "skipped"
    old = existing_row["values"]

    try:
        old_count = int(old.get("evidence_count") or 0)
        old_success = float(old.get("success_rate") or 0.0)
        old_reproduced = int(old.get("reproduced_count") or 0)
        old_first_seen = old.get("first_seen_at") or today
        old_status = old.get("status") or STATUS_BORN
        old_version = int(old.get("version") or 1)
        old_urls = old.get("evidence_urls") or ""
    except (ValueError, TypeError):
        old_count, old_success, old_reproduced = 0, 0.0, 0
        old_first_seen, old_status, old_version, old_urls = today, STATUS_BORN, 1, ""

    new_count = old_count + 1
    new_confidence = _calc_confidence(new_count, today, today, old_success)
    new_status = _determine_status(new_count, old_status, today, today)

    # evidence_urlsに今回のURLを追記(重複は除く)
    existing_urls = set(u.strip() for u in old_urls.split(",") if u.strip())
    new_url = unit.get("evidence_urls", "")
    if new_url:
        existing_urls.add(new_url)
    new_urls = ",".join(list(existing_urls)[:10])  # 最大10件保持

    updated = dict(old)
    updated.update({
        "evidence_count": new_count,
        "confidence": round(new_confidence, 3),
        "status": new_status,
        "last_seen_at": today,
        "evidence_urls": new_urls,
        "version": old_version,
        "reproduced_count": old_reproduced,
        "success_rate": old_success,
        "first_seen_at": old_first_seen,
        # pattern_name / description / dimension は変更しない
        "unit_id": uid,
        "dimension": old.get("dimension") or unit.get("dimension"),
        "pattern_name": old.get("pattern_name") or unit.get("pattern_name"),
        "description": old.get("description") or unit.get("description"),
    })

    try:
        sheets_writer.update_knowledge_unit(row_id, updated)
        return "updated"
    except Exception as e:
        print(f"  ⚠️ knowledge_unit更新失敗({uid}): {e}")
        return "skipped"


# ────────────────────────────────────────────
# メイン公開関数
# ────────────────────────────────────────────

# ────────────────────────────────────────────────────────────────────────────
# ACTIVE / STALE 自動遷移 (2026-07-01追加)
# ────────────────────────────────────────────────────────────────────────────

def transition_stale_units() -> None:
    """
    knowledge_unitsシートを確認し、last_seen_atがSTALE_DAYS日以上前のVALIDATED
    パターンをSTALEに自動降格する。
    main()の冒頭付近(スコアリング前)で呼ぶ。失敗しても例外は外に伝播させない。

    遷移ルール:
      VALIDATED → STALE : last_seen_at が STALE_DAYS 日以上前
      BORN      → STALE : 同上(BORNのまま放置されているパターンも古くなったらSTALEへ)
      STALE     : 新しい証拠(_upsert_unit)が来たときに VALIDATED/BORN に自動復帰する
      ACTIVE    → STALE : 同上(ACTIVEの自動昇格はPattern Forecast実装後に追加)
      EVOLVED   : 変更しない
    """
    today = datetime.date.today().isoformat()
    try:
        rows = sheets_writer.get_knowledge_units()
    except Exception as e:
        print(f"  ⚠️ transition_stale_units: knowledge_units読み込み失敗: {e}")
        return

    staled = 0
    for r in rows:
        v = r["values"]
        status = (v.get("status") or "").strip()
        if status in (STATUS_STALE, STATUS_EVOLVED):
            continue
        last_seen = (v.get("last_seen_at") or "").strip()
        if not last_seen:
            continue
        try:
            days = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(last_seen)).days
        except ValueError:
            continue
        if days >= STALE_DAYS:
            updated = dict(v)
            updated["status"] = STATUS_STALE
            # confidence に鮮度ペナルティをかけて再計算
            try:
                evidence_count = int(v.get("evidence_count") or 1)
                success_rate = float(v.get("success_rate") or 0.0)
                updated["confidence"] = round(_calc_confidence(evidence_count, last_seen, today, success_rate), 3)
            except (ValueError, TypeError):
                pass
            try:
                sheets_writer.update_knowledge_unit(r["row"], updated)
                staled += 1
            except Exception as e:
                uid = v.get("unit_id", "不明")
                print(f"  ⚠️ STALE遷移失敗({uid}): {e}")

    if staled:
        print(f"Learning Engine: {staled}件のパターンをSTALEに降格しました(last_seen_at >= {STALE_DAYS}日前)")


# ────────────────────────────────────────────────────────────────────────────
# Pattern Forecast 土台 — VALIDATED パターンの取得 (2026-07-01追加)
# ────────────────────────────────────────────────────────────────────────────

def get_validated_patterns(top_n: int = 3) -> list:
    """
    knowledge_unitsシートからstatus=VALIDATED(またはACTIVE)のパターンを読み込み、
    confidence降順でtop_n件を返す。

    戻り値: [{"unit_id":..., "dimension":..., "pattern_name":..., "description":...,
               "confidence":..., "evidence_count":..., "success_rate":...}, ...]
    空リストの場合はプロンプトへの差し込みをスキップする(Pattern Forecastは任意強化)。
    """
    try:
        rows = sheets_writer.get_knowledge_units()
    except Exception as e:
        print(f"  ⚠️ get_validated_patterns: knowledge_units読み込み失敗: {e}")
        return []

    validated = []
    for r in rows:
        v = r["values"]
        status = (v.get("status") or "").strip()
        if status not in (STATUS_VALIDATED, STATUS_ACTIVE):
            continue
        try:
            conf = float(v.get("confidence") or 0.0)
        except (ValueError, TypeError):
            conf = 0.0
        validated.append({
            "unit_id": v.get("unit_id", ""),
            "dimension": v.get("dimension", ""),
            "pattern_name": v.get("pattern_name", ""),
            "description": v.get("description", ""),
            "confidence": conf,
            "evidence_count": v.get("evidence_count", ""),
            "success_rate": v.get("success_rate", ""),
        })

    validated.sort(key=lambda x: x["confidence"], reverse=True)
    return validated[:top_n]


# ────────────────────────────────────────────────────────────────────────────
# Evidence Layer ヘルパー (2026-07-01 Sprint3)
# ────────────────────────────────────────────────────────────────────────────

def _generate_evidence_id(evidence_type: str, url: str, observed_at: str = "") -> str:
    """
    Evidence の自然キー。
    instagram_post: hash(type:url) — 同じURLは同じ証拠
    それ以外 / core_hari_result: hash(type:url:observed_at) — 日付込みで一意
    """
    if evidence_type == "instagram_post":
        raw = f"{evidence_type}:{url}"
    else:
        raw = f"{evidence_type}:{url}:{observed_at}"
    return hashlib.md5(raw.encode()).hexdigest()[:10]


def _generate_link_id(unit_id: str, evidence_id: str) -> str:
    raw = f"{unit_id}:{evidence_id}"
    return hashlib.md5(raw.encode()).hexdigest()[:10]


def _make_instagram_evidence(post: dict, observed_at: str) -> dict:
    """Bright Dataの投稿1件からEvidence dictを生成する。"""
    url = post.get("url", "")
    owner = post.get("owner_username") or post.get("owner_full_name") or ""
    eid = _generate_evidence_id("instagram_post", url)
    return {
        "evidence_id": eid,
        "evidence_type": "instagram_post",
        "source_url": url,
        "source_title": owner,
        "platform": "instagram",
        "observed_at": observed_at,
        "summary": (post.get("caption") or "")[:200],
        "reliability_score": str(_INSTAGRAM_POST_RELIABILITY),
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }


def _make_evidence_link(unit_id: str, evidence_id: str, support_reason: str = "") -> dict:
    lid = _generate_link_id(unit_id, evidence_id)
    return {
        "link_id": lid,
        "unit_id": unit_id,
        "evidence_id": evidence_id,
        "support_strength": str(_DEFAULT_SUPPORT_STRENGTH),
        "support_reason": support_reason[:200],
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }


def _load_existing_evidence_ids() -> set:
    """evidence_registryの既存 evidence_id セットを返す(重複登録防止)。"""
    try:
        rows = sheets_writer.get_evidence_registry()
        return {r["values"].get("evidence_id", "") for r in rows}
    except Exception as e:
        print(f"  ⚠️ evidence_registry読み込み失敗(空setで継続): {e}")
        return set()


def _load_existing_link_ids() -> set:
    """evidence_linksの既存 link_id セットを返す(重複登録防止)。"""
    try:
        rows = sheets_writer.get_evidence_links()
        return {r["values"].get("link_id", "") for r in rows}
    except Exception as e:
        print(f"  ⚠️ evidence_links読み込み失敗(空setで継続): {e}")
        return set()


def _calc_confidence_from_evidence(unit_id: str, today_str: str, last_seen_at: str) -> Optional[float]:
    """
    evidence_linksとevidence_registryを参照してEvidenceベースのconfidenceを計算する。
    evidence_linksが0件の場合はNoneを返す(呼び出し元で旧formula fallback)。

    confidence = raw * 0.7 + recency_score * 0.3
    raw = Σ(reliability * support_strength * type_weight) / Σ(type_weight)
    """
    try:
        links = sheets_writer.get_evidence_links()
        reg = sheets_writer.get_evidence_registry()
    except Exception as e:
        print(f"  ⚠️ confidence_from_evidence: シート読み込み失敗: {e}")
        return None

    reg_map = {r["values"].get("evidence_id", ""): r["values"] for r in reg}
    unit_links = [r["values"] for r in links if r["values"].get("unit_id") == unit_id]

    if not unit_links:
        return None

    numerator = 0.0
    denominator = 0.0
    for link in unit_links:
        eid = link.get("evidence_id", "")
        ev = reg_map.get(eid, {})
        etype = ev.get("evidence_type", "instagram_post")
        try:
            reliability = float(ev.get("reliability_score") or _INSTAGRAM_POST_RELIABILITY)
            support = float(link.get("support_strength") or _DEFAULT_SUPPORT_STRENGTH)
        except (ValueError, TypeError):
            reliability, support = _INSTAGRAM_POST_RELIABILITY, _DEFAULT_SUPPORT_STRENGTH
        weight = EVIDENCE_TYPE_WEIGHTS.get(etype, 0.3)
        numerator += reliability * support * weight
        denominator += weight

    raw = numerator / denominator if denominator > 0 else 0.0
    recency = _recency_score(last_seen_at, today_str)
    return round(min(raw * 0.7 + recency * 0.3, 1.0), 3)


def _refresh_confidence_from_evidence(affected_unit_ids: set, today: str) -> None:
    """
    upsert後に影響を受けたunit_idのconfidenceをEvidenceベースで再計算して更新する。
    evidence_linksが0件のunitはスキップ(旧formulaのまま)。
    """
    if not affected_unit_ids:
        return
    try:
        ku_rows = sheets_writer.get_knowledge_units()
    except Exception as e:
        print(f"  ⚠️ _refresh_confidence: knowledge_units読み込み失敗: {e}")
        return

    batch: list = []
    for r in ku_rows:
        v = r["values"]
        uid = v.get("unit_id", "")
        if uid not in affected_unit_ids:
            continue
        last_seen = v.get("last_seen_at") or today
        new_conf = _calc_confidence_from_evidence(uid, today, last_seen)
        if new_conf is None:
            continue
        updated = dict(v)
        updated["confidence"] = new_conf
        batch.append((r["row"], updated))

    if batch:
        try:
            n = sheets_writer.batch_update_knowledge_units(batch)
            print(f"  confidence一括更新: {n}件")
        except Exception as e:
            print(f"  ⚠️ confidence一括更新失敗: {e}")


def run_learning_engine(entries: list) -> None:
    """
    main.py._score_and_analyze_postsの末尾から呼ぶ。
    entries全件からKnowledgeUnitを抽出し、knowledge_unitsシートにupsertする。

    失敗しても例外は外に伝播させない(呼び出し元の処理を止めない)。
    """
    entries = entries or []
    if not entries:
        return

    today = datetime.date.today().isoformat()

    # 全entryからunitを抽出
    all_units: list[dict] = []
    for entry in entries:
        try:
            all_units.extend(extract_units_from_entry(entry))
        except Exception as e:
            url = (entry.get("post") or {}).get("url", "不明")
            print(f"  ⚠️ KnowledgeUnit抽出失敗({url}): {e}")

    if not all_units:
        print("Learning Engine: KnowledgeUnitを抽出できませんでした")
        return

    # 既存unitを読み込む
    existing = _load_existing_units()

    # upsert
    counts = {"added": 0, "updated": 0, "skipped": 0}
    affected_unit_ids: set = set()
    for unit in all_units:
        result = _upsert_unit(unit, existing, today)
        counts[result] += 1
        if result in ("added", "updated"):
            affected_unit_ids.add(unit["unit_id"])
        # 追加した場合はexistingをその場で更新(同一実行内の重複検知)
        if result == "added":
            uid = unit["unit_id"]
            # row=-1 は「同一実行内で追加済み・行番号不明」のセンチネル。
            # _upsert_unit は row_id < 1 をチェックしてスキップする。
            existing[uid] = {"row": -1, "values": unit}

    # ── Evidence Layer (Sprint3) ──────────────────────────────────────────
    # entryごとにEvidence登録 + EvidenceLinks登録 → confidence再計算
    try:
        existing_eids = _load_existing_evidence_ids()
        existing_lids = _load_existing_link_ids()

        new_evidences: list[dict] = []
        new_links: list[dict] = []

        for entry in entries:
            post = entry.get("post") or {}
            url = post.get("url", "")
            if not url:
                continue

            ev = _make_instagram_evidence(post, today)
            eid = ev["evidence_id"]

            # Evidence重複排除
            if eid not in existing_eids:
                new_evidences.append(ev)
                existing_eids.add(eid)

            # このentryから抽出されたunitごとにEvidenceLink登録
            try:
                entry_units = extract_units_from_entry(entry)
            except Exception:
                entry_units = []

            for unit in entry_units:
                uid = unit["unit_id"]
                lid = _generate_link_id(uid, eid)
                if lid not in existing_lids:
                    new_links.append(_make_evidence_link(uid, eid, support_reason=unit.get("dimension", "")))
                    existing_lids.add(lid)

        if new_evidences:
            sheets_writer.append_evidence_entries(new_evidences)
            print(f"  Evidence Registry: {len(new_evidences)}件追加")
        if new_links:
            sheets_writer.append_evidence_links(new_links)
            print(f"  Evidence Links: {len(new_links)}件追加")

        # Evidenceベースのconfidence再計算
        if affected_unit_ids:
            _refresh_confidence_from_evidence(affected_unit_ids, today)

    except Exception as e:
        print(f"  ⚠️ Evidence Layer登録失敗(既存処理への影響なし): {e}")
    # ─────────────────────────────────────────────────────────────────────

    # validated件数を集計
    validated_total = sum(
        1 for r in existing.values()
        if (r["values"].get("status") or "") == STATUS_VALIDATED
    )

    print(
        f"Learning Engine: 追加{counts['added']}件 / 更新{counts['updated']}件 / "
        f"スキップ{counts['skipped']}件 (knowledge_units合計VALIDATEDパターン: {validated_total}件)"
    )
