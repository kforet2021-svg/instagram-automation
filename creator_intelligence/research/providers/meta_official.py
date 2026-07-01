"""優先順位① Meta公式情報。【2026-07-04(6回目)】旧research_engine.pyから移設。"""

from creator_intelligence.research.base import ResearchProvider


class MetaOfficialProvider(ResearchProvider):
    name = "Meta公式情報"
    priority = 1
