"""
creator_intelligence/layers/layer1_business/strategy.py

Layer 1: Business Strategy
専門家・事業の「なぜ発信するか」を定義する最上位レイヤー。

すべてのコンテンツ生成はここから始まる。
Layer1 が定まらないと Layer3〜5 の生成がブレる。

【2026-07-03(1回目): 新規作成。5レイヤーアーキテクチャ実装。】
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class BusinessStrategy:
    """
    事業レベルの発信戦略。Vertical（業種）に依存しない共通構造。

    「何を売りたいか」ではなく「誰の人生をどう変えるか」が起点。
    """

    # ── 存在意義 ─────────────────────────────────────────────────────
    mission: str
    """この専門家・事業が世界に存在する理由。1文で。
    例: 「顔の構造から根本を変え、自信を持って生きる人を増やす」"""

    transformation: str
    """クライアントがビフォー→アフターで何が変わるか。
    例: 「顔のたるみが気になる → 自分の顔が好きになる」"""

    # ── ターゲット ────────────────────────────────────────────────────
    target_person: str
    """理想のクライアント像（1人の具体的な人物として描く）。
    例: 「30代後半、デスクワーク中心、最近写真を避けるようになった女性」"""

    target_pain: str
    """その人が今感じている痛み・悩み・不安。
    例: 「頬のたるみが気になって笑顔に自信が持てない」"""

    target_dream: str
    """その人が本当に手に入れたいもの（表面的な悩みの奥にあるもの）。
    例: 「自分の笑顔が好きで、写真を撮られても嫌じゃない状態」"""

    # ── 差別化 ───────────────────────────────────────────────────────
    unique_perspective: str
    """この専門家だけが持つ視点・解釈。他との違い。
    例: 「顔のたるみの原因の多くは咬筋。流すより緩めるが先」"""

    competitor_difference: str
    """同業他社と何が根本的に違うか。
    例: 「マッサージで流すのではなく、筋肉の使い方から変える」"""

    # ── 収益モデル（発信の最終目標） ─────────────────────────────────
    revenue_goal: str
    """発信が最終的にどのビジネスゴールに繋がるか。
    例: 「体験施術の予約 → リピーター化 → 年間契約」"""

    desired_action: str
    """コンテンツを見た人に取ってほしい1つの行動。
    例: 「プロフィールのリンクから体験予約をする」"""

    # ── 10年ビジョン ─────────────────────────────────────────────────
    ten_year_vision: str = ""
    """10年後にこの専門家・ブランドがどうなっているか。
    例: 「日本全国に認定サロンを持ち、顔専門メソッドの標準を作る」"""

    # ── 発信しないこと ────────────────────────────────────────────────
    never_say: list = field(default_factory=list)
    """絶対に発信しないこと・価値観と合わないこと。
    例: ["痩せる", "モテる", "整形と比較する"]"""

    def summary(self) -> str:
        return (
            f"【Mission】{self.mission}\n"
            f"【Transformation】{self.transformation}\n"
            f"【Target】{self.target_person}\n"
            f"【Pain → Dream】{self.target_pain} → {self.target_dream}\n"
            f"【Unique Perspective】{self.unique_perspective}\n"
            f"【Desired Action】{self.desired_action}"
        )
