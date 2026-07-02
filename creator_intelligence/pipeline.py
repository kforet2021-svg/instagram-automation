"""
creator_intelligence/pipeline.py

Creator Intelligence Platform — 4レイヤーパイプライン定義

【アーキテクチャ】

  ┌─────────────────────────────────────────────────────────────┐
  │  Layer 1: Society Intelligence                               │
  │  「世の中の流れ」を構造化する                                 │
  │  Sources: News / Seasonal / Google Trends / Market / AI      │
  └──────────────────────────┬──────────────────────────────────┘
                             │  SocietySignal[]
  ┌──────────────────────────▼──────────────────────────────────┐
  │  Layer 2: Trend Intelligence                                 │
  │  「プラットフォームで何が伸びているか」を構造として抽出する    │
  │  Platforms: Instagram / TikTok / YouTube / Threads / X / ... │
  │  ※ 内容（キーワード・セリフ）は抽出しない — 構造のみ         │
  └──────────────────────────┬──────────────────────────────────┘
                             │  TrendSignal[]
  ┌──────────────────────────▼──────────────────────────────────┐
  │  Layer 3: Learning Engine                                    │
  │  「社会の文脈 × プラットフォーム構造 × 過去実績」             │
  │  → 今日作るべきコンテンツの設計図（ContentBrief）を生成      │
  └──────────────────────────┬──────────────────────────────────┘
                             │  ContentBrief
  ┌──────────────────────────▼──────────────────────────────────┐
  │  Layer 4: Creator Studio                                     │
  │  「ContentBrief × 専門家の知見（KB） × ブランド（Vertical）」 │
  │  → 今日そのまま使える撮影指示書を生成                        │
  └─────────────────────────────────────────────────────────────┘

【設計原則】

1. コンテンツの「構造」と「内容」は分離する
   - Layer 1〜3 は構造・文脈のみを扱う（「何が伸びているか」）
   - 内容（セリフ・専門知識）は Layer 4 の Vertical KB から来る
   - これが「他サロンでは言えないコンテンツ」を生む根拠

2. 各レイヤーは独立して進化できる
   - TrendProvider を増やしても Creator Studio のコードは変わらない
   - Vertical（ブランド）を増やしても Trend Intelligence は変わらない
   - DB（Sheets→SQLite）を変えても Learning Engine の IF は変わらない

3. 段階的実装
   - 現在: Instagram（Layer2）のみ実装済み
   - Layer1（Society）・Layer2他プラットフォーム・Layer3本実装 は順次追加
   - 未実装プロバイダは is_available()=False で自動スキップ（エラーなし）

【現状の実装状況（2026-07-02）】

  Layer 1: Society Intelligence ── 未実装（インターフェース定義のみ）
  Layer 2: Trend Intelligence
    - Instagram ─────────────── 実装済み（bright_data_fetcher.py）
    - TikTok ────────────────── スタブ（is_available=False）
    - YouTube Shorts ─────────── スタブ（is_available=False）
    - Threads / X / Google ──── スタブ（is_available=False）
  Layer 3: Learning Engine ──── 部分実装
    - KnowledgeUnit 蓄積 ─────── 実装済み（knowledge_registry.py）
    - ContentBrief 生成 ──────── creator_studio.py Priority1〜4 が代行
    - パフォーマンス記録 ─────── 未実装
  Layer 4: Creator Studio ────── 実装済み（creator_studio.py）

【次の実装候補】

  - [ ] GoogleTrendProvider — pytrends で美容・小顔ワードのトレンド取得
  - [ ] SeasonalProvider   — 季節・記念日カレンダー（乾燥注意期、紫外線期等）
  - [ ] LearningEngine 本実装 — ContentBrief 生成を creator_studio から分離
  - [ ] パフォーマンス記録 — 投稿後フォロワー数をフィードバック
  - [ ] TikTokProvider     — Bright Data TikTok スクレーパー
"""

from typing import Optional

from creator_intelligence.society.base  import SocietyIntelligence
from creator_intelligence.trend.base    import TrendIntelligence
from creator_intelligence.learning.base import LearningEngine, ContentBrief
from creator_intelligence.platform.vertical_base import VerticalBase


class CreatorIntelligencePipeline:
    """
    4レイヤーを束ねるオーケストレーター。

    現在は未実装（設計定義のみ）。
    将来的に main.py の run_pipeline() から呼ばれる想定。

    使用例（将来):
        pipeline = CreatorIntelligencePipeline(
            society=society_intel,
            trend=trend_intel,
            learning=learning_engine,
            vertical=core_hari_vertical,
        )
        brief = pipeline.run(date="2026-07-02")
        # creator_studio.py はこの brief を受け取って撮影指示書を生成する
    """

    def __init__(
        self,
        society:  Optional[SocietyIntelligence] = None,
        trend:    Optional[TrendIntelligence]   = None,
        learning: Optional[LearningEngine]      = None,
        vertical: Optional[VerticalBase]        = None,
    ):
        self.society  = society  or SocietyIntelligence()
        self.trend    = trend    or TrendIntelligence()
        self.learning = learning
        self.vertical = vertical

    def run(self, date: str) -> Optional[ContentBrief]:
        """
        パイプラインを実行して ContentBrief を返す。

        Layer 1: 社会シグナル収集
        Layer 2: プラットフォームトレンド収集
        Layer 3: ContentBrief 生成
        Layer 4: Creator Studio（呼び出し元が担当）
        """
        # Layer 1
        vertical_kw = []
        if self.vertical:
            rules = self.vertical.brand_rules()
            vertical_kw = rules.target.split("、") if rules else []
        society_signals = self.society.collect_all(date, vertical_kw)

        # Layer 2
        trend_signals = self.trend.fetch_all(date, society_signals)

        # Layer 3
        if self.learning is None or self.vertical is None:
            return None
        brief = self.learning.generate_brief(
            date, society_signals, trend_signals, self.vertical
        )
        return brief

    def status(self) -> dict:
        """現在のパイプライン稼働状況を返す（デバッグ用）。"""
        return {
            "society_providers":           len(self.society.providers),
            "trend_available_platforms":   self.trend.available_platforms(),
            "trend_all_platforms":         [p.platform for p in self.trend.providers],
            "learning_engine":             type(self.learning).__name__ if self.learning else "未実装",
            "vertical":                    type(self.vertical).__name__ if self.vertical else "未設定",
        }
