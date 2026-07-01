"""
creator_intelligence/verticals/core_hari/kb.py

CORE HARI FACE の Knowledge Base — Vertical 実装。

core_hari_kb シートを唯一の知識源として扱う。
VerticalBase の KB インターフェースを sheets_writer 経由で実装する。

【運用ルール】
- KB への記入はオーナー（CORE HARI スタッフ）が行う。
- AIが自動生成した内容を直接 fact に入れない。
- verified=yes に変更してから初めて Creator Studio がコンテンツ生成に使う。
- Knowledge Gap で提案されたエントリは verified=no で自動追記される。
"""

import datetime
import sys

# sheets_writer はプロジェクトルートにあるため sys.path 調整不要（main.py 経由で呼ばれる）
import sheets_writer
from creator_intelligence.platform.vertical_base import KBEntry, VerticalBase, BrandRules
from creator_intelligence.verticals.core_hari.config import CORE_HARI_BRAND_RULES
from creator_intelligence.verticals.core_hari.structure_patterns import CORE_HARI_STRUCTURE_PATTERNS


class CoreHariVertical(VerticalBase):
    """
    CORE HARI FACE — Creator Intelligence Platform First Vertical。

    Creator Studio はこのクラスのインスタンスを受け取るだけでよい。
    KB の場所・ブランドルール・構造パターンの詳細はここに閉じている。
    """

    vertical_id = "core_hari"
    display_name = "CORE HARI FACE（札幌）"

    # ── ブランドルール ─────────────────────────────────────────────

    def brand_rules(self) -> BrandRules:
        return CORE_HARI_BRAND_RULES

    # ── Knowledge Base ─────────────────────────────────────────────

    def get_kb_entries(self) -> list:
        """
        core_hari_kb シートから全エントリを読み込んで KBEntry に変換する。
        verified=yes のエントリのみ返す（verified=no は候補段階）。
        シートが空または読み込み失敗の場合は空リストを返す。
        """
        try:
            rows = sheets_writer.get_core_hari_kb()
        except Exception as e:
            print(f"  ⚠️ core_hari_kb 読み込み失敗: {e}")
            return []

        entries = []
        for r in rows:
            v = r["values"]
            fact = (v.get("fact") or "").strip()
            topic = (v.get("topic") or "").strip()
            if not fact or not topic:
                continue
            verified_raw = (v.get("verified") or "no").strip().lower()
            if verified_raw != "yes":
                continue  # 未確認エントリは使わない
            entries.append(KBEntry(
                topic=topic,
                fact=fact,
                tags=(v.get("tags") or "").strip(),
                source=(v.get("source") or "").strip(),
                verified=True,
                # Step2で使う追加フィールド（vertical_base.KBEntryに追加予定）
                # knowledge_type と content_role はここで読み込んでおく
                knowledge_type=(v.get("knowledge_type") or "").strip(),
                content_role=(v.get("content_role") or "universal").strip(),
                example_sentence=(v.get("example_sentence") or "").strip(),
            ))
        return entries

    def get_all_kb_entries_including_unverified(self) -> list:
        """
        未確認エントリも含めて全件返す（Knowledge Gap 重複チェック用）。
        """
        try:
            rows = sheets_writer.get_core_hari_kb()
        except Exception:
            return []
        topics = set()
        for r in rows:
            t = (r["values"].get("topic") or "").strip()
            if t:
                topics.add(t)
        return list(topics)

    def append_kb_gap_candidates(self, entries: list) -> None:
        """
        Knowledge Gap で提案された候補を core_hari_kb に追記する。
        既に同じ topic が存在する場合はスキップする（重複防止）。
        entries: [{"topic": ..., "fact": ..., "tags": ..., "source": ..., "verified": "no"}, ...]
        """
        existing_topics = set(self.get_all_kb_entries_including_unverified())
        today = datetime.date.today().isoformat()

        new_entries = []
        for e in entries:
            topic = (e.get("topic") or "").strip()
            if topic and topic not in existing_topics:
                new_entries.append({
                    "topic":    topic,
                    "fact":     e.get("fact", "（ここに実際の知識を記入してください）"),
                    "tags":     e.get("tags", ""),
                    "source":   "Knowledge Gap 自動提案",
                    "added_at": today,
                    "verified": "no",
                })
                existing_topics.add(topic)

        if new_entries:
            try:
                sheets_writer.append_core_hari_kb_entries(new_entries)
                print(f"  KB Gap候補 {len(new_entries)}件を core_hari_kb に追記しました（verified=no）")
            except Exception as e:
                print(f"  ⚠️ KB Gap候補の追記失敗: {e}")
        return

    # ── 構造パターン ──────────────────────────────────────────────

    def get_structure_patterns(self) -> list:
        return CORE_HARI_STRUCTURE_PATTERNS
