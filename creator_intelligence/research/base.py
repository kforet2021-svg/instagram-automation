"""
creator_intelligence.research.base

【2026-07-04(6回目)】
旧research_engine.py内にあったResearchProvider抽象基底クラスをそのまま移設した
ファイル。ロジックは一切変更していない(searchはデフォルトで空リストを返す
=実際の外部検索を行わないスタブ)。
"""


class ResearchProvider:
    """
    リサーチ情報源の抽象基底クラス。

    2026年時点では.envに検索APIキー(Google Custom Search、Bing、SerpAPI等)が
    存在しないため、search()は常に空リストを返すスタブとして扱う
    (AskUserQuestionでユーザーが確認・承認済みの方針: Research Engineは
    「フレームワークのみ」を先に作り、実際の外部検索接続は将来キーが
    用意された時点で個別プロバイダのsearch()を実装する)。
    """

    name = "未設定"
    priority = 99

    def search(self, query: str) -> list:
        return []
