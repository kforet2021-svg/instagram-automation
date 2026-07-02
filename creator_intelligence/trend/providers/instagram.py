"""
creator_intelligence/trend/providers/instagram.py

Instagram TrendProvider — 実装済みプロバイダ（既存コードへの委譲）

【現状】
実際の処理は以下の既存モジュールが担当:
  - bright_data_fetcher.py    — Bright Data 経由の投稿取得
  - research_candidate_score.py — Research Candidate Score 算出

このクラスは将来的に TrendIntelligence.fetch_all() から呼ばれる
ラッパー（アダプター）として機能する。
現時点では main.py から直接 bright_data_fetcher を呼んでいるため、
このクラスは設計定義のみ（未接続）。
"""

from creator_intelligence.trend.base import TrendProvider, TrendSignal


class InstagramTrendProvider(TrendProvider):
    """
    Instagram Reels・投稿トレンドを TrendSignal に変換する。

    実装時:
      fetch() 内で bright_data_fetcher.build_post_pool() を呼び、
      research_candidate_score.score_post() でスコア算出後、
      TrendSignal に変換して返す。
    """

    platform = "instagram"

    def is_available(self) -> bool:
        # 環境変数 BRIGHT_DATA_API_KEY が設定済みならTrue
        import os
        return bool(os.getenv("BRIGHT_DATA_API_KEY") or os.getenv("BRIGHT_DATA_USERNAME"))

    def fetch(self, date: str, society_signals=None) -> list:
        # TODO: bright_data_fetcher.build_post_pool() → TrendSignal 変換
        # 現在は main.py が直接 bright_data_fetcher を呼んでいるため未接続
        return []


class TikTokTrendProvider(TrendProvider):
    """
    TikTok 動画トレンドを TrendSignal に変換する。

    実装時:
      TikTok Research API または Bright Data の TikTok スクレーパーを使用。
      hook_type / structure / engagement_score を抽出して返す。
    """

    platform = "tiktok"

    def is_available(self) -> bool:
        import os
        return bool(os.getenv("TIKTOK_API_KEY"))

    def fetch(self, date: str, society_signals=None) -> list:
        # TODO: TikTok API / Bright Data TikTok scraper
        return []


class YouTubeShortsProvider(TrendProvider):
    """
    YouTube Shorts トレンドを TrendSignal に変換する。

    実装時:
      YouTube Data API v3 を使用。
      category=People&Blogs / Beauty&Fashion でフィルタリング。
    """

    platform = "youtube_shorts"

    def is_available(self) -> bool:
        import os
        return bool(os.getenv("YOUTUBE_API_KEY"))

    def fetch(self, date: str, society_signals=None) -> list:
        # TODO: YouTube Data API v3
        return []


class ThreadsTrendProvider(TrendProvider):
    """Threads 投稿トレンド（現在APIなし、将来的にMeta Graph API経由）"""

    platform = "threads"

    def is_available(self) -> bool:
        return False  # Meta Graph API の Threads 対応待ち

    def fetch(self, date: str, society_signals=None) -> list:
        return []


class XTrendProvider(TrendProvider):
    """X（旧Twitter）トレンド（X API v2 Basic/Pro）"""

    platform = "x"

    def is_available(self) -> bool:
        import os
        return bool(os.getenv("X_BEARER_TOKEN"))

    def fetch(self, date: str, society_signals=None) -> list:
        # TODO: X API v2 search_recent_tweets + engagement metrics
        return []


class GoogleTrendProvider(TrendProvider):
    """
    Google 検索トレンド（pytrends）。

    実装時:
      pytrends.build_payload() で Vertical キーワードのトレンドを取得。
      SocietySignal と組み合わせて "今週急上昇の検索語" を TrendSignal として返す。
    """

    platform = "google_trends"

    def is_available(self) -> bool:
        try:
            import pytrends  # noqa: F401
            return True
        except ImportError:
            return False

    def fetch(self, date: str, society_signals=None) -> list:
        # TODO: pytrends + Vertical キーワードでトレンド抽出
        return []
