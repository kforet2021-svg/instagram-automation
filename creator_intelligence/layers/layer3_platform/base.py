"""
creator_intelligence/layers/layer3_platform/base.py

Layer 3: Platform Engine — 基底クラス
各プラットフォームのDNAを定義する抽象基底クラス。

【鉄則】
  - InstagramのコンテンツをThreadsに流用してはならない
  - ThreadsのコンテンツをInstagramに流用してはならない
  - 各PlatformはそれぞれのDNAを持ち、生成ロジックが独立している
  - 「投稿を最適化する」のではなく「そのPlatformで生まれたコンテンツ」を作る

PlatformDNA とは:
  - そのプラットフォームのユーザーが何を期待しているか
  - アルゴリズムが何を評価するか
  - 専門家がそのプラットフォームでどう振る舞うべきか
  - 何を絶対にやってはいけないか

【2026-07-03(1回目): 新規作成。5レイヤーアーキテクチャ — Layer3実装。】
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlatformDNA:
    """
    プラットフォームのDNA定義。
    このDNAを理解せずにコンテンツを生成してはならない。
    """
    platform_id: str
    """プラットフォーム識別子。例: "instagram", "threads", "tiktok", "youtube", "x" """

    display_name: str
    """表示名。例: Instagram Reels"""

    # ── ユーザー心理 ─────────────────────────────────────────────────
    user_mindset: str
    """そのプラットフォームを開いたときのユーザーの心理状態。
    例: 「発見・保存・学習モード。何かいいものを見つけたい。」"""

    user_behavior: str
    """ユーザーの典型的な行動パターン。
    例: 「スクロールしながらパっと止まる。保存して後で読む。」"""

    # ── アルゴリズム ─────────────────────────────────────────────────
    algorithm_values: list
    """アルゴリズムが評価する指標（重要順）。
    例: ["視聴完了率", "保存数", "シェア数", "コメント数"]"""

    # ── コンテンツ構造 ────────────────────────────────────────────────
    primary_format: str
    """このプラットフォームの主力フォーマット。
    例: "Reels（15〜60秒）、カルーセル（2〜10枚）、静止画" """

    hook_window_sec: int
    """最初の何秒でユーザーを掴まなければならないか。"""

    hook_mechanism: str
    """フックの仕組み（何でユーザーを止めるか）。
    例: 「映像の動き＋テキストオーバーレイ」"""

    content_structure: list
    """コンテンツの理想的な構造（ステップ順）。
    例: ["フック（0〜3秒）", "共感・問題提示", "解決策", "CTA（保存）"]"""

    ideal_length: str
    """理想のコンテンツ長さ。
    例: "Reels: 30〜45秒、カルーセル: 5〜8枚" """

    # ── トーン・スタイル ──────────────────────────────────────────────
    tone: str
    """このプラットフォームでの語り口・雰囲気。"""

    writing_style: str
    """文章スタイルの具体的な指示。
    例: 「体言止め多用。改行を多く。一文を短く。」"""

    # ── 禁止事項（DNA違反） ───────────────────────────────────────────
    forbidden: list
    """このプラットフォームで絶対にやってはいけないこと。
    これを犯すとDNA違反 = コンテンツが機能しない。"""

    # ── CTA ──────────────────────────────────────────────────────────
    primary_cta: str
    """このプラットフォームで最も効果的なCTAの型。
    例: 「保存」（Instagram）、「返信」（Threads）"""

    # ── 専門家の振る舞い ──────────────────────────────────────────────
    expert_role: str
    """専門家がこのプラットフォームでどう振る舞うべきか。
    例: 「先生ではなく、同じ悩みを持つ人の少し先を歩く人」"""

    # ── 他プラットフォームとの違い ───────────────────────────────────
    not_like: list = field(default_factory=list)
    """他のプラットフォームとの根本的な違い（流用禁止の理由）。
    例: ["Threadsのような生の意見投稿はしない", "TikTokのような演出は不要"]"""


@dataclass
class PlatformContent:
    """プラットフォーム向けに生成されたコンテンツ。"""
    platform_id: str
    format_type: str
    """フォーマット。例: "reels", "carousel", "thread", "short", "video" """

    hook: str
    """最初の数秒で使うフック（テロップ・冒頭文）。"""

    body: str
    """本文・台本・スライドテキスト。"""

    caption: str
    """投稿キャプション（プラットフォームによっては空）。"""

    cta: str
    """CTA文言。"""

    metadata: dict = field(default_factory=dict)
    """プラットフォーム固有のメタデータ。
    例: hashtags, thumbnail_concept, chapter_markers, sound_suggestion"""

    generation_notes: str = ""
    """生成時の注意事項・撮影ディレクション。"""

    dna_check: list = field(default_factory=list)
    """このコンテンツがPlatformDNAを守っているかのチェックリスト。"""


class PlatformEngine(ABC):
    """
    Layer 3: Platform Engine の抽象基底クラス。

    各プラットフォーム（Instagram, Threads, TikTok, YouTube, X）が
    このクラスを継承して独自の生成ロジックを実装する。

    Content Engine（Layer5）はこのインターフェースを通じてのみ
    各プラットフォームにアクセスする。
    """

    @property
    @abstractmethod
    def dna(self) -> PlatformDNA:
        """このエンジンが扱うプラットフォームのDNA。"""

    @abstractmethod
    def generate(
        self,
        theme: str,
        intelligence: dict,
        business_strategy: Optional[object] = None,
        account_strategy: Optional[object] = None,
    ) -> PlatformContent:
        """
        プラットフォームに最適化されたコンテンツを生成する。

        Args:
            theme:             今日のテーマ（Editorial Meetingから）
            intelligence:      Layer4から渡される専門家の思考データ
            business_strategy: Layer1のBusinessStrategy（オプション）
            account_strategy:  Layer2のAccountStrategy（オプション）

        Returns:
            PlatformContent: このプラットフォーム専用のコンテンツ
        """

    def validate_dna(self, content: PlatformContent) -> list:
        """
        生成されたコンテンツがDNAに違反していないか検証する。

        戻り値: 違反事項のリスト（空リスト = 合格）
        """
        violations = []
        for forbidden_item in self.dna.forbidden:
            # 簡易チェック（各エンジンでオーバーライド可能）
            if any(keyword in (content.body + content.caption)
                   for keyword in _extract_keywords(forbidden_item)):
                violations.append(f"DNA違反: {forbidden_item}")
        return violations

    def describe(self) -> str:
        """このエンジンのDNAサマリーを返す（デバッグ・表示用）。"""
        d = self.dna
        return (
            f"=== {d.display_name} DNA ===\n"
            f"User Mindset : {d.user_mindset}\n"
            f"Hook Window  : 最初の{d.hook_window_sec}秒\n"
            f"Primary CTA  : {d.primary_cta}\n"
            f"Forbidden    : {' / '.join(d.forbidden[:3])}\n"
            f"Expert Role  : {d.expert_role}"
        )


def _extract_keywords(text: str) -> list:
    """禁止事項テキストから短いキーワードを抽出するヘルパー。"""
    import re
    words = re.findall(r'[ぁ-ん一-龥ァ-ヶA-Za-z]{3,}', text)
    return words[:3] if words else []
