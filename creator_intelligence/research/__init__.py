"""
creator_intelligence.research パッケージ。

【2026-07-04(6回目)新設】
旧research_engine.py(1ファイルにResearchProvider抽象クラス・8つの具象プロバイダ・
優先順位ロジック・gather_evidence_for_post/build_evidence_summary_textをすべて
まとめていた)を、以下の3層に分離した。

- base.py     : ResearchProviderの抽象基底クラス
- providers/  : 優先順位①〜⑧の8つの具象プロバイダ(1ファイル1プロバイダ)
- engine.py   : PRIORITY_ORDER(優先順位一覧)・gather_evidence_for_post・
                build_evidence_summary_text(呼び出し側が実際に使う2関数)

呼び出し側(prompts.py、sheets_writer.py)がimportしてよいのは、
creator_intelligence.research.engine の gather_evidence_for_post と
build_evidence_summary_text の2関数のみ(個々のプロバイダクラスや
PRIORITY_ORDERの実体に直接依存させない)。これにより、将来9番目の情報源を
追加する作業は「providers/に新しいファイルを1つ追加し、engine.pyの一覧に
1行加える」だけで完了し、呼び出し側のコードは一切変更不要になる
(Sprint2_設計レビュー.md ①の方針)。
"""
