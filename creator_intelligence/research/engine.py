"""
creator_intelligence.research.engine

【2026-07-04(6回目)】
旧research_engine.py(ResearchProvider抽象クラス・8具象プロバイダ・優先順位ロジック・
gather_evidence_for_post/build_evidence_summary_textを1ファイルに集約していたもの)を
3層構造へ分離した際の、呼び出し側が実際にimportする「公開面」。

- 8つの具象プロバイダの実体はcreator_intelligence.research.providers配下に分離した。
- このファイルはPRIORITY_ORDER(優先順位順のプロバイダインスタンス一覧)と、
  実際に呼び出される2関数(gather_evidence_for_post、build_evidence_summary_text)
  のみを持つ。

ロジックは旧research_engine.pyと完全に同一(動作を変えていない)。

【2026-07-05: Trend Score → Research Candidate Scoreへのリネームに追従】
trend_score.pyがresearch_candidate_score.pyへリネームされたことに伴い、
gather_evidence_for_postが読む入力キーをpost["trend_score"]からpost["research_
candidate_score"]に変更し、生成する「一次情報(投稿実測値)」エビデンスの「概要」
テキストも「Research Candidate Score N点」に更新した。エビデンス収集ロジック
(プロバイダの呼び出し順・件数)自体は変更していない。
"""

import datetime

from creator_intelligence.research.providers.meta_official import MetaOfficialProvider
from creator_intelligence.research.providers.instagram_official import InstagramOfficialProvider
from creator_intelligence.research.providers.company_ir import CompanyIRProvider
from creator_intelligence.research.providers.marketing_article import MarketingArticleProvider
from creator_intelligence.research.providers.note import NoteProvider
from creator_intelligence.research.providers.x import XProvider
from creator_intelligence.research.providers.news import NewsProvider
from creator_intelligence.research.providers.academic_paper import AcademicPaperProvider

PRIORITY_ORDER = [
    MetaOfficialProvider(),
    InstagramOfficialProvider(),
    CompanyIRProvider(),
    MarketingArticleProvider(),
    NoteProvider(),
    XProvider(),
    NewsProvider(),
    AcademicPaperProvider(),
]


def _today_str() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def gather_evidence_for_post(post: dict) -> list:
    """
    投稿1件分のリサーチ根拠(エビデンス)リストを返す。

    2026-07-04時点では各プロバイダのsearch()は常に空リストを返すスタブのため、
    実質的に返るのは「一次情報(投稿実測値)」エントリ1件のみ(post自身のResearch
    Candidate Score実測値から組み立てるもので、外部情報の創作・捏造は行わない)。
    将来いずれかのプロバイダに実検索を実装すれば、そのプロバイダの結果が
    このリストに自然に積み上がる。
    """
    post = post or {}
    evidence = []
    for provider in PRIORITY_ORDER:
        try:
            results = provider.search(post.get("username", "")) or []
        except Exception:
            results = []
        evidence.extend(results)

    breakdown = ((post.get("research_candidate_score") or {}).get("breakdown")) or {}
    breakdown_text = " / ".join(f"{k}{v}点" for k, v in breakdown.items()) or "(内訳なし)"
    total = (post.get("research_candidate_score") or {}).get("total", "不明")

    evidence.append({
        "出典名": "一次情報(投稿実測値)",
        "URL": post.get("url", ""),
        "概要": f"Research Candidate Score {total}点 [内訳: {breakdown_text}]",
        "取得日": _today_str(),
    })
    return evidence


def build_evidence_summary_text(post: dict) -> str:
    """gather_evidence_for_postの結果を、プロンプト埋め込み用のテキストに整形する。"""
    evidence = gather_evidence_for_post(post)
    lines = [f"  ・[{e['出典名']}] {e['概要']}" for e in evidence]
    return "\n".join(lines)
