"""優先順位④ マーケティング記事。【2026-07-04(6回目)】旧research_engine.pyから移設。"""

from creator_intelligence.research.base import ResearchProvider


class MarketingArticleProvider(ResearchProvider):
    name = "マーケティング記事"
    priority = 4
