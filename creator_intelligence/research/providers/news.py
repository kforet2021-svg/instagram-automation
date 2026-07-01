"""優先順位⑦ ニュース。【2026-07-04(6回目)】旧research_engine.pyから移設。"""

from creator_intelligence.research.base import ResearchProvider


class NewsProvider(ResearchProvider):
    name = "ニュース"
    priority = 7
