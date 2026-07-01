"""
core_hari_kb_seed.py
CORE HARI Knowledge Base — 初期データ投入スクリプト

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【実行方法（Mac / VS Code）】

1. VS Code でこのプロジェクトフォルダを開く
   File → Open Folder → インスタ自動化フォルダ を選ぶ

2. ターミナルを開く
   メニュー: Terminal → New Terminal
   または: Ctrl + ` （バッククォート）

3. 以下のコマンドを1行ずつ実行する（コピペでOK）

   PYTHONPATH="$(pwd)" python3 core_hari_kb_seed.py

4. 完了メッセージが出たら Google Sheets を開いて確認する
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【実行後にあなたがやること】

Google Sheets に 2 つのシートが作られます：

  ① core_hari_kb        ← あなたが入力するシート（27件）
  ② core_hari_kb_samples ← 入力例シート（最初の10件の完成例）

core_hari_kb シートで、以下の3列だけを入力してください：

  D列: fact             ← 実際の知識・事実（1〜3文）
  E列: example_sentence ← どう話すか（任意。口語でOK）
  H列: verified         ← 書き終わったら「yes」と入力

他の列（A・B・C・F・G・I・J）はすべて自動入力済みです。触らないでください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【入力のコツ】

・fact は「専門家として断言できる事実」を1〜3文で。
  長くなるより、短く正確なほうが使いやすいです。

・example_sentence は「実際に口で言う言葉」をそのまま書く。
  「〜なんです」「〜ですよ」など話し言葉でOKです。任意項目なので
  後から追加してもOKです。

・verified は入力が終わったら「yes」と入力。
  「yes」になったエントリだけが Creator Studio で使われます。
  全部一度に入れなくてOK。1件でも yes があれば動き始めます。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import sys
import os
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheets_writer

TODAY = datetime.date.today().isoformat()

# ──────────────────────────────────────────────────────────────────────────────
# 27件のKnowledgeトピック定義
# fact / example_sentence は空欄（オーナーが記入する）
# notes 列に「何を書けばいいか」のヒントを入れる
# ──────────────────────────────────────────────────────────────────────────────

ENTRIES = [

    # ─── MECHANISM（仕組み）6件 ────────────────────────────────────────────

    {
        "topic":            "顔筋（顔の筋肉）とは",
        "knowledge_type":   "mechanism",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "仕組み,顔筋,たるみ,老け見え",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】顔に何種類の筋肉があるか、何の役割を担っているかを1〜3文で。",
    },
    {
        "topic":            "顔筋が衰えると起きること",
        "knowledge_type":   "mechanism",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "仕組み,顔筋,たるみ,老け見え,原因",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】顔筋が衰えたときに起きる具体的な見た目の変化（ほうれい線・フェイスラインなど）を1〜3文で。",
    },
    {
        "topic":            "リンパと顔のむくみの関係",
        "knowledge_type":   "mechanism",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "仕組み,リンパ,むくみ,骨格",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】リンパが滞ると顔にどう影響するか、どこを流すと変わるかを1〜3文で。",
    },
    {
        "topic":            "骨格と顔の形の関係",
        "knowledge_type":   "mechanism",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "仕組み,骨格,誤解",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】「骨格だから無理」は本当か。骨格と顔の位置の関係を正直に1〜3文で。",
    },
    {
        "topic":            "CORE HARIの施術が何にアプローチするか",
        "knowledge_type":   "mechanism",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "仕組み,施術",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】CORE HARIの施術は筋肉・リンパ・骨格のどれにどうアプローチするかを1〜3文で。",
    },
    {
        "topic":            "顔の左右差が生まれる仕組み",
        "knowledge_type":   "mechanism",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "仕組み,左右差,生活習慣",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】日常のどんな習慣・グセが左右差を生むか、なぜそうなるかを1〜3文で。",
    },

    # ─── SYMPTOM（悩み）6件 ────────────────────────────────────────────────

    {
        "topic":            "たるみ・フェイスライン崩れの悩み",
        "knowledge_type":   "symptom",
        "content_role":     "hook",
        "fact":             "",
        "example_sentence": "",
        "tags":             "たるみ,老け見え,フェイスライン",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】たるみ・フェイスライン崩れを訴えるお客様が実際に言う言葉と、その主な原因を1〜3文で。",
    },
    {
        "topic":            "むくみ・顔が大きく見える悩み",
        "knowledge_type":   "symptom",
        "content_role":     "hook",
        "fact":             "",
        "example_sentence": "",
        "tags":             "むくみ,骨格,リンパ,誤解",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】「顔が大きい」という悩みの実態（骨格 vs むくみ）を正直に1〜3文で。",
    },
    {
        "topic":            "ほうれい線の悩み",
        "knowledge_type":   "symptom",
        "content_role":     "hook",
        "fact":             "",
        "example_sentence": "",
        "tags":             "たるみ,ほうれい線,表情グセ",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】ほうれい線が深くなる主な原因と、スキンケアだけでは限界な理由を1〜3文で。",
    },
    {
        "topic":            "笑顔に自信がない悩み",
        "knowledge_type":   "symptom",
        "content_role":     "hook",
        "fact":             "",
        "example_sentence": "",
        "tags":             "笑顔,共感",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】笑顔に自信がないお客様が実際によく言う言葉・相談内容を1〜3文で（CORE HARIのMissionと直結する）。",
    },
    {
        "topic":            "顔の左右差の悩み",
        "knowledge_type":   "symptom",
        "content_role":     "hook",
        "fact":             "",
        "example_sentence": "",
        "tags":             "左右差,生活習慣",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】左右差で悩んでいるお客様から実際によく聞く言葉と、あきらめなくていい理由を1〜3文で。",
    },
    {
        "topic":            "骨格だから無理という誤解",
        "knowledge_type":   "symptom",
        "content_role":     "hook",
        "fact":             "",
        "example_sentence": "",
        "tags":             "誤解,骨格,むくみ",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】「骨格だから無理」とあきらめているお客様の実態と、それが誤解であることを1〜3文で。",
    },

    # ─── OUTCOME（効果・変化）5件 ──────────────────────────────────────────

    {
        "topic":            "1回目の施術後に感じる変化",
        "knowledge_type":   "outcome",
        "content_role":     "proof",
        "fact":             "",
        "example_sentence": "",
        "tags":             "効果,変化,施術回数",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】1回目の施術後にお客様がよく言う言葉・感じる変化を正直に1〜3文で（過大な期待を持たせない）。",
    },
    {
        "topic":            "3回目前後の変化",
        "knowledge_type":   "outcome",
        "content_role":     "proof",
        "fact":             "",
        "example_sentence": "",
        "tags":             "効果,変化,施術回数",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】3回目前後でよく起きる変化・お客様からよく聞く言葉を1〜3文で。",
    },
    {
        "topic":            "6回・継続後の変化",
        "knowledge_type":   "outcome",
        "content_role":     "proof",
        "fact":             "",
        "example_sentence": "",
        "tags":             "効果,変化,施術回数",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】6回以上継続したお客様に起きる変化・定着の感覚を1〜3文で。",
    },
    {
        "topic":            "個人差について正直に伝えること",
        "knowledge_type":   "outcome",
        "content_role":     "proof",
        "fact":             "",
        "example_sentence": "",
        "tags":             "効果,変化,誠実さ",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】変化に個人差がある理由と、それでも続けると変わると言える根拠を1〜3文で。※断言はNG。",
    },
    {
        "topic":            "セルフケアとの組み合わせ効果",
        "knowledge_type":   "outcome",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "効果,セルフケア,生活習慣",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】施術と日常のセルフケアを組み合わせることで変化がどう変わるかを1〜3文で。",
    },

    # ─── PROCESS（手順・フロー）4件 ────────────────────────────────────────

    {
        "topic":            "初回カウンセリングの内容",
        "knowledge_type":   "process",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "施術の流れ,カウンセリング",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】初回カウンセリングで実際に聞くこと・かかる時間・押しつけないというスタンスを1〜3文で。",
    },
    {
        "topic":            "施術中の流れと所要時間",
        "knowledge_type":   "process",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "施術の流れ",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】施術中に何をするか・何分かかるか・お客様の過ごし方（話してもOK等）を1〜3文で。",
    },
    {
        "topic":            "施術後のホームケア指導",
        "knowledge_type":   "process",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "施術の流れ,ホームケア",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】施術後にお客様に伝えること・伝えない（押しつけない）ことの方針を1〜3文で。",
    },
    {
        "topic":            "通院頻度の目安",
        "knowledge_type":   "process",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "施術の流れ,施術回数",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】最初の通院ペース・変化が定着したあとのメンテナンス間隔を1〜3文で。",
    },

    # ─── FAQ（よくある質問）4件 ────────────────────────────────────────────

    {
        "topic":            "施術は痛いか",
        "knowledge_type":   "faq",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "仕組み,施術,誤解",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】施術中の感覚を正直に・安心できる言葉で1〜3文で。「痛い」という言葉は避ける。",
    },
    {
        "topic":            "男性も受けられるか",
        "knowledge_type":   "faq",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "施術の流れ",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】男性のお客様の有無・受け入れ姿勢を1〜2文で。",
    },
    {
        "topic":            "何回通えばいいか",
        "knowledge_type":   "faq",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "効果,変化,施術回数",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】「何回で変わりますか？」という質問に正直かつ希望を持てる形で答えるとしたら何と言うかを1〜3文で。",
    },
    {
        "topic":            "他のエステや美容院との違い",
        "knowledge_type":   "faq",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "仕組み,施術",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】CORE HARIが「顔専門」である理由・他サロンとの違いを1〜2文で。",
    },

    # ─── SELF_CARE（セルフケア）2件 ──────────────────────────────────────

    {
        "topic":            "顔の老け見えを防ぐ表情グセの直し方",
        "knowledge_type":   "self_care",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "セルフケア,表情グセ,生活習慣",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】老け見えを加速する表情グセを具体的に3つ挙げ、直し方を1〜3文で。",
    },
    {
        "topic":            "むくみを防ぐ日常習慣",
        "knowledge_type":   "self_care",
        "content_role":     "body",
        "fact":             "",
        "example_sentence": "",
        "tags":             "セルフケア,むくみ,リンパ,生活習慣",
        "source":           "オーナー確認待ち",
        "verified":         "",
        "added_at":         TODAY,
        "notes":            "【入力ガイド】お客様が今日から実践できるむくみ予防の習慣を具体的に1〜3文で（難しくしない）。",
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# 最初の10件の「完成入力例」（core_hari_kb_samplesシートに書き込む）
# ここは「こう書けばいい」という参考例です。実際の内容はオーナーが書き換えてください。
# ──────────────────────────────────────────────────────────────────────────────

SAMPLE_ENTRIES = [
    {
        "topic":            "顔筋（顔の筋肉）とは",
        "knowledge_type":   "mechanism",
        "content_role":     "body",
        "fact":             "顔には約60種類の筋肉があり、表情を作るだけでなくフェイスラインや目元のリフトアップにも関わっています。体の筋肉と同様に、使わないと衰えて重力で下がります。",
        "example_sentence": "顔には60種類もの筋肉があるんです。使わないと衰えて、顔が下に引っ張られていきます。",
        "tags":             "仕組み,顔筋,たるみ,老け見え",
        "source":           "入力例（要オーナー確認）",
        "verified":         "no",
        "added_at":         TODAY,
        "notes":            "※これは入力例です。実際の知識はオーナーが書き直してください。",
    },
    {
        "topic":            "顔筋が衰えると起きること",
        "knowledge_type":   "mechanism",
        "content_role":     "body",
        "fact":             "顔筋が衰えると、ほうれい線の深化・フェイスラインのたるみ・目元の下がりが起きます。これが「老け見え」の主な正体です。",
        "example_sentence": "顔筋が落ちると、ほうれい線・フェイスライン・目元が重力で下がってきます。これが老け見えの正体なんです。",
        "tags":             "仕組み,顔筋,たるみ,老け見え,原因",
        "source":           "入力例（要オーナー確認）",
        "verified":         "no",
        "added_at":         TODAY,
        "notes":            "※これは入力例です。",
    },
    {
        "topic":            "リンパと顔のむくみの関係",
        "knowledge_type":   "mechanism",
        "content_role":     "body",
        "fact":             "リンパの流れが滞ると老廃物や余分な水分が顔に溜まり、むくみが起きます。耳の下・首のリンパ節が詰まりやすく、ここを流すことで顔がスッキリします。",
        "example_sentence": "リンパが滞ると余分な水分が顔に溜まって、顔がパンパンに見えるんです。耳の下を流すと一気に変わります。",
        "tags":             "仕組み,リンパ,むくみ,骨格",
        "source":           "入力例（要オーナー確認）",
        "verified":         "no",
        "added_at":         TODAY,
        "notes":            "※これは入力例です。",
    },
    {
        "topic":            "骨格と顔の形の関係",
        "knowledge_type":   "mechanism",
        "content_role":     "body",
        "fact":             "顔の骨格は固定されていますが、骨の「位置」は筋肉・靭帯の引っ張りによって少しずつズレます。繰り返しの施術でこの位置を整えることが小顔矯正の目的のひとつです。",
        "example_sentence": "骨格そのものの大きさは変わりませんが、骨の「位置」は整えられます。そこがポイントです。",
        "tags":             "仕組み,骨格,誤解",
        "source":           "入力例（要オーナー確認）",
        "verified":         "no",
        "added_at":         TODAY,
        "notes":            "※これは入力例です。",
    },
    {
        "topic":            "CORE HARIの施術が何にアプローチするか",
        "knowledge_type":   "mechanism",
        "content_role":     "body",
        "fact":             "CORE HARIの施術は①顔筋のコリをほぐす、②リンパを流してむくみを取る、③骨格の位置を整えるの3つに同時にアプローチします。",
        "example_sentence": "私たちの施術は筋肉・リンパ・骨格の3つに同時にアプローチするのが特徴です。",
        "tags":             "仕組み,施術",
        "source":           "入力例（要オーナー確認）",
        "verified":         "no",
        "added_at":         TODAY,
        "notes":            "※これは入力例です。",
    },
    {
        "topic":            "顔の左右差が生まれる仕組み",
        "knowledge_type":   "mechanism",
        "content_role":     "body",
        "fact":             "噛み癖・寝るときの向き・スマホを持つ手など日常の習慣の積み重ねで、顔の筋肉の使い方に偏りが生まれ、左右差になります。",
        "example_sentence": "左右差のほとんどは日常のクセから来ています。噛み癖・寝方・スマホの持ち方。これが積み重なると顔がズレていきます。",
        "tags":             "仕組み,左右差,生活習慣",
        "source":           "入力例（要オーナー確認）",
        "verified":         "no",
        "added_at":         TODAY,
        "notes":            "※これは入力例です。",
    },
    {
        "topic":            "たるみ・フェイスライン崩れの悩み",
        "knowledge_type":   "symptom",
        "content_role":     "hook",
        "fact":             "「最近フェイスラインがぼやけてきた」「写真を撮ると顔が大きく見える」という悩みは、顔筋の衰えとリンパの滞りが主な原因です。",
        "example_sentence": "フェイスラインがぼやけてきた…そう感じていませんか？それ、顔筋とリンパが原因かもしれません。",
        "tags":             "たるみ,老け見え,フェイスライン",
        "source":           "入力例（要オーナー確認）",
        "verified":         "no",
        "added_at":         TODAY,
        "notes":            "※これは入力例です。",
    },
    {
        "topic":            "むくみ・顔が大きく見える悩み",
        "knowledge_type":   "symptom",
        "content_role":     "hook",
        "fact":             "「顔が大きい」という悩みの多くは、骨格の問題ではなくリンパの滞りによるむくみです。骨格を責める前に、まずむくみを疑ってください。",
        "example_sentence": "「顔が大きい」と思っている方に聞きます。それ、骨格じゃなくてむくみかもしれません。",
        "tags":             "むくみ,骨格,リンパ,誤解",
        "source":           "入力例（要オーナー確認）",
        "verified":         "no",
        "added_at":         TODAY,
        "notes":            "※これは入力例です。",
    },
    {
        "topic":            "ほうれい線の悩み",
        "knowledge_type":   "symptom",
        "content_role":     "hook",
        "fact":             "ほうれい線は頬の脂肪・顔筋の衰え・皮膚のたるみが組み合わさって深くなります。スキンケアで表面だけ保湿しても、根本の顔筋にアプローチしないと限界があります。",
        "example_sentence": "ほうれい線が気になる方、スキンケアだけでは限界があります。顔筋から整える必要があります。",
        "tags":             "たるみ,ほうれい線,表情グセ",
        "source":           "入力例（要オーナー確認）",
        "verified":         "no",
        "added_at":         TODAY,
        "notes":            "※これは入力例です。",
    },
    {
        "topic":            "笑顔に自信がない悩み",
        "knowledge_type":   "symptom",
        "content_role":     "hook",
        "fact":             "「写真で自分の顔を見るのが嫌」「笑ったときの顔が気になる」という悩みは、CORE HARIが最も多く受ける相談のひとつです。",
        "example_sentence": "笑った顔が嫌い、写真を撮るのが怖い。そういう方のためにこの仕事をしています。",
        "tags":             "笑顔,共感",
        "source":           "入力例（要オーナー確認）",
        "verified":         "no",
        "added_at":         TODAY,
        "notes":            "※これは入力例です。CORE HARIのMissionと直結するトピック。",
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# 実行
# ──────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 56)
    print("  CORE HARI Knowledge Base 初期データ投入")
    print("=" * 56)

    # ① 既存トピックを確認（重複を防ぐ）
    try:
        existing = sheets_writer.get_core_hari_kb()
        existing_topics = {r["values"].get("topic", "").strip() for r in existing}
    except Exception as e:
        print(f"  ⚠️ 既存データ確認失敗（新規として全件投入します）: {e}")
        existing_topics = set()

    new_entries = [e for e in ENTRIES if e["topic"] not in existing_topics]
    skipped = len(ENTRIES) - len(new_entries)

    # ② core_hari_kb シートに投入
    if skipped:
        print(f"  スキップ（登録済み）: {skipped} 件")
    if new_entries:
        print(f"  投入中: {len(new_entries)} 件...", end="", flush=True)
        sheets_writer.append_core_hari_kb_entries(new_entries)
        print(" 完了")
    else:
        print("  新規エントリはありませんでした")

    # ③ core_hari_kb_samples シートに入力例を投入
    print("  入力例シート作成中（最初の10件）...", end="", flush=True)
    sheets_writer.save_core_hari_kb_samples(SAMPLE_ENTRIES)
    print(" 完了")

    print()
    print("─" * 56)
    print("  ✓ 完了しました！")
    print()
    print("  次にやること:")
    print()
    print("  Google Sheets を開いて 2 つのシートを確認してください")
    print()
    print("  ① core_hari_kb_samples（入力例シート）")
    print("     → まずここを読んで「どう書けばいいか」を確認")
    print()
    print("  ② core_hari_kb（あなたが入力するシート）")
    print("     → D列（fact）と E列（example_sentence）を入力")
    print("     → 書き終わったら H列（verified）に yes と入力")
    print()
    print("  J列（notes）に「入力ガイド」が書いてあります。参考にしてください。")
    print("─" * 56)


if __name__ == "__main__":
    main()
