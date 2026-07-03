"""
creator_intelligence/layers/layer4_intelligence/types.py

Layer 4: Creator Intelligence — 専門家の思考タイプ定義

「知識」ではなく「専門家の思考・会話・感覚」を蓄積する。

Expert Interviewから集まるもの:
  口ぐせ    … 専門家が自然に使う言葉・フレーズ（会話から）
  診断      … 専門家がクライアントの状態をどう見るか（観察から）
  価値観    … 専門家の核心的な信念・こだわり（インタビューから）
  観察      … 専門家が現場で気づくこと（繰り返しのパターン）
  思い込み  … クライアントがよく持つ誤解・勘違い（現場から）

システマティックな知識（構造化されたもの）:
  Question    … 専門家がクライアントに問いかける質問
  Observation … 観察を構造化したもの（再現性ある発見）
  Thinking    … 専門家の思考プロセス・推論の流れ

【2026-07-03(1回目): 新規作成。Layer4 Creator Intelligence。】
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

# ── 思考タイプ定義 ──────────────────────────────────────────────────────────

CREATOR_INTELLIGENCE_TYPES = {
    # Expert Interviewから自然に集まるもの（会話・感覚）
    "口ぐせ":    "専門家が自然に使う言葉・フレーズ。Expert Interviewで最も収集しやすい",
    "診断":      "専門家がクライアントの状態をどう読むか。現場の目線",
    "価値観":    "専門家の核心的な信念・こだわり・絶対に譲れないもの",
    "観察":      "専門家が現場で繰り返し気づくこと。「最近多いのが〜」",
    "思い込み":  "クライアントがよく持つ誤解・勘違い。「みんな〜と思っているが」",
    # システマティックな知識（構造化）
    "Question":    "専門家がクライアントに問いかける質問。会話の入口",
    "Observation": "観察を構造化したもの。再現性のある発見・パターン",
    "Thinking":    "専門家の思考プロセス・なぜそう判断するかの推論の流れ",
}

# どの思考タイプがどのプラットフォームに最も活きるか
PLATFORM_FIT = {
    "口ぐせ":    ["threads", "x", "instagram"],     # 口語・自然な言葉が刺さる
    "診断":      ["instagram", "youtube", "tiktok"], # 視覚的な診断プロセス
    "価値観":    ["x", "threads"],                   # 断言・意見投稿
    "観察":      ["threads", "instagram", "x"],      # 現場の気づき共有
    "思い込み":  ["tiktok", "x", "instagram"],       # 「え、そうなの？」驚き
    "Question":  ["instagram", "threads"],            # 問いかけで引き込む
    "Observation": ["youtube", "instagram"],          # 深い解説に使える
    "Thinking":  ["youtube", "threads"],              # 思考プロセスの可視化
}


@dataclass
class ThoughtEntry:
    """
    専門家の思考1エントリ。
    Expert Interviewで収集するか、手動で追加する。
    """
    id: str
    """一意識別子。例: "CI-001" """

    type: str
    """CREATOR_INTELLIGENCE_TYPES のキー。"""

    content: str
    """思考の核心。専門家の言葉に近い形で記録する。"""

    speaker_words: str = ""
    """そのまま投稿に使えるセリフ・表現。改行区切りで複数可。"""

    source: str = "expert_interview"
    """収集源。"expert_interview" / "thought_library" / "manual" """

    platform_fit: list = field(default_factory=list)
    """この思考が最も活きるプラットフォームリスト（空なら全プラットフォーム）。"""

    topic: str = ""
    """テーマキーワード（検索・マッチングに使う）。"""

    verified: bool = False
    """専門家が確認・承認済みか。"""

    created_at: str = ""
    """記録日。YYYY-MM-DD。"""

    def best_platforms(self) -> list:
        if self.platform_fit:
            return self.platform_fit
        return PLATFORM_FIT.get(self.type, ["instagram", "threads", "x"])

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "type":          self.type,
            "content":       self.content,
            "speaker_words": self.speaker_words,
            "source":        self.source,
            "platform_fit":  ",".join(self.platform_fit),
            "topic":         self.topic,
            "verified":      "TRUE" if self.verified else "FALSE",
            "created_at":    self.created_at,
        }


@dataclass
class InterviewSession:
    """
    1回の Expert Interview セッション記録。
    後から ThoughtEntry に変換・保存する。
    """
    session_id: str
    date: str
    theme: str
    qa_pairs: list          # [{"question": ..., "answer": ...}, ...]
    extracted: dict         # extract_interview_insights の結果

    def to_thought_entries(self) -> list:
        """
        インタビュー結果を ThoughtEntry リストに変換する。
        """
        entries = []
        base_id = self.session_id

        type_map = {
            "observation":  "Observation",
            "question":     "Question",
            "perspective":  "価値観",
            "speaker_words": "口ぐせ",
        }

        for field_key, thought_type in type_map.items():
            content = self.extracted.get(field_key, "").strip()
            if not content:
                continue
            entries.append(ThoughtEntry(
                id=f"{base_id}-{field_key[:3].upper()}",
                type=thought_type,
                content=content,
                speaker_words=content if field_key == "speaker_words" else "",
                source="expert_interview",
                platform_fit=PLATFORM_FIT.get(thought_type, []),
                topic=self.theme,
                verified=False,
                created_at=self.date,
            ))

        return entries
