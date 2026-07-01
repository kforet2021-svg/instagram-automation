"""優先順位③ 企業IR。【2026-07-04(6回目)】旧research_engine.pyから移設。"""

from creator_intelligence.research.base import ResearchProvider


class CompanyIRProvider(ResearchProvider):
    name = "企業IR"
    priority = 3
