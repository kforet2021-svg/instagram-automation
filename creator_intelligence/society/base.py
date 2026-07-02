"""
creator_intelligence/society/base.py

Society Intelligence — Layer 1

【設計思想】
「世の中の流れ」を構造化するレイヤー。
ニュース・季節・経済・AIトレンド・市場データなど、
プラットフォーム横断の社会的文脈を SocietySignal として返す。

Trend Intelligence（Layer 2）はこの信号を受け取り、
各プラットフォームの伸びているコンテンツと照合する。

【現状】
未実装。設計のみ。
将来の実装者は SocietyProvider を継承し、
collect() を実装すれば自動的にパイプラインに組み込まれる。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SocietySignal:
    """
    社会的文脈の1単位。

    source_type:
      news         — ニュース記事・報道
      seasonal     — 季節・年中行事・記念日
      market       — 市場データ・経済指標
      ai_trend     — AI・テクノロジートレンド
      google_trend — Google検索トレンド
      event        — 社会イベント（選挙・災害・スポーツ等）

    relevance_score: 0.0〜1.0（このシグナルが専門家コンテンツに関係する度合い）
    """
    signal_id:       str
    source_type:     str                    # news / seasonal / market / ai_trend / google_trend / event
    title:           str                    # シグナルの要約タイトル
    summary:         str                    # 詳細サマリー
    keywords:        list = field(default_factory=list)  # 関連キーワード
    relevance_score: float = 0.0           # 0.0〜1.0
    date:            str = ""              # YYYY-MM-DD
    source_url:      str = ""
    raw:             dict = field(default_factory=dict)  # プロバイダが返す生データ


class SocietyProvider(ABC):
    """
    SocietySignal を収集する単一ソースの抽象クラス。

    新しい情報源を追加するには:
      1. このクラスを継承する
      2. collect() を実装する
      3. SocietyIntelligence.providers に登録する
    """

    @abstractmethod
    def collect(self, date: str, vertical_keywords: list) -> list:
        """
        指定日の SocietySignal リストを返す。

        Args:
            date:              "YYYY-MM-DD"
            vertical_keywords: Vertical固有のキーワード（例: ["小顔", "エステ", "顔筋"]）
                               これを使ってソースをフィルタリングする。
        Returns:
            [SocietySignal, ...]
        """


class SocietyIntelligence:
    """
    全 SocietyProvider を束ねる集約クラス。

    今後追加予定のプロバイダ:
      - NewsProvider        — RSS/ニュースAPI（NewsAPI等）
      - SeasonalProvider    — 季節カレンダー・記念日DB
      - GoogleTrendProvider — Google Trends API（pytrends）
      - MarketProvider      — 市場データAPI（e.g. 美容業界レポート）
      - AITrendProvider     — AI/テクノロジー動向（ArXiv, HN等）
    """

    def __init__(self, providers: Optional[list] = None):
        self.providers: list = providers or []

    def register(self, provider: SocietyProvider) -> None:
        self.providers.append(provider)

    def collect_all(self, date: str, vertical_keywords: list) -> list:
        """
        全プロバイダから収集し、relevance_score の降順で返す。
        プロバイダが未登録の場合は空リストを返す（エラーではない）。
        """
        signals = []
        for provider in self.providers:
            try:
                signals.extend(provider.collect(date, vertical_keywords))
            except Exception as e:
                print(f"  [SocietyIntelligence] {provider.__class__.__name__} 収集エラー: {e}")
        signals.sort(key=lambda s: s.relevance_score, reverse=True)
        return signals

    def to_context_text(self, signals: list, top_n: int = 5) -> str:
        """
        上位N件を Trend Intelligence / Learning Engine に渡せるテキストに変換する。
        """
        if not signals:
            return ""
        lines = ["【社会的文脈】"]
        for s in signals[:top_n]:
            lines.append(f"・[{s.source_type}] {s.title} — {s.summary[:80]}")
        return "\n".join(lines)
