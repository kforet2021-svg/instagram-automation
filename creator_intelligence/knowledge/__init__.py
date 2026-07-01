"""
creator_intelligence.knowledge パッケージ。

【2026-07-04(6回目)新設】
Sprint2設計レビュー(Sprint2_設計レビュー.md ②)で合意した「Knowledge Store抽象化」
を実装するパッケージ。knowledge_registry.pyの重複排除ロジック(ビジネスロジック)
と、実際の保存先(現状はGoogle Sheets、将来はSQLite等のDBに置き換え可能)を
分離するための薄いインターフェース層。

- base.py         : KnowledgeStore抽象基底クラス(all/append/updateの3メソッド)
- sheets_store.py : 現状の実装(sheets_writer.pyのknowledge_library用関数への
                    薄いラッパー)

将来Sheets以外(SQLite等)に移行する場合は、KnowledgeStoreを継承した新しい
クラス(例: SqliteKnowledgeStore)をこのパッケージに追加し、knowledge_registry.py
側の `_store = SheetsKnowledgeStore()` の1行を差し替えるだけでよい
(knowledge_registry.pyの重複判定・更新ロジックは一切変更不要)。
"""
