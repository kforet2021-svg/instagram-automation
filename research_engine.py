"""
research_engine.py

【2026-07-04(6回目)】互換シム化。
Sprint2設計レビュー(Sprint2_設計レビュー.md ①)で合意した方針に基づき、本体は
creator_intelligence/research/ 配下(base.py / providers/ / engine.py)へ移設した。

このファイルは旧パス(`from research_engine import ...`)で参照している
prompts.py・sheets_writer.pyのコードを変更せずに動かすための薄い互換シムであり、
実際のロジックは一切持たない。新しいコードはこのファイルではなく
creator_intelligence.research.engine を直接importすること。

main.pyはこのモジュールを直接importしていない(prompts.py / sheets_writer.py経由
でのみ使われる)ため、本シム化はmain.pyの動作に影響しない。
"""

from creator_intelligence.research.base import ResearchProvider
from creator_intelligence.research.providers.meta_official import MetaOfficialProvider
from creator_intelligence.research.providers.instagram_official import InstagramOfficialProvider
from creator_intelligence.research.providers.company_ir import CompanyIRProvider
from creator_intelligence.research.providers.marketing_article import MarketingArticleProvider
from creator_intelligence.research.providers.note import NoteProvider
from creator_intelligence.research.providers.x import XProvider
from creator_intelligence.research.providers.news import NewsProvider
from creator_intelligence.research.providers.academic_paper import AcademicPaperProvider
from creator_intelligence.research.engine import (
    PRIORITY_ORDER,
    gather_evidence_for_post,
    build_evidence_summary_text,
)

__all__ = [
    "ResearchProvider",
    "MetaOfficialProvider",
    "InstagramOfficialProvider",
    "CompanyIRProvider",
    "MarketingArticleProvider",
    "NoteProvider",
    "XProvider",
    "NewsProvider",
    "AcademicPaperProvider",
    "PRIORITY_ORDER",
    "gather_evidence_for_post",
    "build_evidence_summary_text",
]
