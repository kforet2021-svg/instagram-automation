"""
creator_intelligence パッケージ。

【2026-07-04(6回目)新設】
Creator Intelligence Sprint 2の設計レビュー(Sprint2_設計レビュー.md)で合意した
方針に基づき、段階的にコードをこの配下へ移していくためのパッケージ。
「いきなり全部移動せず、動作確認しながら進める」というユーザー指示に従い、
最初の移設対象はresearch_engine.py(creator_intelligence.research.engine)のみ。

ルート直下のmain.pyは変更しない(`python3 main.py`が今までと同じ動作をすることを
最優先する)。ルートの各モジュール(research_engine.py等)は、移設後は
creator_intelligence配下の実体へ委譲する薄い互換シムとして残す。
"""
