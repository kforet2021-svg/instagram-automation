"""
creator_studio.py
【2026-07-01: Creator Studio MVP — 初回実装】
【2026-07-01(2回目): 4段階フォールバック実装】
【2026-07-01(3回目): セリフ・撮影順序・動画タイトルを具体化】
【2026-07-01(4回目): Creator Intelligence Platform対応 — Vertical ローダー追加】
【2026-07-02: 出力を「撮影指示書」フォーマット①〜⑧に全面刷新】
【2026-07-02(2回目): ⑨水平思考・⑩Creator Review・⑪CEO Challengeを追加（OpenAIコストゼロ）】
【2026-07-02(3回目): ⑪CEO Challengeに「他サロンでも言えるか？」ゲートを追加 — NOになるまで改善】

目的：Creator Studioを開いたら5分以内に撮影を開始できる状態を作る。
      分析結果の表示ではなく、今日そのまま使える撮影指示書として出力する。

フォールバック優先順位:
  Priority1: 今日の daily_content_picks（AI分析済み投稿案）
  Priority2: VALIDATED KnowledgeUnits（実績に裏付けられたパターン）
  Priority3: 過去30日の Creator Studio（再利用）
  Priority4: Brand DNA（曜日ローテーション・Vertical専門知識を反映）

新規OpenAI呼び出しゼロ。main()の最後で1回だけ呼ぶ。
"""

import datetime
from typing import Optional

import sheets_writer
import config as _config


# ── Vertical ローダー ─────────────────────────────────────────────────────

def _load_vertical():
    vid = _config.ACTIVE_VERTICAL
    if vid == "core_hari":
        from creator_intelligence.verticals.core_hari.kb import CoreHariVertical
        return CoreHariVertical()
    raise ValueError(f"未知の ACTIVE_VERTICAL: '{vid}'")

_VERTICAL = _load_vertical()
_BRAND    = _VERTICAL.brand_rules()
_TARGET   = _BRAND.target
_CTA_SAVE    = _BRAND.cta_save
_CTA_FOLLOW  = _BRAND.cta_follow
_CTA_DM      = _BRAND.cta_contact


# ────────────────────────────────────────────────────────────────────────────
# ブランドスコア（Vertical 委譲）
# ────────────────────────────────────────────────────────────────────────────

def _brand_score(hook: str, cta: str, theme: str):
    return _VERTICAL.score_content(hook, cta, theme)


# ────────────────────────────────────────────────────────────────────────────
# 編集指示テンプレート（全動画共通の構造。尺とカット数だけ変わる）
# ────────────────────────────────────────────────────────────────────────────

def _build_editing_notes(total_sec: int, cut_count: int) -> str:
    return (
        f"【尺】目標 {total_sec}秒（{cut_count}カット）\n"
        "【字幕】話したセリフをそのまま入れる／太ゴシック／白文字＋黒縁／画面下寄せ\n"
        "       1行20〜25文字以内で改行。長い文は2行に分ける\n"
        "【BGM】ピアノ系 or Lo-fi／セリフの30%以下の音量\n"
        "【色味】明るさ ＋10〜15／彩度は変えない／清潔感を最優先\n"
        "【カット割り】シンプルカット or 白フェード／ズームエフェクト禁止\n"
        "【確認】投稿前に①音量②字幕③最後の笑顔カットを必ず確認する"
    )


# ────────────────────────────────────────────────────────────────────────────
# Priority4: Brand DNA — 7本（月〜日）
#
# 【構造はInstagramから、内容はCORE HARIの専門性から】
#   hook_type / structure / psychology_trigger = Instagram分析から学んだ型
#   hook / hook_text / script_full / shot_sequence = CORE HARIの考え方・専門知識
#
# hook_text  : 画面に出すテロップ（0〜3秒）
# hook       : 口で話すセリフ（0〜3秒）
# script_full: 3〜30秒で話す台本（そのまま読む）
# shot_sequence: カット×詳細指示（場所・フレーム・表情・角度・セリフ・B-roll）
# editing_notes: 尺・字幕・BGM・色味・カット割り
# threads_text: Threadsに投稿するテキスト
# ────────────────────────────────────────────────────────────────────────────

_DNA_TEMPLATES = [

    # ── 月曜 ─────────────────────────────────────────────────────────
    # 構造: 疑問提示 → 核心2点（表情筋） → 保存CTA / 目標20秒
    {
        "theme":     "小顔矯正が何にアプローチするか",
        "mission":   "保存を狙う",
        "video_title": "「小顔矯正って何をするの？」に正直に答えます",

        "hook_text":
            "小顔矯正って\n何をするの？",

        "hook":
            "「小顔矯正って、何をするんですか？」\nよく聞かれます。正直に答えますね。",

        "script_full": """\
施術は3つに同時にアプローチしています。

まず、表情筋のコリをほぐすこと。
顔には約60種類の筋肉があって、使い方の偏りがコリを生みます。
コリが残ったままだと、皮膚が引っ張られてフェイスラインが崩れます。

次に、リンパを流す。そして骨格の位置を整える。
この3つ同時にアプローチするのがポイントです。

保存して、気になったときに読み返してください。""",

        "shot_sequence": """\
【カット1 / 2秒】フック用・静止カット
  場所　: 白い壁またはベージュ壁の前（自然光必須）
  フレーム: バストアップ・正面
  表情　: 穏やかに静止（まだ話さない）
  ★ テキスト「小顔矯正って何をするの？」を画面に重ねる

【カット2 / 13秒】解説・カメラ目線 + 手元B-roll
  フレーム: バストアップ・正面 → フェイスライン沿いを指でなぞる手元
  動き　: 「表情筋のコリ」の説明で頬骨下（咬筋）を軽く触れて示す
  表情　: 誠実。「これ大事です」という前のめりのトーン
  セリフ:「施術は3つ同時にアプローチしています。
          まず表情筋のコリをほぐすこと。顔には約60種類の筋肉があって、
          使い方の偏りがコリを生みます。
          次にリンパを流す、骨格の位置を整える。この3つです。」

【カット3 / 5秒】CTA・笑顔
  フレーム: バストアップ・正面
  表情　: 温かく自然な笑顔
  セリフ:「保存して、気になったときに読み返してください。」""",

        "editing_notes": _build_editing_notes(20, 3),

        "cta":     _CTA_SAVE,
        "caption": """\
「小顔矯正って何をするの？」

正直に答えると、3つのことに同時にアプローチしています。

①表情筋のコリをほぐす（顔の筋肉は約60種類）
②リンパを流してむくみを取る
③骨格の位置を整える

どれかひとつではなく、3つ同時にアプローチするのがポイントです。

保存して、気になったときに読み返してください🌿

#小顔矯正 #フェイシャルエステ #札幌エステ #たるみ改善 #顔筋トレーニング #COREHARI""",

        "threads_text": """\
「小顔矯正って何をするの？」に正直に答えます。

①表情筋のコリをほぐす
②リンパを流す
③骨格の位置を整える

「骨格だから無理」と思っていた方に知ってほしいです。
まず①②から変わることが多いです。""",

        "cut_count": 3, "total_sec": 20,
    },

    # ── 火曜 ─────────────────────────────────────────────────────────
    # 構造: 共感 → 専門的な原因（咬筋優位・表情グセ） → 保存CTA / 目標21秒
    {
        "theme":     "老け見えの正体は顔筋の衰え",
        "mission":   "保存を狙う",
        "video_title": "「最近老けた気がする」はスキンケアの問題じゃないかもしれない",

        "hook_text":
            "最近、老けた気がする\nと思ったら見てください",

        "hook":
            "「最近、なんか老けてきた気がする…」\nスキンケアの問題じゃないかもしれません。",

        "script_full": """\
顔の老け見えの正体は、多くの場合「表情筋の使い方の偏り」です。

特に多いのが咬筋優位。
片側だけで噛む・奥歯を食いしばる習慣が続くと、
咬筋が発達してフェイスラインが張ってきます。

表情グセも原因になります。
眉間にシワを寄せる・口をギュッと閉じる。
このクセが毎日積み重なって、顔の形が変わっていきます。

保存して、気になったときに読み返してください。""",

        "shot_sequence": """\
【カット1 / 2秒】フック用・静止カット
  場所　: 白い壁の前・自然光
  フレーム: バストアップ・正面
  表情　: 少し真剣に静止
  ★ テキスト「最近、老けた気がする と思ったら見てください」を重ねる

【カット2 / 14秒】原因解説・カメラ目線 + 実演
  フレーム: バストアップ・正面
  動き　:「咬筋優位」の説明では頬骨の下を指で触れて示す
          「表情グセ」では眉間を軽くシワ寄せした表情を1秒見せてから元に戻す
  表情　: 「これが原因です」という誠実な説明口調
  セリフ:「顔の老け見えの正体は表情筋の使い方の偏りです。
          特に多いのが咬筋優位。片側噛み・食いしばりが続くと
          フェイスラインが張ってきます。
          表情グセも原因です。眉間のシワ・口の食いしばり。
          このクセが積み重なって顔が変わります。」

【カット3 / 5秒】CTA・笑顔
  フレーム: バストアップ・正面
  表情　: 温かく、希望を感じさせる笑顔
  セリフ:「保存して、気になったときに読み返してください。」""",

        "editing_notes": _build_editing_notes(21, 3),

        "cta":     _CTA_SAVE,
        "caption": """\
「最近、老けた気がする…」

それ、スキンケアの問題じゃないかもしれません。

顔の老け見えの正体は「表情筋の使い方の偏り」です。

よくあるのが咬筋優位。
片側噛み・食いしばりが続くと、フェイスラインが張ってきます。

表情グセも原因です。
眉間のシワ・口の食いしばり。
このクセが積み重なって顔が変わります。

保存して、読み返してください🌿

#老け見え #咬筋 #表情グセ #フェイスライン #たるみ改善 #小顔矯正 #札幌エステ #COREHARI""",

        "threads_text": """\
「最近、老けてきた気がする…」

スキンケアじゃなく、表情筋の使い方が原因かもしれないです。

咬筋優位（片側噛み・食いしばり）でフェイスラインが張る。
表情グセ（眉間のシワ・口の食いしばり）でシワが深くなる。

クセに気づくことが最初の一歩です。""",

        "cut_count": 3, "total_sec": 21,
    },

    # ── 水曜 ─────────────────────────────────────────────────────────
    # 構造: 通説への疑問 → 正しい順番 → 保存CTA / 目標20秒
    {
        "theme":     "骨格より先にむくみとリンパを整える",
        "mission":   "保存を狙う",
        "video_title": "「骨格だから無理」は本当ですか？",

        "hook_text":
            "骨格だから無理\nって思ってませんか？",

        "hook":
            "「骨格だから、小顔は無理」\nそう思っているなら、少し聞いてください。",

        "script_full": """\
骨格の大きさは変わりません。正直に言います。

でも、顔が大きく見える原因のほとんどは骨格ではなく、
表情筋のコリとリンパの滞りです。

まずここを整えること。
骨格の話はその後で判断してほしいんです。

CORE HARIでは、筋肉とリンパを整えるところから始めます。
それだけで、顔の印象がかなり変わります。

保存して、気になったときに読み返してください。""",

        "shot_sequence": """\
【カット1 / 2秒】フック用・静止カット
  場所　: 白い壁の前・自然光
  フレーム: バストアップ・正面
  表情　: 静止。少し真剣な目線
  ★ テキスト「骨格だから無理って思ってませんか？」を重ねる

【カット2 / 13秒】解説・カメラ目線
  フレーム: バストアップ・正面
  動き　: リンパラインを耳の下から首にかけて指でなぞる
  表情　: 「本当のことを伝えたい」という誠実さ
  セリフ:「骨格の大きさは変わりません。正直に言います。
          でも顔が大きく見える原因のほとんどは、
          表情筋のコリとリンパの滞りです。
          まずここを整えること。骨格の判断はその後でしてほしいんです。
          それだけで顔の印象がかなり変わります。」

【カット3 / 5秒】CTA・笑顔
  フレーム: バストアップ・正面
  表情　: 温かく、希望を感じさせる笑顔
  セリフ:「保存して、気になったときに読み返してください。」""",

        "editing_notes": _build_editing_notes(20, 3),

        "cta":     _CTA_SAVE,
        "caption": """\
「骨格だから、小顔は無理…」

本当にそうでしょうか？

骨格の大きさは変わりません。正直に言います。
でも、顔が大きく見える原因のほとんどは骨格ではなく
「表情筋のコリ」と「リンパの滞り」です。

まずここを整えてから、骨格がどうかを判断してほしいんです。

保存して、読み返してください🌿

#骨格 #小顔 #表情筋 #リンパ #小顔矯正 #フェイシャルエステ #札幌 #COREHARI""",

        "threads_text": """\
「骨格だから無理」って思ってる方へ。

骨格の大きさは変わりません。正直に言います。
でも顔が大きく見える原因のほとんどは表情筋のコリとリンパの滞りです。

まずそこを整えてから骨格の話をしてほしいです。""",

        "cut_count": 3, "total_sec": 20,
    },

    # ── 木曜 ─────────────────────────────────────────────────────────
    # 構造: 気づき促進 → 咬筋優位 + 舌の位置 → フォローCTA / 目標22秒
    {
        "theme":     "顔を老けさせている3つのグセ",
        "mission":   "フォローを狙う",
        "video_title": "顔を老けさせている2大グセ、教えます",

        "hook_text":
            "顔を老けさせている\n2大グセ、教えます",

        "hook":
            "無意識にやっているグセが、顔を老けさせています。\n今日は2つだけ話します。",

        "script_full": """\
1つ目は、咬筋優位。
片側だけで噛む・奥歯を食いしばる。
このクセが続くと、咬筋が大きくなってフェイスラインが張ってきます。

2つ目は、舌の位置。
舌が下に落ちた状態が続くと、フェイスラインがたるんできます。
正しい位置は、舌を上あごにつけた状態です。

どちらも、気づいたときに直すだけで変わってきます。

フォローすると、毎週こういう情報を届けます。""",

        "shot_sequence": """\
【カット1 / 2秒】フック用・静止カット
  場所　: 白い壁の前・自然光
  フレーム: バストアップ・正面
  表情　: 穏やかに静止
  ★ テキスト「顔を老けさせている2大グセ、教えます」を重ねる

【カット2 / 15秒】グセ実演・カメラ目線
  フレーム: バストアップ・正面
  動き①: 「咬筋優位」の説明で頬骨下（咬筋）を指で触れて示す
  動き②: 「舌の位置」で口を自然に開け、舌が下に落ちた状態を1秒見せてから
          「上あごにつける」正しい位置に直して見せる
  表情　: 「知ってほしいことがある」という前のめりのトーン
  セリフ:「1つ目は咬筋優位。片側噛み・食いしばりが続くと
          咬筋が大きくなってフェイスラインが張ります。
          2つ目は舌の位置。舌が下に落ちていると、フェイスラインがたるみます。
          正しい位置は、舌を上あごにつけた状態です。
          どちらも気づいたときに直すだけで変わってきます。」

【カット3 / 5秒】CTA・笑顔
  フレーム: バストアップ・正面
  表情　: 温かく「一緒に変えていきましょう」という雰囲気
  セリフ:「フォローすると毎週こういう情報を届けます。」""",

        "editing_notes": _build_editing_notes(22, 3),

        "cta":     _CTA_FOLLOW,
        "caption": """\
顔を老けさせている2大グセ、教えます。

①咬筋優位
片側だけで噛む・奥歯を食いしばる
→ 咬筋が大きくなってフェイスラインが張る

②舌の位置
舌が下に落ちた状態が続く
→ フェイスラインがたるんでくる
（正しい位置：舌を上あごにつける）

どちらも、気づいたときに直すだけで変わります🌿

フォローすると毎週こういう情報をお届けします。

#咬筋 #舌の位置 #フェイスライン #表情グセ #たるみ予防 #フェイシャルエステ #札幌 #COREHARI""",

        "threads_text": """\
顔を老けさせている2大グセ。

①咬筋優位（片側噛み・食いしばり）→ フェイスラインが張る
②舌が下に落ちている → フェイスラインがたるむ

どちらも「気づいて直す」だけ。
知っているかどうかで、10年後の顔が変わります。""",

        "cut_count": 3, "total_sec": 22,
    },

    # ── 金曜 ─────────────────────────────────────────────────────────
    # 構造: 正直フック → 回数ごとの変化 → 問い合わせCTA / 目標22秒
    {
        "theme":     "施術回数ごとの正直なタイムライン",
        "mission":   "問い合わせを狙う",
        "video_title": "1回目・3回目・6回目で何が変わるか、正直に話します",

        "hook_text":
            "何回で変わりますか？\nに正直に答えます",

        "hook":
            "「何回で変わりますか？」よく聞かれます。\n正直に答えますね。",

        "script_full": """\
1回目。
感覚変化が主です。スッキリした、軽くなった。
形の変化はまだ出ません。正直に言います。

3回目前後。
フェイスラインの変化を感じ始める方が増えます。
表情筋のコリが取れてくると、顔の印象が変わってきます。

6回以上。
変化が定着します。施術の間隔を空けても戻りにくくなります。

個人差はあります。
でも続けると確実に変わります。それだけは言えます。

気になった方は、プロフィールのリンクからどうぞ。""",

        "shot_sequence": """\
【カット1 / 2秒】フック用・静止カット
  場所　: 白い壁の前・自然光
  フレーム: バストアップ・正面
  表情　: 穏やかに静止
  ★ テキスト「何回で変わりますか？ に正直に答えます」を重ねる

【カット2 / 16秒】回数別変化・カメラ目線
  フレーム: バストアップ・正面
  動き　: 指を1本→3本→6本と立てながら話す
  表情　: 誠実。「本当のことを言います」という真剣さ
  セリフ:「1回目は感覚変化が主です。スッキリした、軽くなった。
          形の変化はまだ出ません。正直に言います。
          3回目前後から表情筋のコリが取れてきて、顔の印象が変わってきます。
          6回以上で変化が定着します。
          個人差はあります。でも続けると確実に変わります。それだけは言えます。」

【カット3 / 5秒】CTA・笑顔
  フレーム: バストアップ・正面
  表情　: 誠実さと希望が同居した表情
  セリフ:「気になった方は、プロフィールのリンクからどうぞ。」""",

        "editing_notes": _build_editing_notes(23, 3),

        "cta":     _CTA_DM,
        "caption": """\
「何回で変わりますか？」に正直に答えます。

1回目
→ 感覚変化が主。スッキリした、軽くなった。
  形の変化はまだ出ません。

3回目前後
→ 表情筋のコリが取れてきて、顔の印象が変わり始める。
  周りから「何か変わった？」と言われる時期。

6回以上
→ 変化が定着する。間隔を空けても戻りにくくなる。

個人差はあります。でも続けると確実に変わります🌿

ご予約・ご相談はプロフィールのリンクからどうぞ。

#小顔矯正 #フェイシャルエステ #札幌エステ #フェイスライン #たるみ改善 #COREHARI""",

        "threads_text": """\
「何回で変わりますか？」に正直に答えます。

1回目：感覚変化のみ。形はまだ。
3回目：表情筋のコリが取れ、顔の印象が変わり始める。
6回以上：変化が定着して戻りにくくなる。

個人差はある。でも続けると確実に変わります。""",

        "cut_count": 3, "total_sec": 23,
    },

    # ── 土曜 ─────────────────────────────────────────────────────────
    # 構造: 共感 → 専門的な原因（咬筋・舌・姿勢） → 保存CTA / 目標21秒
    {
        "theme":     "顔の左右差はクセから来る",
        "mission":   "保存を狙う",
        "video_title": "顔の左右差の正体、話します",

        "hook_text":
            "顔の左右差\n気になってませんか？",

        "hook":
            "顔の左右差が気になる…という方、実はすごく多いんです。",

        "script_full": """\
顔の左右差の原因のほとんどは、日常のクセです。

噛み癖で咬筋の左右差が生まれます。
いつも同じ向きで寝ると、骨格と筋肉が偏ります。
スマホを見る姿勢・頬杖も原因になります。

クセを直すこと、施術でバランスを整えること。
この2つを同時にやるのが一番早いです。

左右差は直せます。あきらめないでください。

保存して、気になったときに読み返してください。""",

        "shot_sequence": """\
【カット1 / 2秒】フック用・静止カット
  場所　: 白い壁の前・自然光
  フレーム: バストアップ・正面
  表情　: 穏やかに静止
  ★ テキスト「顔の左右差 気になってませんか？」を重ねる

【カット2 / 14秒】原因解説・カメラ目線 + 実演
  フレーム: バストアップ・正面
  動き①: 「噛み癖」で左側の咬筋（頬骨下）を指で触れて示す
  動き②: 「頬杖」の姿勢を1秒実演してから元に戻す
  表情　: 「これが原因です」という分かりやすい説明口調
  セリフ:「顔の左右差の原因のほとんどは日常のクセです。
          噛み癖で咬筋の左右差が生まれる。
          いつも同じ向きで寝ると骨格と筋肉が偏る。
          頬杖・スマホ姿勢も原因です。
          クセを直すことと施術でバランスを整えること。
          この2つを同時にやるのが一番早いです。」

【カット3 / 5秒】CTA・笑顔
  フレーム: バストアップ・正面
  表情　: 温かく、希望を感じさせる笑顔
  セリフ:「左右差は直せます。あきらめないでください。
          保存して、読み返してください。」""",

        "editing_notes": _build_editing_notes(21, 3),

        "cta":     _CTA_SAVE,
        "caption": """\
顔の左右差が気になる方へ。

原因のほとんどは、日常のクセです。

・噛み癖 → 咬筋の左右差が生まれる
・いつも同じ向きで寝る → 骨格と筋肉が偏る
・頬杖・スマホ姿勢 → 片側に力がかかり続ける

クセを直すこと ＋ 施術でバランスを整えること。
この2つを同時にやるのが一番早いです🌿

左右差は、直せます。あきらめないでください。

#顔の左右差 #咬筋 #小顔矯正 #フェイシャルエステ #顔筋 #フェイスライン #札幌 #COREHARI""",

        "threads_text": """\
顔の左右差が気になっている方へ。

原因のほとんどは日常のクセです。
噛み癖・寝る向き・頬杖・スマホ姿勢。

咬筋の左右差が特に影響します。
クセを直すこと＋施術でバランスを整えること。この2つが一番早いです。

左右差は直せます。""",

        "cut_count": 3, "total_sec": 21,
    },

    # ── 日曜 ─────────────────────────────────────────────────────────
    # 構造: 不安の解消 → 当日の流れ全公開 → 問い合わせCTA / 目標22秒
    {
        "theme":     "初めての小顔矯正・当日の流れ",
        "mission":   "問い合わせを狙う",
        "video_title": "初めての方へ。当日の流れを全部話します",

        "hook_text":
            "初めての小顔矯正\n当日に何をするか全部話します",

        "hook":
            "初めての小顔矯正、当日に何をするか分からなくて不安…\nそういう方のために、全部話します。",

        "script_full": """\
まず、カウンセリング。10〜15分。
今気になっている部分と、表情グセや姿勢の癖があれば聞かせてください。
押しつけは一切しません。

次が施術。60〜90分。
話しかけてもいいし、寝ていてもOKです。

施術後はホームケアの説明をして終わりです。
必要だと思ったことだけお伝えします。無理に何かを売ったりしません。

気になった方は、プロフィールのリンクからどうぞ。""",

        "shot_sequence": """\
【カット1 / 2秒】フック用・静止カット
  場所　: サロンの入り口 or 白い壁の前
  フレーム: バストアップ・正面
  表情　: 穏やかに静止
  ★ テキスト「初めての小顔矯正 当日に何をするか全部話します」を重ねる

【カット2 / 15秒】流れ説明・カメラ目線
  フレーム: バストアップ・正面
  B-roll: カウンセリングシートを持つ手元（カット中に挿入）
  表情　: 「あなたの不安を分かっています」という安心感のある表情
  セリフ:「まずカウンセリング10〜15分。
          気になる部分と、表情グセや姿勢の癖があれば聞かせてください。
          押しつけは一切しません。
          次が施術60〜90分。寝ていてもOKです。
          施術後はホームケアの説明をして終わり。
          無理に何かを売ったりしません。」

【カット3 / 5秒】CTA・笑顔
  フレーム: バストアップ・正面
  表情　: 温かく「いつでも来てください」という雰囲気
  セリフ:「気になった方は、プロフィールのリンクからどうぞ。」""",

        "editing_notes": _build_editing_notes(22, 3),

        "cta":     _CTA_DM,
        "caption": """\
初めての方へ。当日の流れを全部話します。

①カウンセリング（10〜15分）
気になる部分と表情グセ・姿勢の癖をお聞きします。
押しつけは一切しません。

②施術（60〜90分）
話しかけてもOK、寝ていてもOK。

③施術後のホームケア説明
必要なことだけお伝えします。無理に売りません。

「知らないから不安」がもったいないです🌿
まずは気軽に聞いてください。

ご予約・ご相談はプロフィールのリンクからどうぞ。

#小顔矯正初めて #フェイシャルエステ #札幌エステ #小顔矯正 #たるみ改善 #COREHARI""",

        "threads_text": """\
初めての小顔矯正、当日の流れを全部話します。

①カウンセリング（10〜15分）：表情グセや姿勢の癖も聞かせてもらう。押しつけなし。
②施術（60〜90分）：寝てていい。話しかけてもいい。
③施術後：必要なホームケアだけ伝える。無理に売らない。

「知らないから不安」がもったいないです。
気軽に聞いてください。""",

        "cut_count": 3, "total_sec": 22,
    },
]


# ────────────────────────────────────────────────────────────────────────────
# ⑨ 水平思考（Lateral Thinking） — テーマ別に3案 + 推奨案
# ────────────────────────────────────────────────────────────────────────────

_LATERAL_THINKING = {
    "小顔矯正が何にアプローチするか": {
        "proposals": [
            ("逆説的切り口",
             "「1回で変わります」と言わない動画",
             "「1回で変わる」をウリにする競合が多い中、"
             "「正直に言うと1回では形は変わりません」と先に言う。"
             "誠実さそのものがフックになり、信頼で差別化できます。"),
            ("他業界応用",
             "「整体の問診票」を顔施術に応用する動画",
             "整体院は最初に姿勢・生活習慣を問診票で確認する。"
             "同じ発想で「顔の問診票（噛み癖・寝る向き・スマホ習慣）」を紹介し、"
             "視聴者が自分で原因に気づく構成にする。"),
            ("え？視点",
             "「施術で一番大事な60種類の筋肉、あなたは何個知ってますか？」",
             "「顔の筋肉は60種類」という事実を、クイズ形式で問いかける。"
             "視聴者が「え、そんなにあるの？」と止まる。"
             "知識格差がそのままフックになる構成です。"),
        ],
        "rec": 2,
        "rec_reason":
            "「え？視点」案を推奨。CORE HARIの専門性を具体的な数字で示せる上、"
            "クイズ形式でコメント（「知らなかった！」）が自然に集まりやすい構成です。",
    },
    "老け見えの正体は顔筋の衰え": {
        "proposals": [
            ("逆説的切り口",
             "「スキンケアをやめた方が顔が若返る場合がある」",
             "過剰な保湿・クレンジングがリンパを詰まらせ、むくみを悪化させるケースを切り口に。"
             "「やらない方がいいケア」は保存率が高いテーマです。"),
            ("他業界応用",
             "「スポーツコーチが直す『フォームの癖』を、顔筋で再現する」",
             "アスリートがフォームの癖を直すように、顔にも「使い方の癖」がある。"
             "スポーツ経験のある視聴者に刺さる比喩で、専門性の伝わり方が変わります。"),
            ("え？視点",
             "「老けた原因は鏡の見すぎかもしれない」",
             "鏡を見るたびに眉間にシワを寄せるクセが強化される逆説。"
             "「鏡を見るの、少し減らしてみてください」という締めが意外性を生みます。"),
        ],
        "rec": 1,
        "rec_reason":
            "「他業界応用（スポーツコーチ比喩）」を推奨。"
            "「顔筋 = 体の筋肉と同じ」というCORE HARIのコア哲学を、"
            "スポーツという身近な比喩で瞬時に理解させられます。ブランドらしさとも完全一致。",
    },
    "骨格より先にむくみとリンパを整える": {
        "proposals": [
            ("逆説的切り口",
             "「骨格矯正したいなら、最初に骨に触ってはいけない」",
             "骨格より先にリンパ・むくみを整えることをCORE HARIの原則として言い切る。"
             "「え、順番があるの？」という意外性がフックになります。"),
            ("他業界応用",
             "「家の浸水を止めてから壁紙を直す。顔も同じです」",
             "工務店は浸水を放置して内装を直さない。顔のむくみ＝浸水、骨格＝内装。"
             "この比喩は「なぜ骨格より先にリンパなのか」を直感的に伝えられます。"),
            ("え？視点",
             "「顔が大きい人は、実は顔が小さい」",
             "骨格は平均的でも、むくみで大きく見えているケースが多いという事実。"
             "「え？」という停止力がある上、「だからむくみから整えるんです」への流れが自然です。"),
        ],
        "rec": 2,
        "rec_reason":
            "「え？視点」案を推奨。「顔が大きい人は実は顔が小さい」は、"
            "悩みを持つ視聴者が一瞬「え？」と止まる最大の停止力を持ちます。"
            "その後の解説への流れも自然で、保存率が上がりやすい構成です。",
    },
    "顔を老けさせている3つのグセ": {
        "proposals": [
            ("逆説的切り口",
             "「表情豊かな人ほど老けやすい」",
             "豊かな表情は美しいが、筋肉の偏った使い方がシワを深くする逆説。"
             "「でも表情は消さなくていい。使い方を整えればいい」という結論が救いになります。"),
            ("他業界応用",
             "「ゴルフのグリップ矯正を、顔グセに応用する」",
             "ゴルフのプロコーチは最初にグリップを直す。顔グセも同じで「正しい使い方」に直すだけ。"
             "「顔の動き方に正解がある」という発想が新鮮に映ります。"),
            ("え？視点",
             "「笑顔が老け見えの原因になっていませんか？」",
             "口角を上げるとき、目を細めるとき、どこに力を入れているか。"
             "「正しく笑えると、笑顔で若返る」という逆説がフックになります。"),
        ],
        "rec": 2,
        "rec_reason":
            "「え？視点（笑顔が老け見えの原因）」を推奨。"
            "視聴者の思い込みを正面から壊すフックで、コメント（「え、笑っちゃダメ？」）が集まりやすい。"
            "「正しく笑えば若返る」という結論がポジティブで、CORE HARIのブランドトーンとも合います。",
    },
    "施術回数ごとの正直なタイムライン": {
        "proposals": [
            ("逆説的切り口",
             "「変わりたいなら、変わることを期待しないほうがいい」",
             "焦りが「効果が出たか」を過剰にチェックさせ、グセが抜けにくくする。"
             "「期待を手放すと、変化に気づける」という逆説が誠実さと差別化になります。"),
            ("他業界応用",
             "「フィットネスジムの体重グラフを、顔の変化に応用する」",
             "体重は週単位では変動するが、月単位では着実に変わる。顔の変化も同じ。"
             "「変化を信じるための見方」を教えるコンテンツは保存率が上がります。"),
            ("え？視点",
             "「1回で変わったと言っている人に聞いてはいけない」",
             "1回で劇的に変わった人はむくみが主因。骨格・筋肉系は時間がかかる。"
             "「あなたに合ったペースがある」という正直な説明が、かえって信頼を生みます。"),
        ],
        "rec": 2,
        "rec_reason":
            "「え？視点（1回で変わった人に聞くな）」を推奨。"
            "SNSの「〇回で劇変！」という誇大表現を、正直さで逆手に取るフックです。"
            "「正直に言う」というCORE HARIのブランド軸と完全一致し、信頼で差別化できます。",
    },
    "顔の左右差はクセから来る": {
        "proposals": [
            ("逆説的切り口",
             "「左右対称を目指すと、逆に左右差が強くなる」",
             "鏡を見るたびに左右を比べることで、片側への意識が偏りクセが強化される逆説。"
             "「鏡より感覚を信じて」という締めがCORE HARIらしい誠実さになります。"),
            ("他業界応用",
             "「デスクチェアの高さ調整（エルゴノミクス）で顔の左右差を直す発想」",
             "オフィスワーカーが姿勢の非対称性で体を壊すのと同じ原理。"
             "「椅子の高さ・モニターの位置を直すと顔も整う」という切り口が意外性を生みます。"),
            ("え？視点",
             "「左右が揃っている顔が最も美しいわけではない」",
             "完全対称な顔は実は人工的に見える。「自然な非対称性を活かしながら整える」がゴール。"
             "「対称にしたい」という視聴者の思い込みを優しく外す構成です。"),
        ],
        "rec": 0,
        "rec_reason":
            "「逆説的切り口（左右を比べると逆に悪化する）」を推奨。"
            "「鏡で見すぎている」行動を指摘することで自己関連性が高まります。"
            "CORE HARIの「押しつけない誠実さ」という哲学と完全に一致した構成です。",
    },
    "初めての小顔矯正・当日の流れ": {
        "proposals": [
            ("逆説的切り口",
             "「初めての施術は、変わらなくていい」",
             "「変化を期待する前に、施術者の手を感じることに集中してほしい」という哲学を前に出す。"
             "過大期待をしないことを先に言うことで、かえって信頼が生まれます。"),
            ("他業界応用",
             "「高級レストランがシェフのおまかせコースを最初に勧める理由を、施術に応用する」",
             "初めての顧客に「まず体験してほしい」という姿勢は、一流レストランと同じ。"
             "「CORE HARIのファーストコースメニュー」という表現で付加価値が伝わります。"),
            ("え？視点",
             "「来る前にキャンセルしてもいい、ということをお伝えしています」",
             "「施術を受ける・受けない」の選択権をお客様に渡すことを、最初から伝えている。"
             "「押しつけません」より強いメッセージで、CORE HARIの哲学が伝わります。"),
        ],
        "rec": 2,
        "rec_reason":
            "「え？視点（来る前にキャンセルしてもいい）」を推奨。"
            "「お客様に選択権を渡す」というCORE HARIの非営業スタンスを最も強く表現できます。"
            "「こんなサロン初めて」というコメントが集まりやすく、フォロー・問い合わせに直結します。",
    },
}

_LATERAL_FALLBACK = {
    "proposals": [
        ("逆説的切り口",
         "「やらない方がいいこと」を最初に伝える",
         "何かを『しなければ』という発想より、まず『やめること』を教える動画は保存率が上がります。"
         "CORE HARIのテーマをこの切り口で考え直してみてください。"),
        ("他業界応用",
         "「スポーツコーチの原則」をこのテーマに応用する",
         "スポーツコーチは『正しいフォームを直す』より先に『悪いクセを除く』ことを優先します。"
         "顔・身体のテーマは多くの場合この発想で再構成できます。"),
        ("え？視点",
         "「常識の逆を言ったら、どうなるか？」を考える",
         "このテーマで一般的に信じられていることは何か？"
         "それを丁寧に否定または更新できる事実がCORE HARIの知識の中にあるはずです。"),
    ],
    "rec": 0,
    "rec_reason":
        "上記3案はいずれもCORE HARIのテーマに応用可能な汎用フレームです。"
        "最もブランドらしい誠実さ・専門性を表現できる案を選んでください。",
}


# ────────────────────────────────────────────────────────────────────────────
# ⑩ Creator Review — 10項目自己採点（ルールベース、OpenAIコストゼロ）
# ────────────────────────────────────────────────────────────────────────────

def _compute_creator_review(record: dict) -> dict:
    hook        = record.get("hook", "")
    script      = record.get("script_full", "")
    cta         = record.get("cta", "")
    shot_seq    = record.get("shot_sequence", "")
    brand_score = int(record.get("brand_score", "80") or 80)
    cuts        = int(record.get("shooting_cuts", "6") or 6)
    combined    = f"{hook} {script} {cta}"

    # 1. フック: 疑問形・共感語があるか
    hook_q = any(c in hook for c in ["？", "ですか", "ませんか", "でしょうか"])
    hook_e = any(w in hook for w in ["気がする", "かもしれ", "悩み", "不安", "方へ"])
    s_hook = 90 if hook_q else (85 if hook_e else 72)

    # 2. 専門性: CORE HARI固有ワード（咬筋・舌の位置・表情グセは+6点）
    expert_words_base = ["筋肉", "リンパ", "骨格", "顔筋", "むくみ", "フェイスライン",
                         "ほうれい線", "施術", "コリ", "たるみ"]
    expert_words_core = ["咬筋", "舌の位置", "表情グセ", "咬筋優位", "表情筋", "姿勢"]
    s_expert = min(95, 65
                   + sum(3 for w in expert_words_base if w in combined)
                   + sum(6 for w in expert_words_core if w in combined))

    # 3. 独自性: 逆説・正直告白があるか
    unique_markers = ["正直に", "本当は", "実は", "と思っていませんか", "仕方ない", "無理", "変わりません"]
    s_unique = min(92, 72 + sum(5 for w in unique_markers if w in combined))

    # 4. 保存されやすさ: CTA種別
    s_save = 92 if "保存" in cta else (80 if "フォロー" in cta else 75)

    # 5. 共感: フックに共感ワード
    empathy_words = ["気になる", "悩み", "不安", "感じ", "気がする", "辛い", "多い"]
    s_empathy = min(92, 72 + sum(5 for w in empathy_words if w in hook))

    # 6. 信頼性: 正直表明・個人差・否定しない
    trust_markers = ["正直", "個人差", "変わりません", "あきらめない", "言えます",
                     "必ず言え", "一切しません"]
    s_trust = min(95, 72 + sum(5 for w in trust_markers if w in combined))

    # 7. ブランドらしさ: brand_score から直接算出
    s_brand = brand_score

    # 8. 撮影しやすさ: カット数が少ないほど楽（6カット以下 = 高得点）
    s_shoot = 92 if cuts <= 5 else (86 if cuts == 6 else 75)

    # 9. 編集しやすさ: editing_notesが設定されているか
    has_editing = bool(record.get("editing_notes", "").strip())
    s_edit = 90 if has_editing else 70

    # 10. CTA: 動詞が明確か（「保存して」「フォローすると」「プロフィールのリンクから」）
    cta_verbs = ["保存して", "フォローすると", "プロフィールのリンク", "リンクから"]
    s_cta = min(95, 72 + sum(6 for v in cta_verbs if v in cta))

    scores = {
        "フック":       s_hook,
        "専門性":       s_expert,
        "独自性":       s_unique,
        "保存されやすさ": s_save,
        "共感":         s_empathy,
        "信頼性":       s_trust,
        "ブランドらしさ": s_brand,
        "撮影しやすさ":  s_shoot,
        "編集しやすさ":  s_edit,
        "CTA":          s_cta,
    }

    avg = round(sum(scores.values()) / len(scores), 1)

    # 改善点TOP3（スコアが低い順）
    sorted_items = sorted(scores.items(), key=lambda x: x[1])
    top3_improvements = []
    advice_map = {
        "フック":       "冒頭3秒に疑問形（「〜って知ってますか？」）または強い共感語を入れてください",
        "専門性":       "顔筋・リンパ・骨格など、CORE HARI固有の専門ワードをもう1〜2個追加してください",
        "独自性":       "「正直に言うと…」「よく誤解されますが…」など、常識を更新する一文を入れてください",
        "保存されやすさ": "CTAを「保存して、気になったときに読み返してください」に変更すると保存率が上がります",
        "共感":         "フック（0〜3秒）にターゲットの悩みワード（たるみ・むくみ・左右差）を具体的に入れてください",
        "信頼性":       "「個人差はあります」「正直に言います」など、誠実な補足を1〜2文追加してください",
        "ブランドらしさ": "NGワード（痛い・怖い・劇的・激変）がないか再確認してください",
        "撮影しやすさ":  "カット数を5〜6に絞ると撮影・編集の負担が下がります",
        "編集しやすさ":  "編集指示（尺・字幕・BGM・色味・カット割り）を明記してください",
        "CTA":          "CTAに動詞を明確に（「保存して」「フォローすると」「リンクから」）入れてください",
    }
    for item, sc in sorted_items[:3]:
        top3_improvements.append(f"{item}（{sc}点）: {advice_map.get(item, '内容を強化してください')}")

    # 伸びない可能性
    risks = []
    if s_hook < 80:
        risks.append("フックが弱く最初の3秒で離脱される可能性があります")
    if s_unique < 80:
        risks.append("類似投稿が多く埋もれる可能性があります（独自性の強化を）")
    if s_save < 80:
        risks.append("保存・フォローにつながりにくく拡散力が落ちる可能性があります")
    if not risks:
        risks.append("大きなリスクは見当たりません。改善してさらに伸ばしましょう")

    predicted_after = min(99, round(avg + 6))

    return {
        "scores":            scores,
        "average":           avg,
        "top3_improvements": top3_improvements,
        "risk":              "・".join(risks),
        "predicted_after":   predicted_after,
    }


# ────────────────────────────────────────────────────────────────────────────
# 「他サロンでも言えるか？」ゲート
# ────────────────────────────────────────────────────────────────────────────

# CORE HARIだけが持つ「その人しか言えない視点」のマーカー。
# これが1件でも検出されれば → 他サロンには言えない（NOを返す）。
_CORE_HARI_UNIQUE_MARKERS = {
    "咬筋優位":           "咬筋優位という専門的切り口（片側噛み・食いしばりとフェイスラインの関係）",
    "咬筋の左右差":       "咬筋の左右差という観察視点",
    "咬筋が":             "咬筋の変化・働きへの具体的言及",
    "舌の位置":           "舌の位置とフェイスライン・たるみの関係",
    "舌が下":             "舌低位がもたらす顔への影響",
    "上あごにつける":     "正しい舌の位置（上あご）の具体的指示",
    "表情グセ":           "表情グセという独自の概念・切り口",
    "表情筋の使い方":     "表情筋の「使い方の偏り」という切り口（単なる衰えではない）",
    "約60種類":           "顔の筋肉が約60種類という具体的事実",
    "正直に言います":     "CORE HARIの「正直な告白」スタンス",
    "押しつけは一切しません": "非営業スタンスの明言（CORE HARIの哲学）",
    "あきらめないでください": "お客様への個人的な励まし（CORE HARIのトーン）",
    "変わりません。正直": "変わらないことを先に言う誠実さ（CORE HARIの逆張り）",
    "骨格の大きさは変わりません": "骨格は変わらないという正直な告白",
    "カウンセリング10〜15": "カウンセリング所要時間の具体的開示",
    "施術60〜90":         "施術時間の具体的開示",
    "3回目前後":          "効果が出る回数の具体的タイムライン",
    "6回以上で":          "変化定着の目安という具体的指標",
    "それだけは言えます": "言い切れることだけ言うという誠実さ",
    "無理に何かを売":     "売らないスタンスの明言",
}

# 汎用フレーズ（これだけで構成されていると他サロンでも言える）
_GENERIC_BEAUTY_PHRASES = [
    "むくみ", "リンパ", "たるみ", "ほうれい線", "フェイスライン",
    "小顔", "スキンケア", "老け見え", "保湿", "引き上げ", "リフトアップ",
    "顔のコリ", "血行", "代謝",
]


def _check_other_salon_could_say(record: dict) -> dict:
    """
    「この投稿は他サロンでも言えるか？」を自己判定する。

    CORE HARI固有マーカーが1件でも検出されれば → 他サロンには言えない（unique=True）。
    0件なら → 他サロンでも言える（unique=False）→ CEO Challenge は自動 NO。

    戻り値:
      {
        "is_unique": bool,           # True = 他サロンには言えない（合格）
        "verdict": str,              # "NO（他サロンには言えない）" or "YES（他サロンでも言える）"
        "found_unique": list[str],   # 検出されたユニーク要素の説明
        "found_generic": list[str],  # 検出された汎用フレーズ
        "missing_hint": str,         # unique=Falseのとき、追加すべき要素のヒント
      }
    """
    combined = " ".join([
        record.get("hook", ""),
        record.get("script_full", ""),
        record.get("caption", ""),
    ])

    found_unique  = [desc for marker, desc in _CORE_HARI_UNIQUE_MARKERS.items()
                     if marker in combined]
    found_generic = [w for w in _GENERIC_BEAUTY_PHRASES if w in combined]

    is_unique = len(found_unique) > 0

    if is_unique:
        verdict = "NO（他サロンには言えない）✅"
        missing_hint = ""
    else:
        verdict = "YES（他サロンでも言える）❌ — 再生成が必要"
        # どのユニーク要素を追加すると固有性が出るかを提案
        suggestions = [
            "「咬筋優位」「咬筋の左右差」など、筋肉名を具体的に入れる",
            "「舌の位置」「舌を上あごにつける」など、日常のクセへの具体的指示を入れる",
            "「表情グセ」という言葉を使い、どんなクセが問題かを具体的に示す",
            "「正直に言います」「変わりません」など、CORE HARIの誠実スタンスを前面に出す",
            "「押しつけは一切しません」「無理に何かを売りません」など、非営業姿勢を明言する",
            "回数・時間・種類数など、具体的な数字を1つ以上入れる",
        ]
        missing_hint = "\n".join(f"  ▶ {s}" for s in suggestions)

    return {
        "is_unique":    is_unique,
        "verdict":      verdict,
        "found_unique": found_unique,
        "found_generic": found_generic,
        "missing_hint": missing_hint,
    }


# ────────────────────────────────────────────────────────────────────────────
# ⑪ CEO Challenge — 「森このみ本人が投稿したいか？」＋「他サロンでも言えるか？」
# ────────────────────────────────────────────────────────────────────────────

def _generate_ceo_challenge(record: dict, review: dict) -> dict:
    avg         = review["average"]
    brand_score = int(record.get("brand_score", "80") or 80)
    hook        = record.get("hook", "")
    script      = record.get("script_full", "")
    combined    = f"{hook} {script}"

    # ── Gate 1: 「他サロンでも言えるか？」 ──────────────────────────
    salon_check = _check_other_salon_could_say(record)

    # ── Gate 2: NGワード ────────────────────────────────────────────
    ng_hits = [w for w in _BRAND.ng_words if w in combined]

    # ── Gate 3: NG概念 ──────────────────────────────────────────────
    ng_concept_markers = ["絶対に変わる", "必ず", "〇〇日で", "危険", "失敗しない", "完璧"]
    concept_hits = [m for m in ng_concept_markers if m in combined]

    # ── Gate 4: Creator Review 点数 ─────────────────────────────────
    score_fail = avg < 78 or brand_score < 78

    # ── 総合判定 ─────────────────────────────────────────────────────
    is_no = (not salon_check["is_unique"]) or bool(ng_hits) or bool(concept_hits) or score_fail

    if is_no:
        reasons_no = []
        if not salon_check["is_unique"]:
            reasons_no.append("他サロンでも言える内容になっている（固有視点ゼロ）")
        if ng_hits:
            reasons_no.append(f"NGワード検出: {', '.join(ng_hits)}")
        if concept_hits:
            reasons_no.append(f"NG表現検出: {', '.join(concept_hits)}")
        if avg < 78:
            reasons_no.append(f"Creator Review平均点が{avg}点（目標78点以上）")
        if brand_score < 78:
            reasons_no.append(f"Brand Score {brand_score}点（目標78点以上）")

        improve_hints = []
        if not salon_check["is_unique"]:
            improve_hints.append("【固有視点を追加する】\n" + salon_check["missing_hint"])
        if ng_hits:
            improve_hints.append(
                "【NGワードを言い換える】\n"
                + "\n".join(f"  「{w}」→ より柔らかい表現に" for w in ng_hits)
            )
        if score_fail:
            w_item, w_score = min(review["scores"].items(), key=lambda x: x[1])
            improve_hints.append(f"【最低スコア項目を改善】\n  「{w_item}」（{w_score}点）を優先してください")

        return {
            "verdict":      "NO — 投稿しないでください",
            "reason":       "・".join(reasons_no),
            "improve":      "\n\n".join(improve_hints),
            "salon_check":  salon_check,
        }

    # ── YES ──────────────────────────────────────────────────────────
    strength = []
    if salon_check["found_unique"]:
        strength.append(f"固有視点あり: {salon_check['found_unique'][0]}")
    if review["scores"].get("信頼性", 0) >= 88:
        strength.append("「正直に言う」スタンスが一貫している")
    if review["scores"].get("専門性", 0) >= 85:
        strength.append("CORE HARI固有の専門知識が使われている")
    if review["scores"].get("フック", 0) >= 85:
        strength.append("最初の3秒で視聴者が止まれる")
    if not strength:
        strength.append("ブランドラインを守りながら価値ある情報を届けられている")

    return {
        "verdict":     "YES — 投稿してください",
        "reason":      "・".join(strength),
        "improve":     "",
        "salon_check": salon_check,
    }


# ────────────────────────────────────────────────────────────────────────────
# レコード組み立て
# ────────────────────────────────────────────────────────────────────────────

def _assemble(today: str, source_type: str, source_url: str,
              tmpl: dict, why_today: str, mission: str = "") -> dict:
    hook  = tmpl.get("hook", "")
    cta   = tmpl.get("cta", _CTA_SAVE)
    theme = tmpl.get("theme", "")
    score, notes = _brand_score(hook, cta, theme)
    cut_count = tmpl.get("cut_count", 6)
    total_sec = tmpl.get("total_sec", 45)

    record = {
        "date":          today,
        "source_type":   source_type,
        "source_url":    source_url,
        "today_mission": mission or tmpl.get("mission", "保存を狙う"),
        "theme":         theme,
        "video_title":   tmpl.get("video_title", theme),
        "why_today":     why_today,
        "target":        _TARGET,
        "hook":          hook,
        # script_15_30s をフックテロップとして転用
        "script_15_30s": tmpl.get("hook_text", ""),
        "script_full":   tmpl.get("script_full", ""),
        "shot_sequence": tmpl.get("shot_sequence", ""),
        "shooting_location": "白い壁またはベージュ背景の前 / 自然光が入る明るい場所",
        "shooting_cuts": str(cut_count),
        "b_roll":        "施術台・手元アップ・リンパラインをなぞる動き・笑顔のアウトロ",
        "editing_notes": tmpl.get("editing_notes", _build_editing_notes(cut_count, total_sec)),
        "cta":           cta,
        "caption":       tmpl.get("caption", ""),
        "threads_text":  tmpl.get("threads_text", ""),
        "brand_score":   str(score),
        "brand_notes":   notes,
        "feedback_url_placeholder": "（投稿後にURLを記入）",
    }

    # ⑨⑩⑪ をレコードに埋め込む（"_" プレフィックスで sheets_writer には書かれない）
    lateral_data = _LATERAL_THINKING.get(theme, _LATERAL_FALLBACK)
    record["_lateral"]       = lateral_data
    review = _compute_creator_review(record)
    record["_creator_review"] = review
    record["_ceo_challenge"]  = _generate_ceo_challenge(record, review)

    return record


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

    pick   = picks[0]
    theme  = (pick.get("タイトル") or pick.get("投稿カテゴリ") or "今日の投稿").strip()
    body   = (pick.get("本文") or "").strip()
    caption = (pick.get("キャプション") or "").strip()
    cta    = (pick.get("CTA") or _CTA_SAVE).strip()
    hook   = body.split("。")[0].split("\n")[0][:50].strip() if body else f"「{theme}」について話します"

    body_lines = [l.strip() for l in body.replace("→", "\n").splitlines() if l.strip()]
    shot_parts = ["【カット1 / 2秒】静止・テキストフック用（セリフなし）"]
    shot_parts.append(f'【カット2 / 8秒】カメラ目線\n  セリフ:「{hook}」')
    for i, line in enumerate(body_lines[1:4], start=3):
        shot_parts.append(f'【カット{i} / 10秒】カメラ目線\n  セリフ:「{line}」')
    shot_parts.append(
        f'【カット{len(shot_parts)+1} / 5秒】笑顔・カメラ目線\n  セリフ:「{cta}」'
    )

    tmpl = {
        "theme":       theme,
        "video_title": theme[:35] if len(theme) <= 35 else hook[:35],
        "mission":     "問い合わせを狙う" if "予約" in cta else "保存を狙う",
        "hook":        hook,
        "hook_text":   f"{theme}",
        "shot_sequence": "\n\n".join(shot_parts),
        "script_full": body,
        "cta":         cta,
        "caption":     caption or f"{theme}について話しました。保存して読み返してください。",
        "threads_text": f"{hook}\n\n{body[:120]}",
        "editing_notes": _build_editing_notes(len(shot_parts) * 9, len(shot_parts)),
        "cut_count":   len(shot_parts),
        "total_sec":   len(shot_parts) * 9,
    }
    why = (
        "Instagram分析 × AI分析（daily_content_picks）から選定されました。"
        "North Star IndexとResearch Candidate Scoreで今日最も価値が高いと判定された投稿案です。"
    )
    print("  Creator Studio: Priority1（daily_content_picks）を使用")
    return _assemble(today, "daily_content_picks", pick.get("投稿URL", ""), tmpl, why)


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
        [r["values"] for r in rows
         if r["values"].get("status") in ("VALIDATED", "ACTIVE")],
        key=lambda v: float(v.get("confidence") or 0), reverse=True,
    )
    if not validated:
        return None

    def pick(dim):
        return next((v for v in validated if v.get("dimension") == dim), None)

    hook_u   = pick("Hook")
    if not hook_u:
        return None
    struct_u = pick("Structure")
    psych_u  = pick("Psychology")
    cta_u    = pick("CTA")

    hook_text  = (hook_u.get("description") or hook_u.get("pattern_name") or "")[:50]
    struct_text = (struct_u or {}).get("pattern_name") or "問題提示→解決策→CTA"
    cta_text   = (cta_u or {}).get("pattern_name") or _CTA_SAVE

    shot_seq = (
        "【カット1 / 2秒】静止・テキストフック用（セリフなし）\n\n"
        f"【カット2 / 10秒】カメラ目線でフック\n  セリフ:「{hook_text}」\n\n"
        f"【カット3 / 15秒】本編（構成: {struct_text}）\n  内容はKBから生成予定\n\n"
        f"【カット4 / 5秒】笑顔・CTA\n  セリフ:「{cta_text}」"
    )
    script = f"{hook_text}\n\n（構成: {struct_text}に沿って話す）\n\n{cta_text}"

    dims = [u.get("dimension") for u in [hook_u, struct_u, psych_u, cta_u] if u]
    confs = [float(u.get("confidence") or 0) for u in [hook_u, struct_u, psych_u, cta_u] if u]
    avg_conf = round(sum(confs) / len(confs), 2) if confs else 0
    why = (
        f"Learning Engine が蓄積したVALIDATED KnowledgeUnits（{', '.join(dims)} / "
        f"平均confidence: {avg_conf}）から構成しました。実績データに裏付けられたパターンです。"
    )
    tmpl = {
        "theme":       hook_u.get("pattern_name", "今日の投稿"),
        "video_title": hook_text[:35],
        "mission":     "保存を狙う",
        "hook":        hook_text,
        "hook_text":   hook_text,
        "shot_sequence": shot_seq,
        "script_full": script,
        "cta":         cta_text,
        "caption":     f"{hook_text}\n\nCORE HARI FACEが詳しく解説します🌿\n{_CTA_SAVE}",
        "threads_text": f"{hook_text}\n\n（KBから生成予定）",
        "editing_notes": _build_editing_notes(32, 4),
        "cut_count": 4, "total_sec": 32,
    }
    print(f"  Creator Studio: Priority2（VALIDATED KnowledgeUnits {len(dims)}次元）を使用")
    return _assemble(today, "knowledge_units_validated", "", tmpl, why)


# ────────────────────────────────────────────────────────────────────────────
# Priority3: 過去30日の高スコア Creator Studio
# ────────────────────────────────────────────────────────────────────────────

def _try_priority3(today: str) -> Optional[dict]:
    """
    Learning Engine進化型。
    過去ブリーフの「良かった要素」を抽出し、異なるテーマ・構成・CTAで新しいブリーフを生成。

    絶対条件:
      - 昨日と同じタイトル禁止
      - 昨日と同じHook禁止
      - 昨日と同じ構成禁止
      - 昨日と同じCTA禁止
    """
    try:
        records = sheets_writer.get_recent_creator_studio_records(days=30)
    except Exception as e:
        print(f"  ⚠️ P3 creator_studio_daily読み込み失敗: {e}")
        return None

    candidates = [r for r in records
                  if r.get("date") != today
                  and r.get("source_type") not in ("brand_template",)]
    if not candidates:
        return None

    # 過去ブリーフから「良かった要素」を抽出（学習）
    best        = candidates[0]
    past_theme  = best.get("theme", "")
    past_mission = best.get("today_mission", "保存を狙う")
    past_date   = best.get("date", "過去")
    past_score  = best.get("brand_score", "?")
    past_cta    = best.get("cta", "")

    # 昨日と違うテーマを持つテンプレートを選ぶ（同テーマ禁止）
    diff_theme_tmpls = [t for t in _DNA_TEMPLATES if t.get("theme") != past_theme]
    pool = diff_theme_tmpls if diff_theme_tmpls else _DNA_TEMPLATES

    # 昨日と違うミッション（CTAタイプ）を優先
    diff_mission_tmpls = [t for t in pool if t.get("mission") != past_mission]
    candidate_pool = diff_mission_tmpls if diff_mission_tmpls else pool

    # 曜日 + 1 オフセットでローテーション（昨日使った位置をずらす）
    dow  = datetime.date.today().weekday()
    tmpl = candidate_pool[(dow + 1) % len(candidate_pool)]

    why = (
        f"Learning Engine 進化版:\n"
        f"前回（{past_date}）: テーマ「{past_theme}」 / ミッション「{past_mission}」"
        f" / Brand Score {past_score}\n"
        f"今日は前回と異なるテーマ・構成・CTAで新しいブリーフを生成しました。\n"
        f"Creator Studioは毎日新しい作品を作ること。昨日より少しでも良いものを作ること。"
    )
    print(
        f"  Creator Studio: Priority3 Learning Engine進化版"
        f"（前回「{past_theme}」→ 今回「{tmpl['theme']}」）を使用"
    )
    return _assemble(today, "evolved_from_past", "", tmpl, why)


# ────────────────────────────────────────────────────────────────────────────
# Priority4: Brand DNA Engine
# ────────────────────────────────────────────────────────────────────────────

def _priority4(today: str) -> dict:
    dow  = datetime.date.today().weekday()  # 0=月〜6=日
    tmpl = _DNA_TEMPLATES[dow % len(_DNA_TEMPLATES)]
    why  = (
        f"Brand DNA Engine（曜日ローテーション: 本日は{['月','火','水','木','金','土','日'][dow]}曜日）を使用。"
        "「構造はInstagram分析から、内容はCORE HARIの専門性から」の原則で組み立てました。"
        f"構造パターン: {tmpl.get('mission', '')}。"
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
# ターミナル表示 — 撮影指示書フォーマット ①〜⑧
# ────────────────────────────────────────────────────────────────────────────

def print_creator_studio_summary(record: dict) -> None:
    W = 64
    THICK = "━" * W
    THIN  = "─" * W

    _SOURCE_LABELS = {
        "daily_content_picks":       "Instagram分析 × AI",
        "knowledge_units_validated": "Learning Engine（VALIDATEDパターン）",
        "evolved_from_past":          "Learning Engine 進化版",
        "brand_dna":                 "Brand DNA",
    }
    source_label = _SOURCE_LABELS.get(
        record.get("source_type", ""), record.get("source_type", "")
    )

    def sec(num: str, title: str) -> None:
        print(f"\n{num} {title}")
        print(THIN)

    def body(text: str, indent: int = 2) -> None:
        pad = " " * indent
        for line in (text or "").splitlines():
            print(f"{pad}{line}")

    # ── ヘッダー ──────────────────────────────────────────────────────
    print(f"\n{THICK}")
    print(f"  今日の撮影指示書  [{source_label}]")
    print(f"  目的: {record.get('today_mission', '')}")
    print(THICK)

    # ── ① 今日の投稿タイトル ─────────────────────────────────────────
    sec("①", "今日の投稿タイトル")
    print(f"\n    「{record.get('video_title', '')}」\n")

    # ── ② このテーマを選んだ理由 ─────────────────────────────────────
    sec("②", "このテーマを選んだ理由")
    body(record.get("why_today", ""))

    # ── ③ Hook（0〜3秒）─────────────────────────────────────────────
    sec("③", "Hook（0〜3秒）")
    hook_text = record.get("script_15_30s", "")  # テロップ
    hook_say  = record.get("hook", "")            # 話すセリフ
    if hook_text:
        print("\n  【テロップ（画面に出すテキスト）】")
        for line in hook_text.splitlines():
            print(f"    {line}")
    if hook_say:
        print("\n  【話すセリフ】")
        for line in hook_say.splitlines():
            print(f"    「{line}」" if not line.startswith("「") else f"    {line}")

    # ── ④ 台本（3〜30秒）────────────────────────────────────────────
    sec("④", "台本（3〜30秒）— そのまま読んでください")
    print()
    body(record.get("script_full", ""), indent=4)

    # ── ⑤ 撮影指示 ──────────────────────────────────────────────────
    sec("⑤", "撮影指示（カット別）")
    print()
    body(record.get("shot_sequence", ""), indent=2)

    # ── ⑥ 編集指示 ──────────────────────────────────────────────────
    sec("⑥", "編集指示")
    print()
    body(record.get("editing_notes", ""), indent=2)

    # ── ⑦ キャプション ──────────────────────────────────────────────
    sec("⑦", "キャプション（コピペ用）")
    print()
    body(record.get("caption", ""), indent=2)

    # ── ⑧ Threads ───────────────────────────────────────────────────
    sec("⑧", "Threads（コピペ用）")
    print()
    body(record.get("threads_text", ""), indent=2)

    # ── Brand Check ─────────────────────────────────────────────────
    print(f"\n{THIN}")
    score = record.get("brand_score", "")
    print(f"  Brand Check: {score}/100")
    body(record.get("brand_notes", ""), indent=2)

    # ── ⑨ 水平思考（Lateral Thinking）────────────────────────────────
    lateral = record.get("_lateral", {})
    if lateral:
        sec("⑨", "水平思考（Lateral Thinking）— もっと意外な切り口はないか？")
        proposals = lateral.get("proposals", [])
        for i, p in enumerate(proposals):
            angle_type, title, pitch = p[0], p[1], p[2]
            prefix = "★ 推奨 " if i == lateral.get("rec", -1) else "  案 "
            print(f"\n{prefix}{i+1}【{angle_type}】")
            print(f"    タイトル案: 「{title}」")
            print(f"    説明: {pitch}")
        rec_reason = lateral.get("rec_reason", "")
        if rec_reason:
            print(f"\n  【推奨理由】")
            body(rec_reason, indent=4)

    # ── ⑩ Creator Review（自己採点）────────────────────────────────
    review = record.get("_creator_review", {})
    if review:
        sec("⑩", "Creator Review — 10項目自己採点")
        scores = review.get("scores", {})
        avg = review.get("average", 0)
        print()
        items_order = [
            "フック", "専門性", "独自性", "保存されやすさ",
            "共感", "信頼性", "ブランドらしさ", "撮影しやすさ", "編集しやすさ", "CTA"
        ]
        for item in items_order:
            sc = scores.get(item, 0)
            bar = "■" * (sc // 10) + "□" * (10 - sc // 10)
            print(f"  {item:<10s}: {bar} {sc}点")
        print(f"\n  {'─'*40}")
        print(f"  総合平均: {avg}点 / 100点")
        print(f"\n  【改善点 TOP3】")
        for imp in review.get("top3_improvements", []):
            print(f"    ▶ {imp}")
        print(f"\n  【伸びない可能性】")
        body(review.get("risk", ""), indent=4)
        print(f"\n  【改善後の予測スコア】{review.get('predicted_after', '')}点")

    # ── ⑪ CEO Challenge ──────────────────────────────────────────
    ceo = record.get("_ceo_challenge", {})
    if ceo:
        sec("⑪", "CEO Challenge")
        salon_check = ceo.get("salon_check", {})

        # ── Gate 1: 他サロンでも言えるか？ ─────────────────────────
        print(f"\n  ┌─ GATE: この投稿は他サロンでも言えるか？")
        sc_verdict = salon_check.get("verdict", "")
        sc_icon    = "✅" if salon_check.get("is_unique") else "❌"
        print(f"  │  {sc_icon} {sc_verdict}")

        found_unique = salon_check.get("found_unique", [])
        if found_unique:
            print(f"  │  【固有視点の根拠】")
            for el in found_unique[:3]:
                print(f"  │    ・{el}")

        found_generic = salon_check.get("found_generic", [])
        if found_generic and not salon_check.get("is_unique"):
            print(f"  │  【汎用フレーズのみ検出（固有視点に変換が必要）】")
            print(f"  │    {' / '.join(found_generic)}")

        missing_hint = salon_check.get("missing_hint", "")
        if missing_hint:
            print(f"  │  【固有視点の追加案】")
            body(missing_hint, indent=4)

        print(f"  └─────────────────────────────────────────────────")

        # ── 総合判定 ────────────────────────────────────────────────
        verdict = ceo.get("verdict", "")
        icon    = "✅" if verdict.startswith("YES") else "❌"
        print(f"\n  {icon} {verdict}")

        reason = ceo.get("reason", "")
        if reason:
            print(f"\n  【根拠】")
            body(reason, indent=4)

        improve = ceo.get("improve", "")
        if improve:
            print(f"\n  ⚠️  改善してから投稿してください")
            print(f"  {'─'*50}")
            body(improve, indent=4)
            print(f"  {'─'*50}")

    print(f"\n{THICK}\n")
