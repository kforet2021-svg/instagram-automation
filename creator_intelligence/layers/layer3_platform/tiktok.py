"""
Layer 3: TikTok Platform Engine

TikTok DNA:
  「エンタメ × 発見 × 中毒性」プラットフォーム。
  ユーザーは無目的にスクロールしているが、1秒以内に止まる何かを探している。
  専門家は「親近感のある面白い人」として、知識よりリアクション・驚き・体験を見せる。

【絶対禁止】
  - InstagramのReelsをそのまま流用する（音・構成・空気感が別物）
  - 専門家らしさを出そうと「堅い」話し方をする
  - 最初の1秒に動きがない（静止フレームから始めない）
  - 長い自己紹介・挨拶（1秒以内にコンテンツが始まる）

【2026-07-03(1回目): 新規作成。】
"""

from __future__ import annotations
from typing import Optional
from .base import PlatformDNA, PlatformContent, PlatformEngine

_DNA = PlatformDNA(
    platform_id="tiktok",
    display_name="TikTok",

    user_mindset=(
        "無目的に見ているが「思わず見てしまう」何かを探している。"
        "エンタメ優先。知識は面白ければ受け入れる。"
        "「え、これ知らなかった」「笑った」「共感した」でシェアが生まれる。"
    ),
    user_behavior=(
        "0.5秒で判断してスワイプ。面白ければ最後まで見る（リプレイも）。"
        "友達にシェア・デュエット・ステッチで反応する。"
        "コメントで盛り上がる文化。"
    ),

    algorithm_values=["視聴完了率", "リプレイ率", "シェア数", "コメント数", "フォロー率"],

    primary_format="縦型ショート動画（15〜60秒）、ライブ",
    hook_window_sec=1,
    hook_mechanism=(
        "最初の1秒に動き・驚き・声・テキスト。静止フレーム禁止。"
        "「え？」「なにこれ？」と思わせる冒頭。"
        "音声がなくてもテキストで伝わる（音オフ視聴が多い）。"
    ),

    content_structure=[
        "0〜1秒: 動き＋テキスト（「え？」と思わせる）",
        "1〜5秒: 問いかけ・驚きの事実・共感ポイント",
        "5〜30秒: エンタメ要素を保ちながら価値を届ける",
        "30〜45秒: 結論・驚きの回収",
        "最後: シェアしたくなる締め・ループ設計",
    ],
    ideal_length="15〜45秒（専門家は60秒まで許容）",

    tone=(
        "エネルギッシュで親近感がある。専門家ぶらない。"
        "「みんなに教えたい」感覚。笑い・驚き・テンポが命。"
        "難しい言葉は使わない。感情で伝える。"
    ),
    writing_style=(
        "テンポ重視。一文が短い。リズムがある。"
        "テキストオーバーレイ多用（音オフでも伝わる）。"
        "ハッシュタグは5〜10個（トレンドタグを混ぜる）。"
        "BGMはトレンドサウンドを使う（アルゴリズム優遇）。"
    ),

    forbidden=[
        "InstagramのReelsをそのまま音声だけ変えて投稿する",
        "静止フレームから動画を始める（最初の1秒に動きが必須）",
        "「こんにちは〇〇です」などの長い自己紹介から入る",
        "堅い専門家らしい話し方・難しい用語の多用",
        "音楽なし・無音での投稿（TikTokは音が文化）",
        "Threadsのような文字だけの思考投稿",
    ],

    primary_cta="シェア・デュエット・コメント（「これ誰かに見せたい」を作る）",
    expert_role=(
        "「この人面白い、また見たい」と思わせる親近感のある専門家。"
        "知識より体験・リアクション・現場のリアルを見せる。"
        "難しいことをわかりやすく・楽しく伝える翻訳者。"
    ),

    not_like=[
        "Instagram: Instagramの整った教育コンテンツはTikTokでは堅すぎる",
        "Threads: 思考の言語化はTikTokでは伝わらない",
        "YouTube: 長尺の丁寧な解説はTikTokでは離脱される",
        "X: テキストで考える投稿はTikTokのDNAと合わない",
    ],
)


class TikTokEngine(PlatformEngine):
    """TikTok向けコンテンツ生成エンジン。"""

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
        専門家の「驚き・逆説・現場のリアル」をTikTok向けに変換。

        エンタメ優先。知識は面白さの中に溶け込ませる。
        """
        observation   = intelligence.get("observation", "")
        misconception = intelligence.get("思い込み", "")
        catchphrase   = intelligence.get("口ぐせ", "")

        hook = _tiktok_hook(theme, misconception, observation)

        body_lines = [hook, ""]
        if misconception:
            body_lines.append(f"実は多くの人が「{misconception}」と思ってる。")
            body_lines.append("でも、現場で見てきた私は知っています。")
            body_lines.append("")
        if observation:
            body_lines.append(observation)

        body_lines.append("")
        body_lines.append("これ、知ってた？コメントで教えて。")
        body = "\n".join(body_lines)

        return PlatformContent(
            platform_id="tiktok",
            format_type="short",
            hook=hook,
            body=body,
            caption=f"{hook}\n\n{theme} #知らなかった #専門家が教える",
            cta="コメントで教えて / 友達に送る",
            metadata={
                "hashtags":     f"#{theme.replace('と', '').replace('と', '')} #知らなかった #専門家 #豆知識",
                "sound":        "トレンドサウンドを使用（投稿時に選択）",
                "text_overlay": hook,
                "ideal_sec":    "30〜45秒",
            },
            generation_notes=(
                "【TikTok 撮影メモ】\n"
                "  - 最初の1秒: 動いているところから始める（静止禁止）\n"
                "  - テキストオーバーレイで音なしでも伝わるようにする\n"
                "  - テンポは速めに編集（1〜2秒のカット割り）\n"
                "  - BGMはトレンドサウンドを必ず使う\n"
                "  - 専門家ぶらず、親近感を意識する"
            ),
            dna_check=[
                "✅ 最初の1秒に動きがあるか",
                "✅ Instagramのコンテンツを流用していないか",
                "✅ エンタメ要素があるか（堅くないか）",
                "✅ 音オフでもテキストで伝わるか",
                "✅ シェアしたくなる要素があるか",
            ],
        )


def _tiktok_hook(theme: str, misconception: str, observation: str) -> str:
    if misconception and len(misconception) <= 25:
        return f"「{misconception}」は間違いです。"
    if observation and len(observation) <= 25:
        return f"現場で気づいた{observation}"
    return f"{theme}、実はこれが原因でした。"
