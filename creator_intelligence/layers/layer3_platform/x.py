"""
Layer 3: X (Twitter) Platform Engine

X DNA:
  「情報・意見・速報が飛び交うプラットフォーム」。
  ユーザーはタイムラインを高速スキャンしながら「鋭い一言」を探している。
  専門家は「知的な断言者」として、短く・鋭く・反論可能な意見を投稿する。

【絶対禁止】
  - Instagramのような長い説明文を投稿する
  - 絵文字を多用する（Xでは浮く）
  - 「〜と思います」「〜かもしれません」（Xは断言が強い）
  - Threadsのような「みなさんどうですか？」（Xはより直接的）

【2026-07-03(1回目): 新規作成。】
"""

from __future__ import annotations
from typing import Optional
from .base import PlatformDNA, PlatformContent, PlatformEngine

_DNA = PlatformDNA(
    platform_id="x",
    display_name="X（Twitter）",

    user_mindset=(
        "タイムラインを高速スキャンしながら「鋭い発見・意見・情報」を探している。"
        "短く的確な一言で「この人賢い」と思ったら即フォロー。"
        "反論・引用で議論に参加する文化。"
    ),
    user_behavior=(
        "1秒以内でいいね/引用/スクロールを判断する。"
        "鋭い一言にはいいね・引用・リポスト。"
        "スレッドは読まれるが、1ツイート目が弱ければ続きは読まれない。"
    ),

    algorithm_values=["エンゲージメント率（引用>リプライ>いいね）", "インプレッション", "フォロー率"],

    primary_format="ツイート（280文字）、スレッド（連続ツイート）",
    hook_window_sec=1,
    hook_mechanism=(
        "1ツイートが全て。最初の1行で全てが決まる。"
        "逆説・断言・驚きの事実・反論したくなる一言。"
        "「え、本当に？」「確かに」「違うと思う」どれかの反応を起こす。"
    ),

    content_structure=[
        "1行目: 断言・逆説・驚き（これで全てが決まる）",
        "2〜4行: 根拠・現場経験・具体例（スレッドなら展開）",
        "最後: 引用されやすい締めの一言（なくてもいい）",
    ],
    ideal_length="単ツイート: 100〜200文字　スレッド: 3〜7連投",

    tone=(
        "鋭く、断言する。「〜です」「〜します」で終わる。"
        "敬語は状況次第（堅すぎると知性が伝わらない）。"
        "読者の知性を信頼する（丁寧な説明より鋭い示唆）。"
    ),
    writing_style=(
        "一文が短い。改行は少なめ（Xは縦長が嫌われる）。"
        "ハッシュタグは1〜2個（多すぎると低品質に見える）。"
        "絵文字は最小限（使うなら1個まで）。"
        "数字を使うと具体性が増す（「3つの理由」より「実際に見た300人」）。"
    ),

    forbidden=[
        "Instagramの教育コンテンツを長文で貼り付ける",
        "絵文字を多用する（X文化では知性が下がって見える）",
        "「〜と思います」「〜かもしれません」などの曖昧語",
        "ハッシュタグを5個以上つける",
        "Threadsのような「みなさんはどう思いますか？」の問いかけで終わる",
        "TikTokのエンタメ要素を文字で再現しようとする",
    ],

    primary_cta="引用・リポスト・フォロー（反論・共感どちらでも参加したくなる投稿）",
    expert_role=(
        "知的な断言者。「この人は現場を知っている」と思わせる存在。"
        "一般論を覆す・業界の常識を問い直す視点を持つ人。"
        "フォローすると「賢くなれる」と思わせる。"
    ),

    not_like=[
        "Instagram: まとめ・教育コンテンツの長文はXでは読まれない",
        "Threads: Threadsより直接的・攻撃的・議論的な文化",
        "TikTok: エンタメ・演出はXでは通用しない",
        "YouTube: 構成・体系性はXには不要（断片で刺す）",
    ],
)


class XEngine(PlatformEngine):
    """X（Twitter）向けコンテンツ生成エンジン。"""

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
        専門家の「鋭い視点・逆説・断言」をX投稿に変換。

        Expert Interviewの「思い込み」「価値観」が最も活きる。
        一言で「この人フォローしたい」を目指す。
        """
        misconception = intelligence.get("思い込み", "")
        values        = intelligence.get("価値観", "")
        perspective   = intelligence.get("perspective", "")
        catchphrase   = intelligence.get("口ぐせ", "")

        hook = _x_hook(theme, misconception, values, perspective, catchphrase)

        body_parts = [hook]
        # スレッドとして展開する場合の続き
        if perspective and perspective != hook:
            body_parts.append("")
            body_parts.append(perspective)

        body_parts.append("")
        body_parts.append(_x_closing(theme))
        body = "\n".join(body_parts)

        return PlatformContent(
            platform_id="x",
            format_type="tweet",
            hook=hook,
            body=body,
            caption="",  # Xにキャプションはない（ツイート本文が全て）
            cta="",      # CTAは投稿に溶け込ませる（明示的なCTAは浮く）
            metadata={
                "hashtags":    f"#{theme[:8]} #専門家の視点" if theme else "",
                "thread":      "必要なら2〜3連投で展開",
                "char_count":  len(body),
            },
            generation_notes=(
                "【X 投稿メモ】\n"
                "  - 1行目が全て。弱ければ書き直す\n"
                "  - 「〜と思います」は削除する（断言に変える）\n"
                "  - 絵文字は使わないか1個まで\n"
                "  - 引用・反論されやすい「尖った」角度を意識する\n"
                "  - Instagramの文章をコピーしない"
            ),
            dna_check=[
                "✅ 1行目が断言・逆説・驚きになっているか",
                "✅ 「〜と思います」を使っていないか",
                "✅ 絵文字は1個以下か",
                "✅ Instagramの文章をコピーしていないか",
                "✅ 引用したくなる「鋭さ」があるか",
            ],
        )


def _x_hook(theme: str, misconception: str, values: str, perspective: str, catchphrase: str) -> str:
    """Xの1行目: 断言・逆説・業界の常識への問い直し。"""
    if misconception and len(misconception) <= 30:
        return f"「{misconception}」は間違い。現場で300人見てわかった。"
    if values and len(values) <= 30:
        return values
    if catchphrase and len(catchphrase) <= 30 and "？" not in catchphrase:
        return catchphrase
    if perspective and len(perspective) <= 40:
        return perspective
    return f"{theme}。多くの人が原因を誤解している。"


def _x_closing(theme: str) -> str:
    closings = [
        "これを知ってから変わった人を何人も見てきた。",
        "現場でずっとそう思ってた。",
        "同意する人も、違うと思う人も、返信が欲しい。",
        "これ、業界では言いにくいことだけど。",
    ]
    import hashlib
    idx = int(hashlib.md5(theme.encode()).hexdigest(), 16) % len(closings)
    return closings[idx]
