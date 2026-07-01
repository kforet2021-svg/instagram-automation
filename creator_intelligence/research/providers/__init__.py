"""
creator_intelligence.research.providers パッケージ。

優先順位①〜⑧の8つの具象ResearchProviderを、1ファイル1プロバイダで管理する。
各ファイルはcreator_intelligence.research.baseのResearchProviderを継承するだけの
小さなクラス定義のみを持つ(2026-07-04時点ではsearch()は基底クラスのデフォルト
(空リストを返す)のままで、実際の外部検索は行わない)。

将来、いずれかのプロバイダに実際の検索APIを実装する際は、対応するファイルの
search()メソッドだけをオーバーライドすればよい(他のプロバイダ・呼び出し側
(engine.py以降)には影響しない)。
"""
