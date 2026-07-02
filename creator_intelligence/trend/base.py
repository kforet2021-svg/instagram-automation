"""
creator_intelligence/trend/base.py

Trend Intelligence — Layer 2

【設計思想】
「プラットフォーム上で何が伸びているか」を構造として抽出するレイヤー。

重要な制約:
  - このレイヤーはコンテンツの「内容」を渡さない。
  - 「構造・フック型・CTA型・心理トリガー・投稿パターン」のみを抽出する。
  - 内容（専門知識・セリフ）は Vertical（ブランド）の知識ベースから来る。
  - これが「他サロンとの差別化」を維持する設計上の核心。

【現状】
Instagram = bright_data_fetcher.py + research_candidate_score.py が実装済み。
他プラットフォームは TrendProvider のスタブのみ。

【プロバイダ追加方法】
  1. TrendProvider を継承したクラスを trend/providers/ に作る
  2. fetch() を実装する（プラットフォームのAPIを叩くか、スクレイピングする）
  3. TrendIntelligence.providers に登録する
  → main.py / bright_data_fetcher.py の変更は不要
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TrendSignal:
    """
    「伸びているコンテンツ」の構造的な1単位。

    platform:
      instagram / tiktok / youtube_shorts / threads / x /
      google_trends / news / seasonal / market

    content_type:
      reel / post / short / thread / tweet / search / article

    構造情報（内容は含まない）:
      hook_type     — 疑問形 / 逆説 / 数字 / ストーリー / ショック / リスト
      cta_type      — 保存 / フォロー / コメント / プロフクリック / シェア
      structure     — 構成の流れ（例: 疑問提示→3ステップ→保存CTA）
      trigger       — 心理トリガー（例: 情報ギャップ / 損失回避 / 社会的証明）
      duration_sec  — 動画の場合の秒数
      engagement_score — エンゲージメント推定スコア（プラットフォーム間で正規化）
    """
    signal_id:        str
    platform:         str
    content_type:     str
    hook_type:        str = ""
    cta_type:         str = ""
    structure:        str = ""
    trigger:          str = ""
    duration_sec:     int = 0
    engagement_score: float = 0.0          # 0.0〜100.0（正規化済み）
    date:             str = ""
    source_url:       str = ""
    society_tags:     list = field(default_factory=list)  # SocietySignal との関連タグ
    raw:              dict = field(default_factory=dict)


class TrendProvider(ABC):
    """
    単一プラットフォームのトレンドを TrendSignal として返す抽象クラス。

    実装済みプロバイダ（既存コードのラッパー）:
      InstagramProvider — bright_data_fetcher + research_candidate_score を委譲

    実装予定プロバイダ:
      TikTokProvider
      YouTubeShortsProvider
      ThreadsProvider
      XProvider
      GoogleTrendsProvider
      NewsProvider（SocietyIntelligence と共有も可）
      SeasonalProvider
    """

    platform: str = ""  # サブクラスで上書き

    @abstractmethod
    def fetch(self, date: str, society_signals: Optional[list] = None) -> list:
        """
        TrendSignal のリストを返す。

        Args:
            date:            "YYYY-MM-DD"
            society_signals: SocietyIntelligence から受け取ったシグナル（任意）。
                             ソーシャルトレンドと社会的文脈を照合する用途。
        Returns:
            [TrendSignal, ...]
        """

    def is_available(self) -> bool:
        """APIキーや認証情報が設定済みか確認する。Falseなら fetch() は呼ばれない。"""
        return False  # デフォルトは未実装（スタブ）


class TrendIntelligence:
    """
    全プラットフォームの TrendProvider を束ねる集約クラス。

    is_available() == True のプロバイダのみ fetch() を呼ぶ。
    未実装のプロバイダはスキップ（エラーにならない）。

    Learning Engine はこのクラスから TrendSignal を受け取り、
    KnowledgeUnit（成功パターン）への変換・蓄積を行う。
    """

    def __init__(self, providers: Optional[list] = None):
        self.providers: list = providers or []

    def register(self, provider: TrendProvider) -> None:
        self.providers.append(provider)

    def fetch_all(self, date: str, society_signals: Optional[list] = None) -> list:
        """
        利用可能な全プロバイダからトレンドを収集し、
        engagement_score 降順で返す。
        """
        signals = []
        for p in self.providers:
            if not p.is_available():
                continue
            try:
                signals.extend(p.fetch(date, society_signals))
            except Exception as e:
                print(f"  [TrendIntelligence] {p.__class__.__name__} 取得エラー: {e}")
        signals.sort(key=lambda s: s.engagement_score, reverse=True)
        return signals

    def available_platforms(self) -> list:
        return [p.platform for p in self.providers if p.is_available()]

    def to_pattern_summary(self, signals: list, top_n: int = 10) -> str:
        """
        上位N件を Learning Engine に渡せる構造サマリーテキストに変換する。
        内容（キーワード・セリフ）は含まない。
        """
        if not signals:
            return ""
        lines = ["【プラットフォームトレンド構造】"]
        for s in signals[:top_n]:
            lines.append(
                f"・[{s.platform}] hook={s.hook_type} / cta={s.cta_type}"
                f" / trigger={s.trigger} / score={s.engagement_score:.1f}"
            )
        return "\n".join(lines)
