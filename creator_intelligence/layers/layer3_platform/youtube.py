"""
Layer 3: YouTube Platform Engine

YouTube DNA:
  「深く学びたい人が来るプラットフォーム」。
  ユーザーは検索して来るか、サブスクしている専門家の新着を見る。
  専門家は「この人の話は信頼できる」という権威として、
  体系的・深い知識を届ける。

【絶対禁止】
  - Reelsをそのまま縦動画として投稿する（YouTube Shortsも独自設計が必要）
  - 視聴者が期待している「深さ」を省略する
  - タイトル・サムネイルを手を抜く（CTRが全て）
  - 「えーと」「あのー」が多い無編集の素材そのまま（最低限の編集は必須）

【2026-07-03(1回目): 新規作成。】
"""

from __future__ import annotations
from typing import Optional
from .base import PlatformDNA, PlatformContent, PlatformEngine

_DNA = PlatformDNA(
    platform_id="youtube",
    display_name="YouTube",

    user_mindset=(
        "「これについてちゃんと知りたい」という能動的な学習意欲を持って来る。"
        "信頼できる専門家・チャンネルを探していて、見つけたらサブスクする。"
        "時間を使う覚悟がある（10〜20分でも見る）。"
    ),
    user_behavior=(
        "タイトル＋サムネイルで視聴を判断（CTR）。"
        "最初の30秒で離脱か継続かを決める。"
        "途中まで見てから停止・後で再視聴（プレイリスト保存）。"
        "コメントで質問・感謝を書く。"
    ),

    algorithm_values=["視聴維持率（Watch Time）", "クリック率（CTR）", "サブスク数", "コメント数"],

    primary_format="長尺動画（8〜20分）、YouTube Shorts（60秒以内）",
    hook_window_sec=30,
    hook_mechanism=(
        "タイトル＋サムネイルでクリックさせる（CTR）。"
        "冒頭30秒で「この動画を最後まで見る価値がある」を証明する。"
        "「この動画では〇〇を教えます」という明確な約束。"
    ),

    content_structure=[
        "タイトル: SEO + 感情を動かすキーワード（30〜60文字）",
        "サムネイル: テキスト＋表情＋ビフォーアフター（CTRを最大化）",
        "冒頭30秒: 約束（この動画で何が得られるか）＋視聴者の悩みへの共感",
        "本編: 構造化された解説（章立て・3〜5のポイント）",
        "証拠・実例: 施術映像・事例・データ",
        "まとめ: 行動可能な結論",
        "エンドカード: 関連動画＋サブスク促進",
    ],
    ideal_length="長尺: 8〜15分　Shorts: 30〜60秒（長尺とは別設計）",

    tone=(
        "教育的・権威的だが親近感がある。「先生」ではなく「頼れる専門家の先輩」。"
        "データ・事例・現場経験を組み合わせて信頼を構築する。"
        "結論を先に言う（視聴者の時間を尊重する）。"
    ),
    writing_style=(
        "章立て・構成が明確。「今日は3つのことを話します」形式。"
        "概要欄にタイムスタンプ必須（8分以上の動画）。"
        "SEOを意識したキーワードをタイトル・概要欄に含める。"
    ),

    forbidden=[
        "InstagramのReelsをそのまま縦動画として投稿する",
        "タイトルとサムネイルを手抜きする（YouTubeはCTRが全て）",
        "最初の30秒に価値のある情報を一切入れない",
        "概要欄を空にする（SEOとユーザビリティの両方で失点）",
        "TikTokのようなエンタメ構成（YouTube視聴者は深さを期待している）",
        "Threadsのような思考の断片を動画にする",
    ],

    primary_cta="サブスク（「これが役に立ったらサブスクをお願いします」）",
    expert_role=(
        "この分野の権威・信頼できる先生。「この人に聞けばわかる」存在。"
        "体系的な知識と現場経験を組み合わせて解説する。"
        "視聴者の時間を尊重し、価値を最大化する。"
    ),

    not_like=[
        "Instagram: 短くて視覚的な投稿はYouTubeの期待値と合わない",
        "Threads: 思考の断片投稿はYouTubeには向かない",
        "TikTok: エンタメ優先・浅い内容はYouTube視聴者を失望させる",
        "X: 短い断言はYouTubeでは根拠・深さがないと信頼されない",
    ],
)


class YouTubeEngine(PlatformEngine):
    """YouTube向けコンテンツ生成エンジン。"""

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
        専門家の「体系的な知識・現場経験・思考プロセス」をYouTube動画設計に変換。

        タイトル・サムネイルコンセプト・章立て・台本概要を生成する。
        """
        observation  = intelligence.get("observation", "")
        perspective  = intelligence.get("perspective", "")
        diagnosis    = intelligence.get("診断", "")
        thinking     = intelligence.get("Thinking", "")

        title = _youtube_title(theme, perspective, observation)
        thumbnail = _youtube_thumbnail(theme, title)

        body_parts = [
            f"【冒頭30秒】",
            f"「{theme}」について、現場で何百人と向き合ってきてわかったことがあります。",
            f"今日はその核心を話します。",
            "",
            "【本編構成（3ポイント）】",
            f"1. なぜ{theme}が起きるのか（本当の原因）",
            f"2. 多くの人が間違えていること",
            f"3. 実際に変わるためにすること",
        ]
        if observation:
            body_parts.extend(["", "【専門家の観察から】", observation])
        if perspective:
            body_parts.extend(["", "【専門家の視点】", perspective])
        if diagnosis:
            body_parts.extend(["", "【診断・見極め方】", diagnosis])

        body_parts.extend([
            "",
            "【エンドカード】",
            "この動画が役に立ったらチャンネル登録をお願いします。",
            f"次は「{theme}に関連するテーマ」の動画もご覧ください。",
        ])
        body = "\n".join(body_parts)

        description = (
            f"{title}\n\n"
            f"▼ この動画の内容\n"
            f"00:00 はじめに\n"
            f"01:30 {theme}の本当の原因\n"
            f"05:00 よくある勘違い\n"
            f"09:00 実際にできること\n"
            f"12:00 まとめ\n\n"
            f"▼ 関連動画\n（関連動画リンクを追加）\n\n"
            f"▼ ご予約・お問い合わせ\nプロフィールのリンクからどうぞ。"
        )

        return PlatformContent(
            platform_id="youtube",
            format_type="video",
            hook=title,
            body=body,
            caption=description,
            cta="チャンネル登録をお願いします",
            metadata={
                "title":          title,
                "thumbnail":      thumbnail,
                "ideal_length":   "8〜15分",
                "chapters":       "00:00 / 01:30 / 05:00 / 09:00 / 12:00",
                "description":    description,
                "tags":           f"{theme}, 専門家, 解説, 方法",
            },
            generation_notes=(
                "【YouTube 制作メモ】\n"
                "  - タイトルはSEOキーワード＋感情を動かす言葉を両立する\n"
                "  - サムネイルは表情（驚き・笑顔・真剣）＋テキスト＋ビフォーアフター\n"
                "  - 冒頭30秒で「見る価値がある」を証明する\n"
                "  - 概要欄のタイムスタンプは必須\n"
                "  - 最低限の編集（無音・長い間を削除）は行う"
            ),
            dna_check=[
                "✅ タイトルにSEOキーワードが含まれているか",
                "✅ サムネイルコンセプトが明確か",
                "✅ 冒頭30秒に約束があるか",
                "✅ 章立てが明確か",
                "✅ InstagramのReelsを流用していないか",
            ],
        )


def _youtube_title(theme: str, perspective: str, observation: str) -> str:
    """クリックされるYouTubeタイトルを生成。"""
    if perspective and "だと思" not in perspective and len(perspective) <= 30:
        return f"【専門家が解説】{theme}の本当の原因と解決策"
    if observation and len(observation) <= 20:
        return f"現場で{observation}。{theme}を根本から直す方法"
    return f"【{theme}】プロが教える本当の原因と改善法"


def _youtube_thumbnail(theme: str, title: str) -> str:
    return (
        f"サムネイルコンセプト: \n"
        f"  - テキスト:「{theme[:12]}の本当の原因」（大きく）\n"
        f"  - 表情: 真剣・または驚き顔\n"
        f"  - 背景: ビフォーアフターか、施術シーン\n"
        f"  - 色: 目立つ（赤・黄・白のコントラスト）"
    )
