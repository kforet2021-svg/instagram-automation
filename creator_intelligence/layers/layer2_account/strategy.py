"""
creator_intelligence/layers/layer2_account/strategy.py

Layer 2: Account Strategy
SNSアカウント全体のポジショニング・発信テーマ・頻度を定義する。

Layer1（ビジネス）を各SNSアカウントに翻訳する層。
アカウントのポジションが定まることで、各投稿の「役割」が明確になる。

【2026-07-03(1回目): 新規作成。】
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ContentPillar:
    """発信の柱（テーマ）。アカウント全体を構成する3〜5本の柱。"""
    name: str
    """柱の名前。例: 「顔の構造を知る」"""
    purpose: str
    """この柱が担う役割。例: 「専門家としての信頼を構築する」"""
    frequency: str
    """投稿頻度の目安。例: 「週1」「月2」"""
    example_themes: list = field(default_factory=list)
    """このテーマに沿った投稿例。例: ["咬筋とむくみ", "フェイスラインと姿勢"]"""


@dataclass
class AccountStrategy:
    """
    SNSアカウント全体の戦略定義。
    Platform（Layer3）に依存しない共通戦略と、Platform別設定を持つ。
    """

    # ── アカウント基本情報 ────────────────────────────────────────────
    account_name: str
    """アカウント名・ハンドル。例: 「@core_hari_face」"""

    account_position: str
    """このアカウントが市場でどのポジションを取るか（1文で）。
    例: 「顔の専門家として、顔の構造から根本を変えるメソッドを発信する」"""

    # ── 発信テーマの柱 ───────────────────────────────────────────────
    content_pillars: list = field(default_factory=list)
    """ContentPillar のリスト。3〜5本が理想。"""

    # ── フォロワー設計 ────────────────────────────────────────────────
    follower_type_a: str = ""
    """最もフォローしてほしい人物像（Layer1のtarget_personと連動）。"""
    follower_type_b: str = ""
    """次にフォローしてほしい人物像（Layer Aより広い層）。"""

    # ── アカウントの「声」 ────────────────────────────────────────────
    account_voice: str = ""
    """このアカウントの語り口・キャラクター。
    例: 「親しみやすいが根拠がある。専門用語より感覚で話す。断言する。」"""

    # ── 競合ポジショニング ────────────────────────────────────────────
    positioning_vs_competitor: str = ""
    """競合アカウントと何が根本的に違うか。
    例: 「他の美容アカウントは見た目の変化だけ。こちらは構造から説明する。」"""

    # ── 発信しない領域（アカウントレベル） ───────────────────────────
    out_of_scope: list = field(default_factory=list)
    """このアカウントでは扱わないテーマ・領域。
    例: ["ダイエット", "メイク", "整形"]"""

    # ── KPI ──────────────────────────────────────────────────────────
    primary_kpi: str = "予約数"
    """このアカウントの最優先KPI。"""
    secondary_kpi: str = "保存数"
    """二次KPI（Instagramならsave率、Threadsならreply率など）。"""

    def get_pillar_names(self) -> list:
        return [p.name if hasattr(p, "name") else str(p) for p in self.content_pillars]
