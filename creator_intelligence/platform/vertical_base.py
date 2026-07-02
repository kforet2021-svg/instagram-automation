"""
creator_intelligence/platform/vertical_base.py

Creator Intelligence Platform — Vertical 抽象基底クラス。

このプラットフォームは「専門家の思考をAIが学ぶ」汎用エンジン。
Instagram 投稿ツールではなく、Creator Intelligence Platform。

Vertical とは「ある専門家・事業向けの知識ベース＋ブランドルール」のひとまとまり。
CORE HARI は最初の Vertical（First Vertical）。

新しい Vertical を追加するには:
  1. creator_intelligence/verticals/{vertical_id}/ ディレクトリを作る
  2. VerticalBase を継承したクラスを実装する
  3. config.py の ACTIVE_VERTICAL を変えるか、環境変数 ACTIVE_VERTICAL を設定する

分析パイプライン（Bright Data / Research Candidate Score / OpenAI Analyzer）は
Vertical に依存しない。Vertical が差し替わっても main.py と分析処理は変わらない。

# Knowledge Types（AIが学ぶ8つのカテゴリ）
  Observation   = 専門家が現場で気づいたこと
  Question      = 専門家がクライアントや読者に問いかける質問
  Evidence      = 一般的な根拠・エビデンス（論文・統計など）
  Experience    = 専門家の臨床経験・実体験
  Perspective   = 専門家独自の考え方・解釈
  Advice        = 専門家が与えるアドバイス・推奨行動
  Research      = まだ検証中の仮説・探求中のテーマ
  ContentAsset  = そのまま使えるコンテンツ素材（セリフ・例え話など）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BrandRules:
    """Vertical ごとのブランド基準。コンテンツ生成時の制約に使う。"""
    vertical_id: str
    display_name: str
    mission: str                        # Vertical の存在意義
    target: str                         # 誰に向けて発信するか
    tone: str                           # 語り口・雰囲気
    ng_words: list = field(default_factory=list)       # 使ってはいけない語
    ng_concepts: list = field(default_factory=list)    # 避けるべき概念・表現
    cta_save: str = "保存して、気になったときに読み返してください。"
    cta_follow: str = "フォローすると、毎週情報をお届けします。"
    cta_contact: str = "ご予約・ご相談はプロフィールのリンクからどうぞ。"


# 汎用 knowledge_type の有効値（全Verticalで共通）
KNOWLEDGE_TYPES = {
    "Observation":   "専門家が現場で気づいたこと",
    "Question":      "専門家がクライアント・読者に問いかける質問",
    "Evidence":      "一般的な根拠・エビデンス（論文・統計など）",
    "Experience":    "専門家の臨床経験・実体験",
    "Perspective":   "専門家独自の考え方・解釈",
    "Advice":        "専門家が与えるアドバイス・推奨行動",
    "Research":      "まだ検証中の仮説・探求中のテーマ",
    "ContentAsset":  "そのまま使えるコンテンツ素材（セリフ・例え話など）",
}

CONTENT_ROLES = {
    "hook":      "動画冒頭フックで使える",
    "body":      "本編説明・解説で使える",
    "proof":     "信頼性・根拠として使える",
    "universal": "どのパートでも使える",
}


@dataclass
class KBEntry:
    """
    Knowledge Base の1エントリ。Vertical 固有の専門知識。
    knowledge_type は KNOWLEDGE_TYPES のキーを使う（全Vertical共通）。
    content_role は CONTENT_ROLES のキーを使う。
    """
    topic: str                      # 知識のトピック
    fact: str                       # 実際の知識・事実（専門家が記載する核心）
    tags: str                       # カンマ区切りタグ（StructurePatternと対応）
    source: str                     # 出典
    verified: bool                  # オーナー確認済みか
    knowledge_type: str = "Evidence"  # KNOWLEDGE_TYPES のキー
    content_role: str = "universal"   # CONTENT_ROLES のキー
    speaker_words: str = ""         # 専門家がこの知識をどう語るか（セリフ例）


@dataclass
class StructurePattern:
    """
    Instagram から学んだ「伸びる構造」。内容（知識・セリフ）はここに書かない。
    Vertical 共通で使える純粋な構造定義。
    """
    pattern_id: str          # 一意ID（例: edu_3step）
    hook_type: str           # フックの型（例: 疑問形）
    structure: str           # 構成の流れ（例: 疑問提示→3ステップ解説→保存CTA）
    cta_type: str            # CTA の型（例: 保存）
    mission: str             # 狙い（例: 保存を狙う）
    psychology_trigger: str  # 心理トリガー（例: 情報ギャップ、損失回避）
    required_kb_tags: list   # このパターンに必要な KB タグのリスト
    proposed_kb_topics: list = field(default_factory=list)  # KB 不足時の提案候補


@dataclass
class KnowledgeGapReport:
    """KB 不足時の出力。コンテンツを生成せず、追加すべき知識候補を返す。"""
    pattern: StructurePattern
    available_kb: list          # 実際に見つかった KB エントリ
    missing_tags: list          # 見つからなかった必要タグ
    proposed_entries: list      # core_hari_kb に追記すべき候補 [{topic, fact_placeholder, tags}, ...]


class VerticalBase(ABC):
    """
    Vertical 抽象基底クラス。

    Creator Studio はこのインターフェースだけを参照する。
    Vertical の実装詳細（KB の場所・ブランドルール）は各 Vertical が持つ。
    """

    # ── 識別子（サブクラスで上書き必須）─────────────────────────────
    vertical_id: str = ""
    display_name: str = ""

    # ── ブランドルール ─────────────────────────────────────────────

    @abstractmethod
    def brand_rules(self) -> BrandRules:
        """このVerticalのブランド判断基準を返す。"""

    # ── Knowledge Base ─────────────────────────────────────────────

    @abstractmethod
    def get_kb_entries(self) -> list:
        """
        Vertical の Knowledge Base から全エントリを返す。
        戻り値: [KBEntry, ...]
        """

    def filter_kb_by_tags(self, all_entries: list, required_tags: list) -> list:
        """
        required_tags のいずれかにマッチする KB エントリを絞り込む。
        verified=True のエントリを優先する。
        """
        if not required_tags:
            return all_entries

        matched = []
        for entry in all_entries:
            entry_tags = {t.strip() for t in entry.tags.split(",")}
            if any(rt in entry_tags for rt in required_tags):
                matched.append(entry)

        # verified=True を先頭に
        matched.sort(key=lambda e: (0 if e.verified else 1))
        return matched

    def check_knowledge_gap(
        self,
        pattern: StructurePattern,
        all_kb: list,
        min_entries: int = 2,
    ) -> Optional[KnowledgeGapReport]:
        """
        パターンに必要な KB エントリが min_entries 件以上あるか確認する。
        不足なら KnowledgeGapReport を返す（充足なら None）。
        """
        relevant = self.filter_kb_by_tags(all_kb, pattern.required_kb_tags)
        if len(relevant) >= min_entries:
            return None

        # 不足しているタグを特定
        found_tags: set = set()
        for entry in relevant:
            found_tags.update(t.strip() for t in entry.tags.split(","))
        missing = [t for t in pattern.required_kb_tags if t not in found_tags]

        # 提案候補を組み立て（placeholder で返す。オーナーが記入する）
        proposals = []
        for topic in pattern.proposed_kb_topics:
            proposals.append({
                "topic": topic,
                "fact": "（専門家がここに実際の知識・事実を記入してください）",
                "tags": ",".join(pattern.required_kb_tags),
                "source": "未確認",
                "verified": "no",
            })

        return KnowledgeGapReport(
            pattern=pattern,
            available_kb=relevant,
            missing_tags=missing,
            proposed_entries=proposals,
        )

    @abstractmethod
    def append_kb_gap_candidates(self, entries: list) -> None:
        """
        Knowledge Gap で提案されたエントリを KB に追記する（verified=no で保存）。
        """

    # ── 構造パターン ──────────────────────────────────────────────

    @abstractmethod
    def get_structure_patterns(self) -> list:
        """
        この Vertical で使う StructurePattern のリストを返す。
        内容（知識・セリフ）はここに含まない。
        """

    def pick_structure_for_today(self) -> StructurePattern:
        """曜日ローテーションで今日の構造パターンを選ぶ。"""
        import datetime
        patterns = self.get_structure_patterns()
        dow = datetime.date.today().weekday()
        return patterns[dow % len(patterns)]

    # ── ブランドスコア ────────────────────────────────────────────

    def score_content(self, hook: str, cta: str, theme: str) -> tuple:
        """
        ブランドルールに基づいてコンテンツをスコアリングする。
        戻り値: (score: int, notes: str)
        """
        rules = self.brand_rules()
        combined = f"{hook} {cta} {theme}"
        hits = [w for w in rules.ng_words if w in combined]
        if not hits:
            return 88, "ブランドラインOK。投稿前に最終確認してください。"
        score = max(50, 88 - len(hits) * 10)
        return score, f"NGワード検出: {', '.join(hits)}。言い換えを検討してください。"
