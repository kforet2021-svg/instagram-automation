"""
Layer 3: Threads Platform Engine

Threads DNA:
  「会話・意見・思考の垂れ流し」プラットフォーム。
  ユーザーはタイムラインを流し見しながら「面白い意見」を探している。
  専門家は「思考している人」として、生の視点・違和感・発見を投稿する。

【絶対禁止】
  - Instagramの教育コンテンツを文字起こしして投稿する
  - 「〜については▶️Instagramで解説しています」への誘導だけ（それは補足OK）
  - 完成度の高い「まとめ」投稿（Threadsは思考の途中でいい）
  - ハッシュタグ多用（1〜2個まで、なくてもいい）

【2026-07-03(1回目): 新規作成。】
"""

from __future__ import annotations
from typing import Optional
from .base import PlatformDNA, PlatformContent, PlatformEngine

_DNA = PlatformDNA(
    platform_id="threads",
    display_name="Threads",

    user_mindset=(
        "タイムラインを流し見しながら「面白い意見」「共感できる一言」を探している。"
        "教育コンテンツより、専門家の生の視点・違和感・本音に反応する。"
    ),
    user_behavior=(
        "短いテキストを流し読みする。"
        "面白い投稿にはいいね・引用・返信で反応する。"
        "スレッドで繋がった続きも読む。"
    ),

    algorithm_values=["返信数", "引用数", "いいね数", "フォロワーとのやりとり"],

    primary_format="テキスト投稿（500文字以内）、スレッド（複数連投）",
    hook_window_sec=2,
    hook_mechanism=(
        "1行目で「あ、これ読みたい」と思わせる。"
        "問いかけ・逆説・専門家ならではの違和感。"
        "Twitterのような短い断言が効く。"
    ),

    content_structure=[
        "1行目: 止まる一言（問いかけ・逆説・本音）",
        "2〜4行: 専門家の生の観察・感覚・現場から見えること",
        "最終行: 返信を誘う問いかけ、または締めの一言",
    ],
    ideal_length="150〜300文字。スレッドなら1投稿100文字×3〜5連投",

    tone=(
        "生で、未完成でいい。思考の途中を見せる。"
        "「〜だと思う」「〜が気になってる」など、断言より問い。"
        "専門家の本音・違和感・日々の発見を素直に書く。"
    ),
    writing_style=(
        "改行多め。体言止めより話し言葉。"
        "敬語は状況に応じて（堅苦しくなければ外す）。"
        "ハッシュタグは0〜2個（なくてもいい）。"
        "絵文字は最小限（使いすぎるとInstagram化する）。"
    ),

    forbidden=[
        "Instagramの教育コンテンツをテキスト化してそのまま投稿する",
        "完成されたまとめ・教科書的な投稿（Threadsは思考の途中でいい）",
        "ハッシュタグを5個以上つける",
        "「保存してください」というCTA（Threadsには保存文化がない）",
        "カルーセルや複数画像の代わりにリスト投稿する（情報量を詰め込まない）",
        "「詳しくはInstagramで」だけで終わる（誘導は補足として）",
    ],

    primary_cta="返信・引用（「あなたはどうですか？」「これ、どう思いますか？」）",
    expert_role=(
        "思考している人。専門家の頭の中を見せる存在。"
        "完成品ではなく「最近気になってること」「現場で感じたこと」を言語化する。"
        "フォロワーと一緒に考える姿勢。"
    ),

    not_like=[
        "Instagram: 教育・まとめ・保存CTAはInstagramの文化。Threadsに持ち込まない",
        "X: Threadsは返信・会話文化。バイラルより深い対話",
        "TikTok: エンタメ・演出はThreadsでは浮く",
        "YouTube: 構成された長い説明はThreadsでは読まれない",
    ],
)


class ThreadsEngine(PlatformEngine):
    """Threads向けコンテンツ生成エンジン。"""

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
        専門家の「生の思考・会話」をThreads投稿に変換する。

        Expert Interviewの口ぐせ・観察・思い込みが最も活きるプラットフォーム。
        完成品ではなく「思考の途中」を投稿する。
        """
        # Expert Interviewの口ぐせ・観察が最も使いやすい
        observation  = intelligence.get("observation", "")
        perspective  = intelligence.get("perspective", "")
        misconception = intelligence.get("思い込み", "")  # Layer4から
        catchphrase   = intelligence.get("口ぐせ", "")    # Layer4から

        # ── 1行目: 止まる一言 ───────────────────────────────────────
        hook = _threads_hook(theme, observation, misconception, catchphrase)

        # ── Body: 専門家の生の視点 ───────────────────────────────────
        body_parts = [hook]

        if perspective:
            body_parts.append("")
            body_parts.append(perspective)
        elif observation:
            body_parts.append("")
            body_parts.append(observation)

        # 返信を誘う締め
        body_parts.append("")
        body_parts.append(_threads_closing(theme))

        body = "\n".join(body_parts)

        return PlatformContent(
            platform_id="threads",
            format_type="thread",
            hook=hook,
            body=body,
            caption="",  # Threadsにキャプションは不要
            cta="あなたはどうですか？",
            metadata={
                "hashtags": "",  # 基本不要
                "thread_count": "1投稿（必要なら2〜3連投）",
                "char_count": len(body),
            },
            generation_notes=(
                "【Threads 投稿メモ】\n"
                "  - 完成品を作らない。思考の途中でいい\n"
                "  - 「保存してください」は書かない\n"
                "  - Instagramの教育コンテンツをコピーしない\n"
                "  - 返信が来たら必ず返す（会話が資産）"
            ),
            dna_check=[
                "✅ 1行目が止まる一言になっているか",
                "✅ 教育コンテンツをコピーしていないか",
                "✅ 保存CTAを入れていないか",
                "✅ ハッシュタグは2個以下か",
                "✅ 返信・対話を誘う要素があるか",
            ],
        )


def _threads_hook(theme: str, observation: str, misconception: str, catchphrase: str) -> str:
    """Threadsの1行目: 専門家の生の言葉・違和感・本音。"""
    if catchphrase and len(catchphrase) <= 40:
        return catchphrase
    if misconception and len(misconception) <= 50:
        return f"多くの人が勘違いしていること。\n{misconception}"
    if observation and len(observation) <= 40:
        return observation
    return f"{theme}について、現場から正直に言うと。"


def _threads_closing(theme: str) -> str:
    closings = [
        "これ、みなさんはどう感じますか？",
        "最近そう感じることが多くて。",
        "あなたの経験、聞かせてください。",
        "こう思うのは私だけかな。",
    ]
    import hashlib
    idx = int(hashlib.md5(theme.encode()).hexdigest(), 16) % len(closings)
    return closings[idx]
