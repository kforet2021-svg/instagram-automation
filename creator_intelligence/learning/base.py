"""
creator_intelligence/learning/base.py

Learning Engine — Layer 3

【設計思想】
Society Intelligence（世の中の流れ）と
Trend Intelligence（プラットフォーム構造）を受け取り、
「今日この専門家が作るべきコンテンツの設計図」を出力するレイヤー。

Learning Engine の役割:
  1. TrendSignal を KnowledgeUnit（再利用可能な成功パターン）に変換・蓄積
  2. 過去の投稿実績から「何が効いたか」を学習
  3. SocietySignal × TrendSignal × 過去実績 → ContentBrief を生成
  4. Vertical の Knowledge Base と照合し、「今日話せる内容」を特定

【現状】
既存の knowledge_registry.py / knowledge_library (Sheets) が部分的に担当。
ContentBrief 生成は creator_studio.py の Priority1〜4 フォールバックが担当。
このクラスはそれらを統合するための設計定義（未実装）。

【KnowledgeUnit との違い】
KnowledgeUnit = 「何が伸びたか」の構造的な記録（content free）
ContentBrief  = 「今日作るべきコンテンツ」の設計図（Vertical固有の内容を含む）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ContentBrief:
    """
    Learning Engine が Creator Studio に渡す「今日の制作指示書の種」。

    Vertical（ブランド）固有の内容（セリフ・台本）はここに含まない。
    「何をテーマに、どんな構造で、誰の感情に刺さる投稿を作るか」の設計図。

    Creator Studio はこれを受け取り、
    Vertical の Knowledge Base からコンテンツを肉付けして撮影指示書を完成させる。
    """
    brief_id:         str

    # ── 文脈（どんな社会・プラットフォーム状況から来ているか）──────────
    society_context:  str = ""    # SocietySignal の要約テキスト
    trend_pattern:    str = ""    # TrendSignal の構造サマリー

    # ── テーマ・ゴール ────────────────────────────────────────────────
    theme:            str = ""    # 投稿テーマ（例: 「咬筋優位と顔の歪み」）
    follower_goal:    str = ""    # なぜフォローしたくなるか
    audience_emotion: str = ""    # 視聴者の悩み・感情

    # ── 構造設計（内容を含まない）─────────────────────────────────────
    hook_type:        str = ""    # 疑問形 / 逆説 / 数字 / ストーリー etc.
    structure:        str = ""    # 構成の流れ
    cta_type:         str = ""    # 保存 / フォロー / 問い合わせ
    psychology:       str = ""    # 心理トリガー
    duration_sec:     int = 0     # 目標秒数

    # ── Knowledge Base 要件 ───────────────────────────────────────────
    required_kb_tags: list = field(default_factory=list)   # 必要な KB タグ
    series_context:   str = ""    # シリーズ設計（例: 第1話 / 全3話予定）

    # ── 信頼度 ───────────────────────────────────────────────────────
    confidence:       float = 0.0  # 0.0〜1.0（高いほど優先して使う）
    source:           str = ""    # どの Priority/Intelligence から生成されたか
    date:             str = ""


@dataclass
class KnowledgeUnit:
    """
    「伸びた投稿の構造」を再利用可能な形で記録したもの。

    内容（キーワード・セリフ・ブランド名）を含まない。
    Vertical 横断で使える純粋な「コンテンツ構造パターン」。

    status:
      candidate  — 候補（Research Candidate Score が高いもの）
      validated  — 実績で効果が確認されたもの
      archived   — 古くなって使わないもの
    """
    unit_id:          str
    hook_type:        str
    structure:        str
    cta_type:         str
    psychology:       str
    platforms:        list = field(default_factory=list)  # どのプラットフォームで観測したか
    status:           str = "candidate"
    performance_avg:  float = 0.0
    usage_count:      int = 0
    last_used:        str = ""
    source_signals:   list = field(default_factory=list)  # 元の TrendSignal ID リスト


class LearningEngine(ABC):
    """
    Learning Engine 抽象基底クラス。

    今後の実装では:
      - knowledge_registry.py の重複排除ロジックをここに統合
      - creator_studio.py の Priority1〜4 フォールバックを
        ContentBrief 生成ロジックとしてここに移植
      - Google Sheets → SQLite/Supabase 移行時はこのクラスだけ差し替え
    """

    @abstractmethod
    def ingest_trend_signals(self, signals: list) -> list:
        """
        TrendSignal → KnowledgeUnit に変換して蓄積する。
        戻り値: 新規追加・更新された KnowledgeUnit のリスト
        """

    @abstractmethod
    def generate_brief(
        self,
        date: str,
        society_signals: list,
        trend_signals: list,
        vertical,              # VerticalBase インスタンス
    ) -> Optional[ContentBrief]:
        """
        今日の ContentBrief を生成して返す。
        データが不足している場合は None を返す（フォールバックを促す）。
        """

    @abstractmethod
    def record_performance(self, brief_id: str, metrics: dict) -> None:
        """
        投稿後のパフォーマンス（フォロワー増加数・保存数等）を記録する。
        これが「Learning」の実体 — 実績フィードバックで KnowledgeUnit を更新する。
        """
