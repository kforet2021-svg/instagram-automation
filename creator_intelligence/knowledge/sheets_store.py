"""
creator_intelligence.knowledge.sheets_store

【2026-07-04(6回目)新設】
KnowledgeStoreのGoogle Sheets実装。実際の読み書きはすべてsheets_writer.pyの
既存関数(get_knowledge_library_rows / append_knowledge_library_row /
update_knowledge_library_row)に委譲する薄いラッパーであり、Sheets固有のAPI呼び出し
(gspreadのworksheet操作等)はsheets_writer.py側に閉じたまま変更していない。

将来SQLite等のDBへ移行する場合は、creator_intelligence.knowledge.baseの
KnowledgeStoreを継承した別クラス(例: SqliteKnowledgeStore)を新設し、
sheets_writer.get_knowledge_library_rows等と同等の役割を持つDBアクセス関数を
そちらで実装すればよい(本クラス・knowledge_registry.pyのロジックには手を入れない)。
"""

import sheets_writer
from creator_intelligence.knowledge.base import KnowledgeStore


class SheetsKnowledgeStore(KnowledgeStore):
    """knowledge_libraryシートをバックエンドとするKnowledgeStore実装。"""

    def all(self) -> list:
        rows = sheets_writer.get_knowledge_library_rows()
        return [{"id": r["row"], "values": r["values"]} for r in rows]

    def append(self, values: dict) -> None:
        sheets_writer.append_knowledge_library_row(values)

    def update(self, record_id, values: dict) -> None:
        sheets_writer.update_knowledge_library_row(record_id, values)
