"""優先順位⑧ 論文。【2026-07-04(6回目)】旧research_engine.pyから移設。"""

from creator_intelligence.research.base import ResearchProvider


class AcademicPaperProvider(ResearchProvider):
    name = "論文"
    priority = 8
