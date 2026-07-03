"""
creator_intelligence/layers/layer5_content/engine.py

Layer 5: Content Engine
Layer1〜4を統合し、各プラットフォーム向けコンテンツを一括生成する。

【鉄則】
  - 各プラットフォームのコンテンツは独自に生成する
  - 「Instagramの文章をThreadsへ流用」は絶対禁止
  - 「Threadsの考え方をInstagramへ流用」も絶対禁止
  - PlatformDNA を必ず参照して生成する

生成フロー:
  Layer4（専門家の思考）
    ↓ テーマ×思考タイプでマッチング
  Layer3（Platform Engine）× 5プラットフォーム
    ↓ それぞれ独自のDNAで独立生成
  Layer5（Content Engine）
    ↓ プラットフォームごとのコンテンツをパッケージ化
  出力: MultiPlatformPackage

【2026-07-03(1回目): 新規作成。】
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from ..layer3_platform.base import PlatformContent
from ..layer3_platform.instagram import InstagramEngine
from ..layer3_platform.threads import ThreadsEngine
from ..layer3_platform.tiktok import TikTokEngine
from ..layer3_platform.youtube import YouTubeEngine
from ..layer3_platform.x import XEngine

# 全プラットフォームエンジン
_ENGINES = {
    "instagram": InstagramEngine(),
    "threads":   ThreadsEngine(),
    "tiktok":    TikTokEngine(),
    "youtube":   YouTubeEngine(),
    "x":         XEngine(),
}

# プラットフォームの表示順
PLATFORM_ORDER = ["instagram", "threads", "tiktok", "youtube", "x"]


@dataclass
class MultiPlatformPackage:
    """
    1つのテーマ × 専門家の思考から生成された全プラットフォームパッケージ。

    各プラットフォームのコンテンツは独立生成されており、
    流用・コピーを一切含まない。
    """
    theme: str
    date: str
    intelligence: dict          # Layer4から渡された思考データ
    contents: dict              # {platform_id: PlatformContent}
    platforms_generated: list   # 実際に生成されたプラットフォームリスト

    def get(self, platform_id: str) -> Optional[PlatformContent]:
        return self.contents.get(platform_id)

    def summary(self) -> str:
        lines = [
            f"テーマ: {self.theme}",
            f"日付:   {self.date}",
            f"生成:   {', '.join(self.platforms_generated)}",
            "",
        ]
        for pid in PLATFORM_ORDER:
            content = self.contents.get(pid)
            if not content:
                continue
            engine = _ENGINES.get(pid)
            dna_name = engine.dna.display_name if engine else pid
            lines.append(f"── {dna_name} ──")
            lines.append(f"  Hook: {content.hook[:60]}")
            lines.append(f"  CTA:  {content.cta[:40]}")
            lines.append("")
        return "\n".join(lines)

    def dna_violation_report(self) -> list:
        """全プラットフォームのDNA違反チェック結果。"""
        violations = []
        for pid, content in self.contents.items():
            engine = _ENGINES.get(pid)
            if engine:
                v = engine.validate_dna(content)
                for item in v:
                    violations.append(f"[{pid}] {item}")
        return violations


class ContentEngine:
    """
    Layer 5: Content Engine

    Expert Interview / Thought Library の思考を受け取り、
    各プラットフォーム向けコンテンツを独立生成する。
    """

    def generate_all(
        self,
        theme: str,
        date: str,
        intelligence: dict,
        platforms: Optional[list] = None,
        business_strategy=None,
        account_strategy=None,
    ) -> MultiPlatformPackage:
        """
        全プラットフォーム（または指定プラットフォーム）向けコンテンツを生成する。

        Args:
            theme:             今日のテーマ
            date:              実行日（YYYY-MM-DD）
            intelligence:      Layer4の専門家思考データ
              {
                "observation":   str,   # 現場の気づき
                "question":      str,   # クライアントへの質問
                "perspective":   str,   # 独自の視点
                "speaker_words": str,   # 専門家のセリフ
                "口ぐせ":        str,   # Expert Interviewから
                "診断":          str,
                "価値観":        str,
                "観察":          str,
                "思い込み":      str,
                "Thinking":      str,
              }
            platforms:         生成するプラットフォームのリスト（None = 全て）
            business_strategy: Layer1のBusinessStrategy
            account_strategy:  Layer2のAccountStrategy

        Returns:
            MultiPlatformPackage
        """
        target_platforms = platforms or PLATFORM_ORDER
        contents = {}
        generated = []

        for pid in target_platforms:
            engine = _ENGINES.get(pid)
            if not engine:
                continue
            try:
                content = engine.generate(
                    theme=theme,
                    intelligence=intelligence,
                    business_strategy=business_strategy,
                    account_strategy=account_strategy,
                )
                contents[pid] = content
                generated.append(pid)
            except Exception as e:
                print(f"  ⚠️ {pid} コンテンツ生成エラー: {e}")

        return MultiPlatformPackage(
            theme=theme,
            date=date,
            intelligence=intelligence,
            contents=contents,
            platforms_generated=generated,
        )

    def generate_for(
        self,
        platform_id: str,
        theme: str,
        date: str,
        intelligence: dict,
        business_strategy=None,
        account_strategy=None,
    ) -> Optional[PlatformContent]:
        """指定プラットフォーム1つのコンテンツを生成する。"""
        engine = _ENGINES.get(platform_id)
        if not engine:
            raise ValueError(f"Unknown platform: {platform_id}. Available: {list(_ENGINES.keys())}")
        return engine.generate(
            theme=theme,
            intelligence=intelligence,
            business_strategy=business_strategy,
            account_strategy=account_strategy,
        )

    def describe_dna(self, platform_id: Optional[str] = None) -> str:
        """プラットフォームDNAの説明を返す（デバッグ・学習用）。"""
        if platform_id:
            engine = _ENGINES.get(platform_id)
            return engine.describe() if engine else f"Unknown platform: {platform_id}"
        lines = []
        for pid in PLATFORM_ORDER:
            engine = _ENGINES[pid]
            lines.append(engine.describe())
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def available_platforms() -> list:
        return PLATFORM_ORDER.copy()

    @staticmethod
    def cross_platform_rule() -> str:
        return (
            "【Cross-Platform 流用禁止ルール】\n"
            "  ✗ Instagramの文章をThreadsへ流用する\n"
            "  ✗ ThreadsのコンテンツをInstagramへ流用する\n"
            "  ✗ TikTok向けの演出をYouTubeに持ち込む\n"
            "  ✗ YouTubeの長い解説をXに貼り付ける\n"
            "  → 各プラットフォームはDNAが異なる別の生き物。\n"
            "    同じテーマでも、生成ロジックは完全に独立している。"
        )
