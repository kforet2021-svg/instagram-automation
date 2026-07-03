"""
Layer 3: Instagram Platform Engine

Instagram DNA:
  「見つけて、保存する」プラットフォーム。
  ユーザーは発見モードにある。視覚的なフックで止め、保存価値で刺す。
  専門家は「少し先を歩く人」として、変容のビフォーアフターを見せる。

【絶対禁止】
  - Threadsで書いたような生の意見・雑談をそのまま使う
  - テキスト主体で視覚がないコンテンツ
  - 「〜と思います」などの曖昧な語尾（断言する）

【2026-07-03(1回目): 新規作成。】
"""

from __future__ import annotations
from typing import Optional
from .base import PlatformDNA, PlatformContent, PlatformEngine

_DNA = PlatformDNA(
    platform_id="instagram",
    display_name="Instagram",

    user_mindset=(
        "発見・保存・学習モード。何かいい情報を見つけたい。"
        "スクロール中に「これ自分のことだ」と思った瞬間に止まる。"
    ),
    user_behavior=(
        "縦スクロールしながら視覚で止まる。"
        "気に入ったら保存して後で読み直す。"
        "プロフィールに飛んでフォローを判断する。"
    ),

    algorithm_values=["保存数", "視聴完了率（Reels）", "シェア数", "コメント数", "いいね数"],

    primary_format="Reels（15〜60秒）、カルーセル（5〜8枚）、静止画",
    hook_window_sec=3,
    hook_mechanism=(
        "映像の動き＋テキストオーバーレイ（テロップ）。"
        "画面を止めた人が「続きを見たい」と思う問いかけ・驚き・共感。"
    ),

    content_structure=[
        "フック（0〜3秒）: テロップ＋動き。スクロールを止める問いかけ",
        "共感（3〜10秒）: ターゲットの悩みをそのまま代弁する",
        "診断（10〜25秒）: 専門家が見るもの・気づいていないこと",
        "解決（25〜40秒）: なぜそうなるか、どうすればいいか",
        "CTA（40〜45秒）: 保存・フォロー・予約（1つだけ）",
    ],
    ideal_length="Reels: 30〜45秒　カルーセル: 5〜8枚（1枚に情報を詰めすぎない）",

    tone=(
        "温かく断言する。「〜だと思います」ではなく「〜です」。"
        "専門用語より感覚の言葉。論文より現場の話。"
    ),
    writing_style=(
        "体言止め多用。改行を多く。一文25字以内。"
        "キャプションは投稿の補足（本文は映像・スライドで伝える）。"
        "ハッシュタグは5〜10個（多すぎない）。"
    ),

    forbidden=[
        "Threadsで書いた生の意見・雑談をそのまま流用する",
        "視覚要素（映像・スライド）なしでテキストだけで完結させる",
        "1投稿に複数のCTAを入れる（保存もフォローも予約も、は禁止）",
        "「〜と思います」「〜かもしれません」などの曖昧な語尾",
        "競合他社・他サロンへの言及・比較",
        "過度なビフォーアフター（医療的な効果を断言する）",
    ],

    primary_cta="保存（「あとで見返してください」）",
    expert_role=(
        "変容のガイド。「あなたもできる」を見せる存在。"
        "先生ではなく、同じ悩みを経験した少し先を歩く専門家。"
        "施術映像・実際の変化でリアリティを担保する。"
    ),

    not_like=[
        "Threads: 生の意見・感情・雑談はInstagramには向かない",
        "X: 短い断言ツイートをそのまま投稿にしない",
        "TikTok: 音楽・トレンドに乗ったエンタメ構成は別物",
        "YouTube: 長尺の丁寧な解説はReelsには向かない",
    ],
)


class InstagramEngine(PlatformEngine):
    """Instagram向けコンテンツ生成エンジン。"""

    @property
    def dna(self) -> PlatformDNA:
        return _DNA

    def generate(
        self,
        theme: str,
        intelligence: dict,
        business_strategy=None,
        account_strategy=None,
    ) -> PlatformContent:
        """
        Expert Interview / Thought Library の思考を
        Instagram Reels 向けコンテンツに変換する。

        Persona-First: テーマから作らず「この人に話しかける」形で組み立てる。
        """
        # 専門家の言葉を取得（優先順位: interview > thought_library）
        speaker_words = (
            intelligence.get("speaker_words") or
            intelligence.get("thought_speaker_words") or ""
        )
        observation  = intelligence.get("observation", "")
        perspective  = intelligence.get("perspective", "")
        question_ci  = intelligence.get("question", "")
        target_pain  = (
            (business_strategy.target_pain if business_strategy else "") or
            intelligence.get("target_pain", "")
        )

        # ── Hook: 最初の3秒で止める問いかけ ─────────────────────────
        hook = _build_hook(theme, question_ci, observation)

        # ── Body: 専門家の言葉を軸に組み立てる ───────────────────────
        body_lines = []
        if speaker_words:
            # 専門家の実際の言葉を優先（Expert Interviewから）
            body_lines.extend(
                line for line in speaker_words.split("\n") if line.strip()
            )
        else:
            if observation:
                body_lines.append(observation)
            if perspective:
                body_lines.append(perspective)

        body = "\n".join(body_lines) if body_lines else f"{theme}について、現場から伝えたいことがあります。"

        # ── Caption ──────────────────────────────────────────────────
        cta = _build_cta(account_strategy)
        caption_parts = [hook, "", body[:200] if len(body) > 200 else body, "", cta]
        caption = "\n".join(caption_parts)

        # ── Metadata ─────────────────────────────────────────────────
        hashtags = _build_hashtags(theme, business_strategy)
        metadata = {
            "hashtags":         hashtags,
            "thumbnail_concept": f"「{hook[:20]}」のテロップ＋カメラ目線の静止フレーム",
            "reels_structure":  "\n".join(f"  {i+1}. {s}" for i, s in enumerate(_DNA.content_structure)),
            "ideal_length_sec": "30〜45秒",
        }

        return PlatformContent(
            platform_id="instagram",
            format_type="reels",
            hook=hook,
            body=body,
            caption=caption,
            cta=cta,
            metadata=metadata,
            generation_notes=(
                "【Instagram Reels 撮影メモ】\n"
                "  - 冒頭3秒: テロップ表示＋わずかな動き（静止は避ける）\n"
                "  - カメラ目線で話しかける（説明ではなく対話）\n"
                "  - 保存したくなる「まとめ感」を意識する\n"
                "  - BGMは控えめ（声を聴かせる）"
            ),
            dna_check=[
                "✅ 最初の3秒でフックがあるか",
                "✅ ターゲットの悩みを代弁しているか",
                "✅ CTAは1つだけか",
                "✅ 「保存」したくなる価値があるか",
                "✅ Threadsの文体を流用していないか",
            ],
        )


def _build_hook(theme: str, question: str, observation: str) -> str:
    if question and "？" in question:
        return question
    if observation and len(observation) <= 30:
        return observation
    return f"{theme}、本当の原因を知っていますか？"


def _build_cta(account_strategy) -> str:
    if account_strategy and hasattr(account_strategy, "primary_kpi"):
        if "予約" in account_strategy.primary_kpi:
            return "気になった方はプロフィールのリンクから体験予約できます。\nまずは保存して、気になったときに読み返してください。"
    return "保存して、気になったときに読み返してください。"


def _build_hashtags(theme: str, business_strategy) -> str:
    base = ["#顔専門", "#小顔", "#フェイスライン", "#たるみ改善", "#顔筋"]
    # テーマから追加
    if "姿勢" in theme:
        base.append("#姿勢改善")
    if "むくみ" in theme:
        base.append("#むくみ")
    if "咬筋" in theme:
        base.append("#食いしばり")
    return " ".join(base[:10])
