"""
creator_studio.py
【2026-07-01: Creator Studio MVP — 初回実装】
【2026-07-01(2回目): 4段階フォールバック実装】
【2026-07-01(3回目): セリフ・撮影順序・動画タイトルを具体化 — 考えずにそのまま撮影できるレベルへ】
【2026-07-01(4回目): Creator Intelligence Platform対応 — Vertical ローダー追加】

「撮影から投稿までの迷いをなくし、朝15分で撮影開始できる状態を作る」

フォールバック優先順位:
  Priority1: 今日の daily_content_picks（AI分析済み・Vertical向け投稿案）
  Priority2: VALIDATED KnowledgeUnits（実績に裏付けられたパターン）
  Priority3: 過去30日の Creator Studio（再利用）
  Priority4: Vertical の StructurePattern × core_hari_kb（KB駆動。KB不足 → knowledge_gap）

新規OpenAI呼び出しゼロ。main()の最後で1回だけ呼ぶ。
"""

import datetime
import textwrap
from typing import Optional

import sheets_writer
import config as _config

# ── Vertical ローダー ─────────────────────────────────────────────────────
# ACTIVE_VERTICAL に応じて Vertical 実装を動的にロードする。
# 将来の Vertical 追加時はここに elif を足すだけでよい。

def _load_vertical():
    vid = _config.ACTIVE_VERTICAL
    if vid == "core_hari":
        from creator_intelligence.verticals.core_hari.kb import CoreHariVertical
        return CoreHariVertical()
    raise ValueError(f"未知の ACTIVE_VERTICAL: '{vid}'。config.py または環境変数を確認してください。")

_VERTICAL = _load_vertical()

# ────────────────────────────────────────────────────────────────────────────
# 共通定数
# ────────────────────────────────────────────────────────────────────────────

# Vertical のブランドルールから定数を取得（CORE HARI 固定値を排除）
_BRAND = _VERTICAL.brand_rules()
_TARGET = _BRAND.target
_CTA_SAVE = _BRAND.cta_save
_CTA_FOLLOW = _BRAND.cta_follow
_CTA_DM = _BRAND.cta_contact

# 共通編集メモ（今日の動画専用に毎回組み立てる）
def _editing_notes(cut_count: int, total_sec: int) -> str:
    return (
        f"尺: {total_sec}秒 / カット数: {cut_count}カット\n"
        "字幕: 話したセリフをそのまま入れる / 太ゴシック / 白文字＋黒縁 / 画面下寄せ / 1行に収まる長さで改行\n"
        "BGM: ピアノ系またはLo-fi / 音量はセリフの30%に下げる\n"
        "色補正: 明るさ＋10〜15 / 彩度は変えない / 清潔感を優先\n"
        "カット切替: シンプルカット または 白フェード / ズームエフェクト禁止\n"
        "確認: 投稿前に音量・字幕・最後の笑顔カットを必ず確認する"
    )


# ────────────────────────────────────────────────────────────────────────────
# ブランドスコア計算
# ────────────────────────────────────────────────────────────────────────────

def _brand_score(hook: str, cta: str, theme: str):
    return _VERTICAL.score_content(hook, cta, theme)


# ────────────────────────────────────────────────────────────────────────────
# Priority4: Brand DNA Engine — 7本・曜日ローテーション
# セリフ・撮影順序・動画タイトルまで完全具体化済み
# ────────────────────────────────────────────────────────────────────────────

_DNA_TEMPLATES = [
    # ── 月曜 ── 保存ねらい / 教育型 / 仕組み解説
    {
        "theme":       "小顔矯正の仕組みを知ると怖くない",
        "video_title": "「小顔矯正って痛いの？」に正直に答えます",
        "mission":     "保存を狙う",
        "hook":        "小顔矯正って、痛いんですか？",
        "shot_sequence": """\
【カット1 / 3秒】スマホ固定・白い壁の前に立つ・無表情で静止
  → 画面にテキストを重ねる用。セリフなし。

【カット2 / 12秒】カメラ目線で話す
  セリフ:「小顔矯正って痛そう、怖そうって思ってませんか？
  　　　　仕組みを知れば、全然怖くないんです。
  　　　　3つに分けて説明しますね。」

【カット3 / 10秒】耳の周りを軽く手で触れながら話す
  セリフ:「1つ目は筋肉。顔の筋肉のコリをほぐすことで、
  　　　　顔の輪郭が引っ張られなくなります。」

【カット4 / 10秒】頬骨の下あたりを手でなぞりながら話す
  セリフ:「2つ目はリンパ。むくみをとるだけで
  　　　　顔が一回り小さく見えます。」

【カット5 / 10秒】カメラ目線に戻る
  セリフ:「3つ目は骨格の位置。繰り返し受けることで、
  　　　　顔のバランスが整ってきます。」

【カット6 / 5秒】笑顔でカメラ目線
  セリフ:「保存して、気になったときに読み返してください。」""",
        "script_full": """\
小顔矯正って痛そう、怖そうって思ってませんか？
仕組みを知れば、全然怖くないんです。
3つに分けて説明しますね。

1つ目は筋肉。
顔の筋肉のコリをほぐすことで、
顔の輪郭が引っ張られなくなります。

2つ目はリンパ。
むくみをとるだけで、顔が一回り小さく見えます。

3つ目は骨格の位置。
繰り返し受けることで、顔のバランスが整ってきます。

保存して、気になったときに読み返してください。""",
        "cta":     _CTA_SAVE,
        "caption": "「小顔矯正って怖そう…」そう思っていませんか？\n仕組みを知れば、全然怖くないんです🌿\n3ステップで解説しました。保存して、気になったときに読み返してください。",
        "cut_count": 6, "total_sec": 50,
    },

    # ── 火曜 ── 保存ねらい / 教育型 / 原因解説
    {
        "theme":       "顔のたるみは「顔筋」の衰えから来る",
        "video_title": "40代から老けて見える本当の理由",
        "mission":     "保存を狙う",
        "hook":        "最近、老けた気がする…それ、顔筋が原因かもしれません",
        "shot_sequence": """\
【カット1 / 3秒】白い壁の前・カメラ目線・静止
  → テキストフック用。セリフなし。

【カット2 / 12秒】カメラ目線で話す
  セリフ:「最近、なんか老けてきた気がする…
  　　　　そう感じていませんか？
  　　　　実は、顔の筋肉が落ちているサインなんです。」

【カット3 / 10秒】頬を軽く引き上げながら話す
  セリフ:「顔筋が衰えると、ほうれい線・フェイスライン・
  　　　　目元が重力で下がってきます。
  　　　　これが『老け見え』の正体です。」

【カット4 / 10秒】指で顔の筋肉の流れをなぞりながら話す
  セリフ:「でも、顔筋は鍛えられます。
  　　　　CORE HARIの施術は、この顔筋に直接アプローチします。」

【カット5 / 10秒】カメラ目線
  セリフ:「若い頃の顔に戻すのではなく、
  　　　　今の顔を一番いい状態にする。それが目的です。」

【カット6 / 5秒】笑顔
  セリフ:「保存して、気になったときに読み返してください。」""",
        "script_full": """\
最近、なんか老けてきた気がする…
そう感じていませんか？
実は、顔の筋肉が落ちているサインなんです。

顔筋が衰えると、ほうれい線・フェイスライン・目元が
重力で下がってきます。
これが「老け見え」の正体です。

でも、顔筋は鍛えられます。
CORE HARIの施術は、この顔筋に直接アプローチします。

若い頃の顔に戻すのではなく、
今の顔を一番いい状態にする。それが目的です。

保存して、気になったときに読み返してください。""",
        "cta":     _CTA_SAVE,
        "caption": "「最近、老けてきた気がする…」\nそれ、顔筋が原因かもしれません。\n顔筋を整えると何が変わるか、詳しく解説しました🌿\n保存して読み返してください。",
        "cut_count": 6, "total_sec": 50,
    },

    # ── 水曜 ── 保存ねらい / 誤解解消型 / 骨格よりむくみ
    {
        "theme":       "骨格より先にむくみとリンパを整える",
        "video_title": "「骨格だから無理」って、本当ですか？",
        "mission":     "保存を狙う",
        "hook":        "骨格だから小顔になれない、は本当に正しいですか？",
        "shot_sequence": """\
【カット1 / 3秒】静止・カメラ目線
  → テキストフック用。セリフなし。

【カット2 / 10秒】カメラ目線で話す
  セリフ:「骨格だから無理って、あきらめてませんか？
  　　　　実は、骨格より先に整えられることがあります。」

【カット3 / 12秒】耳の後ろ〜首にかけてリンパラインをなぞりながら
  セリフ:「小顔になれない理由の多くは、むくみとリンパの滞りです。
  　　　　ここを流すだけで、顔が一回り小さく見えます。
  　　　　これは骨格とは関係ありません。」

【カット4 / 10秒】カメラ目線
  セリフ:「CORE HARIでは、まずリンパとむくみを整えることから始めます。
  　　　　骨格の話はその次です。」

【カット5 / 10秒】笑顔を少し見せながら
  セリフ:「あきらめる前に、一度試してみてください。
  　　　　思っていたより変わります。」

【カット6 / 5秒】カメラ目線・笑顔
  セリフ:「保存して、気になったときに読み返してください。」""",
        "script_full": """\
骨格だから無理って、あきらめてませんか？
実は、骨格より先に整えられることがあります。

小顔になれない理由の多くは、むくみとリンパの滞りです。
ここを流すだけで、顔が一回り小さく見えます。
これは骨格とは関係ありません。

CORE HARIでは、まずリンパとむくみを整えることから始めます。
骨格の話はその次です。

あきらめる前に、一度試してみてください。
思っていたより変わります。

保存して、気になったときに読み返してください。""",
        "cta":     _CTA_SAVE,
        "caption": "「私、骨格だから無理かな…」\nでも、骨格より先に整えられることがあります🌿\nむくみとリンパの話、保存して読み返してください。",
        "cut_count": 6, "total_sec": 50,
    },

    # ── 木曜 ── フォローねらい / セルフケア / 表情グセ
    {
        "theme":       "無意識の表情グセが顔を変えている",
        "video_title": "知らないうちにやってる、顔を老けさせる3つのグセ",
        "mission":     "フォローを狙う",
        "hook":        "今日から直せる。顔を老けさせる表情グセ3つ",
        "shot_sequence": """\
【カット1 / 3秒】静止・カメラ目線
  → テキストフック用。セリフなし。

【カット2 / 10秒】カメラ目線で話す
  セリフ:「無意識にやっている表情のグセが、
  　　　　顔を老けさせています。
  　　　　今日は3つだけ紹介します。」

【カット3 / 8秒】眉間にシワを寄せて見せてから話す
  セリフ:「1つ目。眉間にシワを寄せるグセ。
  　　　　これを続けると縦ジワが定着します。」

【カット4 / 8秒】顎を前に突き出す動きを見せてから話す
  セリフ:「2つ目。顎を前に出して下を向くグセ。
  　　　　フェイスラインがたるんできます。」

【カット5 / 8秒】口を真一文字に結ぶ表情を見せてから話す
  セリフ:「3つ目。口を閉じるとき、グッと力を入れるグセ。
  　　　　ほうれい線が深くなりやすいです。」

【カット6 / 10秒】カメラ目線・穏やかな表情で
  セリフ:「3つとも、気づいたときに直すだけで変わります。
  　　　　フォローすると、毎週こういう情報を届けます。」""",
        "script_full": """\
無意識にやっている表情のグセが、顔を老けさせています。
今日は3つだけ紹介します。

1つ目。眉間にシワを寄せるグセ。
これを続けると縦ジワが定着します。

2つ目。顎を前に出して下を向くグセ。
フェイスラインがたるんできます。

3つ目。口を閉じるとき、グッと力を入れるグセ。
ほうれい線が深くなりやすいです。

3つとも、気づいたときに直すだけで変わります。
フォローすると、毎週こういう情報を届けます。""",
        "cta":     _CTA_FOLLOW,
        "caption": "知らないうちにやってる顔グセ、3つあります🌿\n今日から直せるものばかりです。\nフォローすると毎週セルフケア情報をお届けします。",
        "cut_count": 6, "total_sec": 47,
    },

    # ── 金曜 ── 問い合わせねらい / 体験訴求 / 変化の実感
    {
        "theme":       "月1回の施術で起きる変化",
        "video_title": "月1回だけで本当に変わるの？正直に答えます",
        "mission":     "問い合わせを狙う",
        "hook":        "月1回で変わりますか？と聞かれたら、正直に答えます",
        "shot_sequence": """\
【カット1 / 3秒】静止・カメラ目線
  → テキストフック用。セリフなし。

【カット2 / 10秒】カメラ目線で話す
  セリフ:「月1回だけで本当に変わるの？
  　　　　よく聞かれます。正直に答えますね。」

【カット3 / 12秒】指を1本立てながら話す
  セリフ:「1回目は、まず『軽さ』を感じます。
  　　　　顔のむくみがとれて、スッキリする感覚です。
  　　　　形の変化は、まだこの段階では出ません。」

【カット4 / 10秒】指を3本立てながら話す
  セリフ:「3回目あたりから、顔のラインが変わってきます。
  　　　　フェイスラインがシュッとしてきたと言われる方が多いです。」

【カット5 / 10秒】穏やかな表情で話す
  セリフ:「変化には個人差があります。でも続けると確実に変わります。
  　　　　それだけは自信を持って言えます。」

【カット6 / 5秒】カメラ目線・笑顔
  セリフ:「気になった方は、プロフィールのリンクからどうぞ。」""",
        "script_full": """\
月1回だけで本当に変わるの？
よく聞かれます。正直に答えますね。

1回目は、まず「軽さ」を感じます。
顔のむくみがとれて、スッキリする感覚です。
形の変化は、まだこの段階では出ません。

3回目あたりから、顔のラインが変わってきます。
フェイスラインがシュッとしてきたと言われる方が多いです。

変化には個人差があります。
でも続けると確実に変わります。
それだけは自信を持って言えます。

気になった方は、プロフィールのリンクからどうぞ。""",
        "cta":     _CTA_DM,
        "caption": "「月1回で本当に変わるの？」\n正直に答えます。\n1回目・3回目・6回目で何が起きるか解説しました🌿\nご予約・ご相談はプロフィールリンクから。",
        "cut_count": 6, "total_sec": 50,
    },

    # ── 土曜 ── 保存ねらい / 共感型 / 顔の左右差
    {
        "theme":       "顔の左右差はクセから来る",
        "video_title": "顔の左右差が気になる人へ。原因と対策を話します",
        "mission":     "保存を狙う",
        "hook":        "顔の左右、同じじゃないって気になってませんか？",
        "shot_sequence": """\
【カット1 / 3秒】静止・カメラ目線
  → テキストフック用。セリフなし。

【カット2 / 10秒】カメラ目線で話す
  セリフ:「顔の左右差が気になる…という方、多いんです。
  　　　　実は原因のほとんどは、日常のクセです。」

【カット3 / 10秒】右側と左側を交互に示しながら話す
  セリフ:「噛み癖・寝るときの向き・スマホを持つ手。
  　　　　こういったクセが積み重なって、左右差が出てきます。」

【カット4 / 10秒】頬骨あたりを手で触れながら話す
  セリフ:「クセを直すことと、施術でバランスを整えること。
  　　　　この2つを同時にやるのが、一番早いです。」

【カット5 / 10秒】カメラ目線・穏やかに
  セリフ:「左右差は、直せます。
  　　　　気になっているなら、あきらめないでください。」

【カット6 / 5秒】笑顔・カメラ目線
  セリフ:「保存して、気になったときに読み返してください。」""",
        "script_full": """\
顔の左右差が気になる…という方、多いんです。
実は原因のほとんどは、日常のクセです。

噛み癖・寝るときの向き・スマホを持つ手。
こういったクセが積み重なって、左右差が出てきます。

クセを直すことと、施術でバランスを整えること。
この2つを同時にやるのが、一番早いです。

左右差は、直せます。
気になっているなら、あきらめないでください。

保存して、気になったときに読み返してください。""",
        "cta":     _CTA_SAVE,
        "caption": "「顔の左右、なんか違う気がする…」\n原因はほぼ日常のクセです🌿\n直し方を解説しました。保存して読み返してください。",
        "cut_count": 6, "total_sec": 48,
    },

    # ── 日曜 ── 問い合わせねらい / 体験案内 / 初回の流れ
    {
        "theme":       "初めての小顔矯正、当日の流れ",
        "video_title": "初めての小顔矯正。当日に何をするか、全部見せます",
        "mission":     "問い合わせを狙う",
        "hook":        "初めての方へ。当日の流れを全部話します",
        "shot_sequence": """\
【カット1 / 3秒】静止・カメラ目線
  → テキストフック用。セリフなし。

【カット2 / 10秒】カメラ目線で話す
  セリフ:「初めての小顔矯正、何をするか分からなくて不安…
  　　　　そういう方のために、当日の流れを全部話します。」

【カット3 / 10秒】指を1本立てながら話す（サロン内で）
  セリフ:「まずカウンセリングです。
  　　　　今気になっている部分と、目指したいイメージを聞かせてください。
  　　　　これに10〜15分かけます。」

【カット4 / 10秒】施術ベッドの前で話す
  セリフ:「次が施術。60〜90分です。
  　　　　話しかけてもいいし、寝ていてもOKです。」

【カット5 / 10秒】カメラ目線に戻る
  セリフ:「施術後は、ホームケアの説明をして終わりです。
  　　　　押しつけはしません。必要だと思ったことだけお伝えします。」

【カット6 / 5秒】笑顔・カメラ目線
  セリフ:「気になった方は、プロフィールのリンクからどうぞ。」""",
        "script_full": """\
初めての小顔矯正、何をするか分からなくて不安…
そういう方のために、当日の流れを全部話します。

まずカウンセリングです。
今気になっている部分と、目指したいイメージを聞かせてください。
これに10〜15分かけます。

次が施術。60〜90分です。
話しかけてもいいし、寝ていてもOKです。

施術後は、ホームケアの説明をして終わりです。
押しつけはしません。必要だと思ったことだけお伝えします。

気になった方は、プロフィールのリンクからどうぞ。""",
        "cta":     _CTA_DM,
        "caption": "初めての小顔矯正、当日の流れを全部話します🌿\nカウンセリング・施術・アフターケア、隠しません。\nご予約・ご相談はプロフィールリンクから。",
        "cut_count": 6, "total_sec": 48,
    },
]


# ────────────────────────────────────────────────────────────────────────────
# record 組み立て共通関数
# ────────────────────────────────────────────────────────────────────────────

def _assemble(today: str, source_type: str, source_url: str, tmpl: dict,
              why_today: str, mission: str = "") -> dict:
    hook = tmpl.get("hook", "")
    cta = tmpl.get("cta", _CTA_SAVE)
    theme = tmpl.get("theme", "")
    score, notes = _brand_score(hook, cta, theme)
    cut_count = tmpl.get("cut_count", 6)
    total_sec = tmpl.get("total_sec", 50)
    script_full = tmpl.get("script_full", "")

    return {
        "date":          today,
        "source_type":   source_type,
        "source_url":    source_url,
        "today_mission": mission or tmpl.get("mission", "保存を狙う"),
        "theme":         theme,
        "video_title":   tmpl.get("video_title", theme),
        "why_today":     why_today,
        "target":        _TARGET,
        "hook":          hook,
        "script_15_30s": script_full[:150] + "…" if len(script_full) > 150 else script_full,
        "script_full":   script_full,
        "shot_sequence": tmpl.get("shot_sequence", ""),
        "shooting_location": "白い壁またはベージュ背景の前 / 自然光が入る場所",
        "shooting_cuts": tmpl.get("shot_sequence", "")[:200],
        "b_roll":        "施術中の手元アップ / ビフォーアフター / 笑顔のアウトロ",
        "editing_notes": _editing_notes(cut_count, total_sec),
        "cta":           cta,
        "caption":       tmpl.get("caption", ""),
        "threads_text":  "",
        "brand_score":   str(score),
        "brand_notes":   notes,
        "feedback_url_placeholder": "（投稿後にURLを記入 → manual_post_resultsシートへ）",
    }


# ────────────────────────────────────────────────────────────────────────────
# Priority1: daily_content_picks
# ────────────────────────────────────────────────────────────────────────────

def _try_priority1(today: str) -> Optional[dict]:
    try:
        picks = sheets_writer.get_today_daily_content_picks(today)
    except Exception as e:
        print(f"  ⚠️ P1 daily_content_picks読み込み失敗: {e}")
        return None
    if not picks:
        return None

    pick = picks[0]
    theme   = (pick.get("タイトル") or pick.get("投稿カテゴリ") or "今日の投稿").strip()
    body    = (pick.get("本文") or "").strip()
    caption = (pick.get("キャプション") or "").strip()
    cta     = (pick.get("CTA") or _CTA_SAVE).strip()
    hook    = body.split("。")[0].split("\n")[0][:50].strip() if body else f"「{theme}」について話します"

    # body をセリフ全文として使い、具体的な撮影順序を組み立てる
    body_lines = [l.strip() for l in body.replace("→", "\n").splitlines() if l.strip()]
    shot_parts = ["【カット1 / 3秒】静止・カメラ目線（テキストフック用・セリフなし）"]
    shot_parts.append(f'【カット2 / 10秒】カメラ目線で話す\n  セリフ:「{hook}」')
    for i, line in enumerate(body_lines[1:4], start=3):
        shot_parts.append(f'【カット{i} / 10秒】カメラ目線で話す\n  セリフ:「{line}」')
    shot_parts.append(f'【カット{len(shot_parts)+1} / 5秒】笑顔・カメラ目線\n  セリフ:「{cta}」')
    shot_seq = "\n\n".join(shot_parts)

    # 動画タイトル: "タイトル" があればそのまま、なければフックから生成
    video_title = theme if len(theme) <= 30 else hook[:35]

    tmpl = {
        "theme":         theme,
        "video_title":   video_title,
        "mission":       "問い合わせを狙う" if "予約" in cta or "dm" in cta.lower() else "保存を狙う",
        "hook":          hook,
        "shot_sequence": shot_seq,
        "script_full":   body,
        "cta":           cta,
        "caption":       caption or f"{theme}について解説しました。保存して読み返してください。",
        "cut_count":     len(shot_parts),
        "total_sec":     len(shot_parts) * 9,
    }
    why = (
        "daily_content_picksが選んだ今日の投稿案です。"
        "North Star分析とResearch Candidate Scoreで選定されました。"
    )
    print("  Creator Studio: Priority1（daily_content_picks）を使用")
    return _assemble(today, "daily_content_picks",
                     pick.get("投稿URL", ""), tmpl, why)


# ────────────────────────────────────────────────────────────────────────────
# Priority2: VALIDATED KnowledgeUnits
# ────────────────────────────────────────────────────────────────────────────

def _try_priority2(today: str) -> Optional[dict]:
    try:
        rows = sheets_writer.get_knowledge_units()
    except Exception as e:
        print(f"  ⚠️ P2 knowledge_units読み込み失敗: {e}")
        return None

    validated = sorted(
        [r["values"] for r in rows if r["values"].get("status") in ("VALIDATED", "ACTIVE")],
        key=lambda v: float(v.get("confidence") or 0), reverse=True
    )
    if not validated:
        return None

    def pick(dim):
        return next((v for v in validated if v.get("dimension") == dim), None)

    hook_u = pick("Hook")
    if not hook_u:
        return None

    struct_u  = pick("Structure")
    psych_u   = pick("Psychology")
    cta_u     = pick("CTA")

    hook_text   = (hook_u.get("description") or hook_u.get("pattern_name") or "")[:50]
    struct_text = (struct_u or {}).get("pattern_name") or "問題提示→解決策→CTA"
    psych_text  = (psych_u or {}).get("pattern_name") or "共感"
    cta_text    = (cta_u or {}).get("pattern_name") or _CTA_SAVE

    theme       = f"{hook_u.get('pattern_name', 'CORE HARI FACE投稿')}"
    video_title = hook_text[:35] if hook_text else theme

    confs = [float(u.get("confidence") or 0)
             for u in [hook_u, struct_u, psych_u, cta_u] if u]
    avg_conf = round(sum(confs) / len(confs), 2) if confs else 0

    shot_seq = (
        f"【カット1 / 3秒】静止・カメラ目線（テキストフック用・セリフなし）\n\n"
        f"【カット2 / 12秒】カメラ目線で話す\n"
        f"  セリフ:「{hook_text}」\n\n"
        f"【カット3 / 15秒】構成に沿って話す\n"
        f"  構成: {struct_text}（心理: {psych_text}）\n\n"
        f"【カット4 / 5秒】笑顔・カメラ目線\n"
        f"  セリフ:「{cta_text}」"
    )
    script = (
        f"{hook_text}\n\n"
        f"{struct_text}の流れで話す（心理: {psych_text}）\n\n"
        f"{cta_text}"
    )
    dims = [u.get("dimension") for u in [hook_u, struct_u, psych_u, cta_u] if u]
    why = (
        f"VALIDATED KnowledgeUnits（{', '.join(dims)} / 平均confidence: {avg_conf}）"
        f"から組み立てました。実績データに裏付けられたパターンの組み合わせです。"
    )
    tmpl = {
        "theme": theme, "video_title": video_title,
        "mission": "保存を狙う", "hook": hook_text,
        "shot_sequence": shot_seq, "script_full": script,
        "cta": cta_text,
        "caption": f"{hook_text}…\nCORE HARI FACEが詳しく解説します🌿\n{_CTA_SAVE}",
        "cut_count": 4, "total_sec": 35,
    }
    print(f"  Creator Studio: Priority2（VALIDATED KnowledgeUnits {len(dims)}次元）を使用")
    return _assemble(today, "knowledge_units_validated", "", tmpl, why)


# ────────────────────────────────────────────────────────────────────────────
# Priority3: 過去30日の高スコア Creator Studio
# ────────────────────────────────────────────────────────────────────────────

def _try_priority3(today: str) -> Optional[dict]:
    try:
        records = sheets_writer.get_recent_creator_studio_records(days=30)
    except Exception as e:
        print(f"  ⚠️ P3 creator_studio_daily読み込み失敗: {e}")
        return None

    candidates = [r for r in records
                  if r.get("date") != today and r.get("source_type") != "brand_template"]
    if not candidates:
        return None

    best = candidates[0]
    why = (
        f"Priority1・2が取得できなかったため、"
        f"{best.get('date', '過去')}（Brand Score {best.get('brand_score', '?')}）の"
        f"実績ブリーフを再利用しています。「{best.get('theme', '')}」のパターンが今日も有効です。"
    )
    record = dict(best)
    record["date"]        = today
    record["source_type"] = "reused_past_brief"
    record["why_today"]   = why
    print(f"  Creator Studio: Priority3（{best.get('date')}の実績ブリーフ再利用）を使用")
    return record


# ────────────────────────────────────────────────────────────────────────────
# Priority4: Brand DNA Engine
# ────────────────────────────────────────────────────────────────────────────

def _priority4(today: str) -> dict:
    dow  = datetime.date.today().weekday()  # 0=月 〜 6=日
    tmpl = _DNA_TEMPLATES[dow % len(_DNA_TEMPLATES)]
    why  = (
        f"Priority1〜3が利用できないため、Brand DNA Engine（曜日{dow+1}番）を使用しています。"
        "CORE HARI FACEのMission・Targetから直接組み立てた恒久コンテンツです。"
    )
    print(f"  Creator Studio: Priority4（Brand DNA: {tmpl['theme']}）を使用")
    return _assemble(today, "brand_dna", "", tmpl, why)


# ────────────────────────────────────────────────────────────────────────────
# メイン公開関数
# ────────────────────────────────────────────────────────────────────────────

def generate_creator_studio_daily() -> Optional[dict]:
    """4段階フォールバックで必ず「今日撮る1本」を出力する。"""
    today = datetime.date.today().isoformat()

    record = (
        _try_priority1(today)
        or _try_priority2(today)
        or _try_priority3(today)
        or _priority4(today)
    )

    try:
        sheets_writer.save_creator_studio_daily(record)
        print(f"  ✓ creator_studio_daily に保存（source: {record.get('source_type')}）")
    except Exception as e:
        print(f"  ⚠️ creator_studio_daily 保存失敗: {e}")

    return record


# ────────────────────────────────────────────────────────────────────────────
# ターミナル表示 — 考えずにそのまま撮影できるレベルで出力する
# ────────────────────────────────────────────────────────────────────────────

def print_creator_studio_summary(record: dict) -> None:
    W = 62
    BAR = "=" * W
    bar = "─" * W

    _LABELS = {
        "daily_content_picks":      "[P1] AI分析済み",
        "knowledge_units_validated": "[P2] VALIDATEDパターン",
        "reused_past_brief":        "[P3] 過去実績再利用",
        "brand_dna":                "[P4] Brand DNA",
    }
    label = _LABELS.get(record.get("source_type", ""), record.get("source_type", ""))

    def block(title: str, body: str) -> None:
        print(f"\n▼ {title}")
        for line in body.splitlines():
            print(f"  {line}")

    print(f"\n{BAR}")
    print(f"  今日のCreator Studio  {label}")
    print(BAR)

    # ── 今日の1本 ──────────────────────────────
    print(f"\n  目的：{record.get('today_mission', '')}")
    print(f"  テーマ：{record.get('theme', '')}")
    print(f"\n  ┌{'─'*(W-2)}┐")
    title_line = f"  動画タイトル：{record.get('video_title', '')}"
    print(f"  │ {title_line:<{W-4}} │")
    print(f"  └{'─'*(W-2)}┘")

    # ── なぜ今日これか ─────────────────────────
    block("なぜ今日これか", record.get("why_today", ""))

    # ── フック ────────────────────────────────
    print(f"\n{bar}")
    print("▼ 冒頭フック（画面に出るテキスト）")
    print(f"\n    「{record.get('hook', '')}」\n")
    print(bar)

    # ── 撮影順序 ──────────────────────────────
    print("\n▼ 撮影順序（この番号順に撮る）")
    shot = record.get("shot_sequence", "")
    if shot:
        for line in shot.splitlines():
            print(f"  {line}")
    else:
        print("  （撮影順序データなし）")

    # ── セリフ全文 ────────────────────────────
    print(f"\n{bar}")
    print("▼ セリフ全文（読み上げ用・そのまま話してOK）")
    print(bar)
    script = record.get("script_full", record.get("script_15_30s", ""))
    if script:
        print()
        for line in script.splitlines():
            print(f"    {line}")
    print()

    # ── 編集メモ ──────────────────────────────
    block("編集メモ", record.get("editing_notes", ""))

    # ── CTA ───────────────────────────────────
    print(f"\n▼ CTA（動画の最後に言う）")
    print(f"\n    「{record.get('cta', '')}」\n")

    # ── 投稿キャプション ──────────────────────
    print(bar)
    print("▼ 投稿キャプション（コピペ用）")
    print(bar)
    caption = record.get("caption", "")
    if caption:
        print()
        for line in caption.splitlines():
            print(f"  {line}")
    print()

    # ── Brand Check ───────────────────────────
    score = record.get("brand_score", "")
    print(f"▼ Brand Check: {score}/100")
    notes = record.get("brand_notes", "")
    for line in notes.splitlines():
        print(f"  {line}")

    print(f"\n{BAR}")
