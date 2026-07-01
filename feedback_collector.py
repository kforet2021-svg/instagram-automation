"""
feedback_collector.py
【2026-07-01: Sprint2 フィードバックループ — 初回実装】
【2026-07-01(Sprint3): manual_post_results → evidence_registry/evidence_links 変換追加】

CORE HARIが実際に投稿した結果をknowledge_unitsのsuccess_rateに反映する。

流れ:
  1. manual_post_resultsシートを読み込む
  2. checked_atが空かつresult_statusが入力済みの行を「未処理」として選ぶ
  3. source_pattern_id (= knowledge_units.unit_id) でグループ化する
  4. グループごとに success_rate を計算する
     success_rate = success件数 / (success + partial + none件数)
     ※ partialは0.5件として重み付けする(成果があいまいなため)
  5. 対応するknowledge_unitのsuccess_rateとconfidenceを更新する
  6. 処理済み行のchecked_atに今日の日付を書き込む(二重処理を防ぐ)

OpenAI呼び出しゼロ。main()の末尾で1回だけ呼ぶ。

【result_statusの定義】
  success : 明確な成果あり(フォロワー増・保存多数・予約問い合わせ等)
  partial : 再生数は伸びたが集客成果は不明
  none    : 反応が薄く成果なし
  (空欄)  : 未評価(処理対象外)

【success_rateの計算】
  success = 1.0点、partial = 0.5点、none = 0.0点 として
  weighted_sum / total_count を計算する。
  例: success×2件 + partial×1件 + none×1件 → (2×1.0 + 1×0.5 + 1×0.0) / 4 = 0.625

【source_pattern_idの書き方(手入力ガイド)】
  knowledge_unitsシートの unit_id 列の値をそのままコピーする。
  例: "Hook:鏡を見て衝撃を受けた主婦の表情から始まる"
      "Psychology:社会的証明・共感"
      "CTA:予約"
  空欄でも構わない(source_pattern_idが空の行はsuccess_rate更新をスキップする)。
"""

import datetime

import sheets_writer
from learning_engine import (
    _calc_confidence,
    _generate_evidence_id,
    _generate_link_id,
    _make_evidence_link,
)

# result_statusの重み(success/partial/none以外は無視)
_STATUS_WEIGHT = {
    "success": 1.0,
    "partial": 0.5,
    "none": 0.0,
}


def _today_str() -> str:
    return datetime.date.today().isoformat()


def _collect_unprocessed(results: list) -> list:
    """
    manual_post_resultsの全行から、未処理(checked_at空 & result_status入力済み)
    の行だけを返す。
    """
    unprocessed = []
    for r in results:
        v = r["values"]
        checked = (v.get("checked_at") or "").strip()
        status = (v.get("result_status") or "").strip().lower()
        if not checked and status in _STATUS_WEIGHT:
            unprocessed.append(r)
    return unprocessed


def _group_by_pattern(unprocessed: list) -> dict:
    """
    未処理行を source_pattern_id でグループ化する。
    source_pattern_idが空の行は "UNKNOWN" キーにまとめる(success_rate更新はスキップ)。
    戻り値: {pattern_id: [row_dict, ...]}
    """
    groups: dict[str, list] = {}
    for r in unprocessed:
        pid = (r["values"].get("source_pattern_id") or "").strip()
        key = pid if pid else "UNKNOWN"
        groups.setdefault(key, []).append(r)
    return groups


def _calc_success_rate(rows: list) -> float:
    """
    rowsのresult_statusから重み付きsuccess_rateを計算する。
    対象外ステータスの行は除外してから計算する。
    """
    total = 0
    weighted_sum = 0.0
    for r in rows:
        status = (r["values"].get("result_status") or "").strip().lower()
        weight = _STATUS_WEIGHT.get(status)
        if weight is None:
            continue
        weighted_sum += weight
        total += 1
    if total == 0:
        return 0.0
    return round(weighted_sum / total, 3)


def _convert_mpr_to_evidence(rows: list, today: str) -> None:
    """
    manual_post_resultsの処理済み行をevidence_registry + evidence_linksに変換して登録する。
    既存のmanual_post_results処理フローには一切影響しない(追加処理のみ)。
    """
    if not rows:
        return
    try:
        existing_eids = {
            r["values"].get("evidence_id", "")
            for r in sheets_writer.get_evidence_registry()
        }
        existing_lids = {
            r["values"].get("link_id", "")
            for r in sheets_writer.get_evidence_links()
        }
    except Exception as e:
        print(f"  ⚠️ _convert_mpr_to_evidence: Evidence読み込み失敗(スキップ): {e}")
        return

    new_evidences = []
    new_links = []
    now_str = datetime.datetime.now().isoformat(timespec="seconds")

    for r in rows:
        v = r["values"]
        url = (v.get("posted_url") or "").strip()
        posted_at = (v.get("posted_at") or today).strip()
        pattern_id = (v.get("source_pattern_id") or "").strip()
        result_status = (v.get("result_status") or "").strip().lower()
        notes = (v.get("notes") or "").strip()

        # reliability: success=1.0, partial=0.7, none=0.3
        reliability_map = {"success": 1.0, "partial": 0.7, "none": 0.3}
        reliability = reliability_map.get(result_status, 0.5)

        eid = _generate_evidence_id("core_hari_result", url, posted_at)
        if eid not in existing_eids:
            new_evidences.append({
                "evidence_id": eid,
                "evidence_type": "core_hari_result",
                "source_url": url,
                "source_title": "CORE HARI FACE",
                "platform": (v.get("platform") or "instagram").strip(),
                "observed_at": posted_at,
                "summary": f"result={result_status} / {notes}"[:200],
                "reliability_score": str(reliability),
                "created_at": now_str,
            })
            existing_eids.add(eid)

        # EvidenceLink: result_statusがsuccess/partial/noneかつpattern_idがある場合のみ
        if pattern_id and result_status in ("success", "partial", "none"):
            lid = _generate_link_id(pattern_id, eid)
            if lid not in existing_lids:
                # support_strength: success=1.0, partial=0.5, none=0.0
                strength_map = {"success": 1.0, "partial": 0.5, "none": 0.0}
                link = _make_evidence_link(pattern_id, eid, support_reason=f"CORE HARI実投稿: {result_status}")
                link["support_strength"] = str(strength_map.get(result_status, 0.5))
                new_links.append(link)
                existing_lids.add(lid)

    if new_evidences:
        try:
            sheets_writer.append_evidence_entries(new_evidences)
            print(f"  Feedback→Evidence: {len(new_evidences)}件のcore_hari_resultを登録")
        except Exception as e:
            print(f"  ⚠️ Evidence登録失敗: {e}")
    if new_links:
        try:
            sheets_writer.append_evidence_links(new_links)
            print(f"  Feedback→Evidence Links: {len(new_links)}件登録")
        except Exception as e:
            print(f"  ⚠️ Evidence Links登録失敗: {e}")


def run_feedback_collector() -> None:
    """
    manual_post_resultsの未処理行を読み込み、knowledge_unitsのsuccess_rateを更新する。
    失敗しても例外は外に伝播させない。
    """
    today = _today_str()

    # 1. manual_post_results を読み込む
    try:
        all_results = sheets_writer.get_manual_post_results()
    except Exception as e:
        print(f"Feedback Collector: manual_post_results読み込み失敗: {e}")
        return

    # 2. 未処理行を選別
    unprocessed = _collect_unprocessed(all_results)
    if not unprocessed:
        print("Feedback Collector: 未処理の投稿結果はありませんでした")
        return

    print(f"Feedback Collector: 未処理の投稿結果 {len(unprocessed)}件を処理します...")

    # 3. source_pattern_id でグループ化
    groups = _group_by_pattern(unprocessed)

    # 4. knowledge_units を読み込んで unit_id → row のマップを作る
    try:
        ku_rows = sheets_writer.get_knowledge_units()
    except Exception as e:
        print(f"Feedback Collector: knowledge_units読み込み失敗: {e}")
        return
    ku_map = {r["values"].get("unit_id", ""): r for r in ku_rows if r["values"].get("unit_id")}

    updated_count = 0
    skipped_count = 0

    for pattern_id, rows in groups.items():
        if pattern_id == "UNKNOWN":
            print(f"  source_pattern_id未入力の行が {len(rows)}件あります(スキップ)")
            skipped_count += len(rows)
            continue

        new_rate = _calc_success_rate(rows)

        if pattern_id not in ku_map:
            print(f"  ⚠️ knowledge_unitsに unit_id='{pattern_id}' が見つかりません(スキップ)")
            skipped_count += len(rows)
            continue

        ku_row = ku_map[pattern_id]
        row_id = ku_row["row"]
        old_values = dict(ku_row["values"])

        # reproduced_count を増やす(今回処理した件数分)
        old_reproduced = int(old_values.get("reproduced_count") or 0)
        new_reproduced = old_reproduced + len(rows)

        # evidence_count と last_seen_at はそのまま維持(新しい投稿証拠ではないため)
        evidence_count = int(old_values.get("evidence_count") or 1)
        last_seen_at = old_values.get("last_seen_at") or today

        # success_rateが既にある場合は既存件数と今回件数を加重平均でマージ
        existing_rate = float(old_values.get("success_rate") or 0.0)
        if existing_rate > 0.0 and old_reproduced > 0:
            merged_rate = (existing_rate * old_reproduced + new_rate * len(rows)) / new_reproduced
            new_rate = round(merged_rate, 3)

        new_confidence = _calc_confidence(evidence_count, last_seen_at, today, new_rate)

        updated_values = dict(old_values)
        updated_values.update({
            "success_rate": new_rate,
            "confidence": round(new_confidence, 3),
            "reproduced_count": new_reproduced,
        })

        try:
            sheets_writer.update_knowledge_unit(row_id, updated_values)
            print(
                f"  ✓ {pattern_id}: success_rate={new_rate} / "
                f"confidence={round(new_confidence,3)} / reproduced={new_reproduced}"
            )
            updated_count += 1
        except Exception as e:
            print(f"  ⚠️ knowledge_unit更新失敗({pattern_id}): {e}")
            skipped_count += len(rows)
            continue

        # 5. 処理済み行の checked_at を書き込む
        for r in rows:
            try:
                sheets_writer.mark_manual_post_result_checked(r["row"], today)
            except Exception as e:
                print(f"  ⚠️ checked_at書き込み失敗(row={r['row']}): {e}")

    print(
        f"Feedback Collector: パターン更新 {updated_count}件 / "
        f"スキップ {skipped_count}件"
    )

    # ── Evidence Layer (Sprint3): MPR行をevidence_registry/linksに変換 ──────
    # 既存の処理(success_rate更新)には一切影響しない。追加処理のみ。
    _convert_mpr_to_evidence(unprocessed, today)
