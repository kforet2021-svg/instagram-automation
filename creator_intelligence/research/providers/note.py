"""優先順位⑤ note。【2026-07-04(6回目)】旧research_engine.pyから移設。"""

from creator_intelligence.research.base import ResearchProvider


class NoteProvider(ResearchProvider):
    name = "note"
    priority = 5
