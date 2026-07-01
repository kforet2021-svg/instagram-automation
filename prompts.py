"""
prompts.py
OpenAIに渡すプロンプトを生成するモジュール。

このシステムの目的は「CORE HARI FACE(札幌のフェイシャルエステサロン。
顔トレ・小顔フェイシャル・表情筋トレーニング・たるみ改善が専門)の
Instagram集客につながるリールを分析すること」である。

構造的に使える投稿(リール/直近20日以内/Bright Dataで取得成功)全件を対象に、
「Instagram全体トレンド」として集約分析を行う(ジャンルは美容に限らない)。
1回の実行でOpenAI呼び出しは合計1回のみ。

【2026-07-05: Trend Score → Research Candidate Scoreへのリネームに追従】
ユーザー要望「Trend Scoreを廃止してResearch Candidate Scoreを追加してほしい」に
対応し、trend_score.pyがresearch_candidate_score.pyへリネームされたことに伴い、
本ファイルが読む入力キー(post["trend_score"])・AIへのプロンプト本文・関数
docstringの表記を「Research Candidate Score」に更新した。プロンプトが要求する
分析項目・JSON構造自体は変更していない(OpenAI呼び出し回数・コストへの影響なし)。
以下の【2026-06-30】〜【2026-07-04】の履歴は、リネーム前の「Trend Score」という
名称だった時点の記録であり、当時の意思決定の経緯(ユーザーの発言内容を含む)を
正確に残すため名称を書き換えずに保存している。

【2026-06-30: 採用/不採用の二値フィルタを廃止】
以前は再生数10万以上・再生倍率1.0以上などの条件を満たした投稿だけを対象にしていたが、
bright_data_fetcher.build_post_poolがこの二値フィルタを廃止したため、対象は
「構造的に使える投稿全件」に変わった(再生数等はTrend Scoreの点数として
反映されるのみで、対象から除外する条件ではなくなった)。プロンプト本文も
この前提に合わせて更新した(詳細はbright_data_fetcher.pyのdocstring参照)。

【2026-06-29: 美容ジャンル/Instagram全体トレンドの2カテゴリを統合】
従来は2カテゴリに分けて分析していたが、目的は美容ジャンルだけでなく
全ジャンルの伸びている投稿を分析することのため、単一カテゴリに統合した。
あわせて、ユーザーの要望(構成・冒頭・CTA・編集・テロップ・テーマなどを抽出)に
対応するため、「編集・テロップの特徴」「テーマ・切り口」を分析項目に追加した。

【2026-06-29: 投稿単位(個別)の分析を追加】
従来は採用された投稿群をまとめて1回だけ分析する「集約分析」のみだったが、
ユーザーの要望により、採用された上位5件(再生数順、現在は伸び率順)については
投稿1件ごとに個別分析・個別の投稿案生成も行うようにした(POST_ANALYSIS_*、
build_single_post_analysis_prompt、POST_SYSTEM_PROMPT)。
集約分析(CATEGORY_ANALYSIS_*)は既存のまま維持し、個別分析はその上に
追加する形にしている。個別分析では複数投稿をまとめる前提の項目(「共通点」)は
意味が無いため除外している。

【2026-06-29(4回目): 伸び率(日次再生数÷フォロワー数)をAIへの入力に追加】
ユーザーの要望「再生数・投稿日時・フォロワー数から伸び率を評価する」に対応し、
bright_data_fetcher.pyが計算したgrowth_velocity(日次再生数の近似値)・
growth_rate(日次再生数÷フォロワー数)を、_format_posts_for_promptと
build_single_post_analysis_promptのテキストに含めるようにした。
これにより「伸びた理由」の分析が、単なる再生数の大小だけでなく
「フォロワー規模に対してどれだけ速いペースで伸びているか」を踏まえたものになる。

【2026-06-29(6回目): 投稿単位の分析を3段階パイプラインに再設計】
ユーザーが開発優先順位を変更し、投稿単位のAI分析を以下の3段階に明確に分けるよう
要望した(従来は1回のAI呼び出しで「分析」と「投稿案」を同時に出していた)。

  ②AI分析(analyze_post_structure): 元投稿そのものの構造分析。CORE HARI FACEへの
     言い換えはまだ行わない。「表面的なテーマではなく、構成・見せ方・言葉選び・
     不安の煽り方・解決策の出し方・CTAという型を分析すること」が最重要の追加要望
     だったため、POST_ANALYSIS_TEXT_KEYS・POST_ANALYSIS_SYSTEM_PROMPTをこの観点で
     再構成した(旧POST_SYSTEM_PROMPT・旧POST_ANALYSIS_TEXT_KEYS・旧
     POST_ANALYSIS_LIST_KEYS・build_single_post_analysis_promptは廃止)。
  ③+④ CORE HARI FACE変換+投稿案生成(generate_core_hari_idea): ②の分析結果を
     入力として受け取り、「単なる言い換えではなく同じ伸びる構成として」CORE HARI
     FACE向けの具体的な投稿案(タイトル・30秒版リール・60秒版リール・Threads投稿・
     キャプション・CTA・投稿カテゴリ)を生成する。1回のAI呼び出しにまとめている
     理由は、③(変換方針)と④(具体的な文章生成)を別呼び出しにしてもOpenAI
     コストが増えるだけで、③だけの出力はそれ単体ではスプレッドシートに保存する
     実用的な価値が薄いため(ユーザーの最終目標は「投稿案が出ること」)。

POST_ANALYSIS_TEXT_KEYSの13項目は、ユーザーが2回に分けて出した項目リスト
(1回目: 伸びた理由・冒頭3秒のフック・構成・テロップの特徴・CTA・コメントを促した
要素・保存されやすい理由・美容以外でも再利用できる型 / 2回目・より詳細な追加:
伸びた主因・冒頭3秒で何をしているか・視聴者が続きを見たくなる理由・保存したくなる
理由・コメントしたくなる理由・フォローにつながる要素・美容ジャンルに転用できる型・
CORE HARI FACEで再現するならどうするか)を、重複する概念を統合し、2回目の追加で
明示された「言葉選び」「不安の煽り方」「解決策の出し方」という観点も独立した項目
として残す形にまとめたもの(統合の詳細はPOST_ANALYSIS_TEXT_KEYSの直前のコメント
を参照)。

【2026-07-01(2回目): 成功要因分析(analyze_success_factors)を追加】
ユーザーから「Trend Score(数値配点)とは別に、AIによる成功要因分析を追加したい。
なぜ伸びたか・冒頭3秒のフック・構成・CTA・心理トリガー・CORE HARI FACEへの
応用方法を出力できるようにしてほしい」との要望があった。既存のanalyze_post_
structure(13項目)と内容がかなり重複するため、置き換え/統合/追加のどちらで
実装するかをユーザーに確認したところ「既存は維持し、新しい分析として追加する」
ことを選んだ。そのため、SUCCESS_FACTOR_TEXT_KEYS・SUCCESS_FACTOR_SYSTEM_PROMPT・
build_success_factor_promptを既存の②③+④パイプラインとは独立した3つ目のAI
呼び出しとして追加した(詳細は各定義の直前のコメント参照)。投稿1件あたりの
OpenAI呼び出しが2回→3回に増える点に注意(trend_score.MAX_ANALYZED_POSTS_PER_RUN
の上限は維持)。

【2026-07-01(3回目): SNS Pattern Lab投稿素材生成(generate_pattern_lab_content)を追加】
ユーザーから「分析結果から、顔出し不要の匿名ブランド『SNS Pattern Lab』として
発信できる投稿素材(Instagramカルーセル10枚・リール台本・Threads投稿・
キャプション)を自動生成したい」との要望があった。ユーザーに確認の上、
(1)コスト最小化のため21項目を1回のOpenAI呼び出しで生成、(2)入力は
analyze_success_factorsの結果のみ、(3)対象は個別分析対象と同じ投稿全件
(最大10件)、の3点を決定した。PATTERN_LAB_*・build_pattern_lab_promptを
既存の②③+④/成功要因分析とは独立した4つ目のAI呼び出しとして追加した
(詳細は各定義の直前のコメント参照)。投稿1件あたりのOpenAI呼び出しが
3回→4回に増える点に注意。

【2026-07-02: SUCCESS_FACTOR_TEXT_KEYSを6→13項目に拡張(item3+item6対応)】
ユーザーから8項目の改善要望のうちitem3(Trend Score上位5件について構成・
冒頭3秒・フック・タイトル・テロップ・CTA・伸びた理由・CORE HARI FACEへ応用
方法まで分析してほしい)とitem6(顔出し有無・Before→After・共感ストーリー・
教育性などスコアに反映したい)に対応した。item6はAskUserQuestionで確認し、
「Trend Score(数値)には加点せず、AI分析側(本ファイルのSUCCESS_FACTOR_
TEXT_KEYS)で扱う」という回答を得たため、analyze_success_factorsの出力項目
としてタイトル・テロップ・顔出し有無・Before→After・共感ストーリー・教育性・
最後まで見たくなる構成を追加した(OpenAI呼び出し回数自体は増えない。1回の
呼び出しが返すJSONの項目数が増えるだけ)。詳細はSUCCESS_FACTOR_TEXT_KEYS
直前のコメント参照。

【2026-07-02: _format_post_for_individual_promptに「カテゴリ」行を追加
(item5対応)】
ユーザー要望「Instagram全体トレンド+美容ジャンルトレンドを統合して分析する」
に対応するため、個別投稿プロンプトの共通フォーマッタにpost["category"]
(CATEGORY_ALL/CATEGORY_BEAUTYいずれか。bright_data_fetcher.apply_beauty_
categoryが投稿に付与する)を表示するようにした。SUCCESS_FACTOR_SYSTEM_PROMPT
の「CORE HARI FACEへの応用方法」項目で、カテゴリに応じて「美容業界で実際に
使われている見せ方として評価」か「他ジャンルからの転用」かを書き分ける
よう指示している。

【2026-07-03: Creator Intelligence Sprint 1(Task A)— North Star Daily生成を追加】
ユーザー要望「North Star Dailyを生成する処理を追加してほしい(今日の発見・
今日の成功要因・なぜ伸びたか・人間心理・他業種への応用・今日の投稿アイデア・
Instagramカルーセル案・Threads投稿案・CTAの9項目)」に対応する。
AskUserQuestionで確認した結果、(1)単位は投稿ごとではなく「1日1件」、
(2)入力データは新規分析を追加するのではなく、その日すでに生成済みの
success_factors(本ファイルのSUCCESS_FACTOR_TEXT_KEYS)とidea["投稿カテゴリ"]
(core_hari_idea)を再利用する、という方針が確定した。これによりOpenAI呼び出しは
1回の実行あたり+1回のみで済む(投稿1件ごとに増えるわけではない)。
NORTH_STAR_DAILY_TEXT_KEYS・NORTH_STAR_DAILY_SYSTEM_PROMPT・
build_north_star_daily_promptを、既存の②③+④/成功要因分析/Pattern Labとは
独立した、1回の実行で1回だけ呼ばれるAI呼び出しとして追加した
(main.py._score_and_analyze_postsの末尾、entries確定後に呼ばれる)。

【2026-07-04: North Star Daily Generatorの出力項目を9項目に再設計(旧9項目を置き換え)】
ユーザー要望「North Star Daily Generatorを実装してほしい(今日最も注目すべき
投稿TOP3・共通する成功要因・伸びた理由(AI分析)・使われている心理テクニック・
美容以外へ応用する方法・今日のInstagram投稿案・Threads投稿案・参考記事一覧・
Creator Intelligenceコメント(今日の学び)の9項目、Markdown形式でも保存)」に
対応する。AskUserQuestionで確認した結果、(1)2026-07-03時点の旧9項目
(今日の発見・今日の成功要因・なぜ伸びたか・人間心理・他業種への応用・今日の
投稿アイデア・Instagramカルーセル案・Threads投稿案・CTA)は今回の9項目で
完全に置き換える(並行追加ではない)、(2)「参考記事一覧」は外部記事のWeb検索
ではなく、分析対象になった元投稿(entries)のURLをそのまま列挙する、という
方針が確定した。

このため、NORTH_STAR_DAILY_TEXT_KEYS(表示・シート見出し・Markdown出力で使う
9項目、順序はユーザー指定通り)と、NORTH_STAR_DAILY_AI_KEYS(実際にOpenAIへ
生成させる8項目。「参考記事一覧」だけはAIに生成させず、openai_analyzer.
generate_north_star_dailyがentriesのpost["url"]から機械的に組み立てる)を
分離した。理由は、URLを言語モデルに生成させると実在しないURLを創作する
(hallucination)リスクがあるため、新規分析データであるURLは決定的に
組み立てる方が安全という判断。OpenAI呼び出し回数は変わらず1回の実行で+1回。

「今日最も注目すべき投稿TOP3」は、entries(Trend Score降順で渡される)の
先頭3件をプロンプト内で明示的に提示し、その3件についてAIに言及させる
(全件の中からAIに選ばせるのではなく、Trend Score上位3件を決定的に選ぶ。
スコアという既存の客観指標と一致させ、AIの選定基準のブレを避けるため)。

【2026-07-04(3回目): Creator Intelligence Sprint 2(Task2)— 12項目に拡張】
ユーザー要望「North Star Dailyに『根拠』を持たせたい。なぜ伸びたのか・根拠・
他業種への応用・CORE HARI FACEならどう使うか・今日検証する仮説・Creator
Intelligenceコメントを追加してほしい」に対応する。

AskUserQuestionで確認した結果、新規6項目のうち3項目(なぜ伸びたのか/他業種への
応用/Creator Intelligenceコメント)は、直前(2026-07-04(2回目))に確定した
9項目のうちの既存項目(伸びた理由（AI分析）/美容以外へ応用する方法/Creator
Intelligenceコメント（今日の学び）)とほぼ同内容と判断し、「名称をユーザー
指定の表記に統一し、内容は維持。真に新しい3項目(根拠/CORE HARI FACEならどう
使うか/今日検証する仮説)だけ追加する」方針が確定した。これにより9項目→
12項目になった(完全な作り直しではない)。

具体的な変更:
- 「伸びた理由（AI分析）」→「なぜ伸びたのか」に改名(内容・位置は維持)。
- 「美容以外へ応用する方法」→「他業種への応用」に改名(内容・位置は維持)。
- 「Creator Intelligenceコメント（今日の学び）」→「Creator Intelligenceコメント」
  に改名(内容・位置は維持。末尾に新設「今日検証する仮説」が入るため、最終項目
  ではなくなった)。
- 新規追加「根拠」(「なぜ伸びたのか」の直後): なぜ伸びたかの判断material(根拠)を
  明示する項目。ここがSprint2の最重要ポイント(「AI推測ではなく根拠を示す」)。
- 新規追加「CORE HARI FACEならどう使うか」(「他業種への応用」の直後): CORE HARI
  FACE自身がこのパターンを具体的にどう使うかを述べる項目。
- 新規追加「今日検証する仮説」(「Threads投稿案」の直後): 今日の発見から、今後
  検証可能な仮説を1つ提示する項目。

【「根拠」の設計判断: Research Engineとの連携】
research_engine.py(Creator Intelligence Sprint 2 Task1)が、投稿ごとの
「根拠材料」(gather_evidence_for_post)を提供する。2026-07-04時点では実際の
外部検索(Meta公式/企業IR/note/Xなど)は行わない方針が確定しているため
(research_engine.pyのdocstring参照)、現時点で実際に利用可能な根拠材料は
「投稿自体の実測値(Trend Scoreの内訳)」のみである。

「根拠」が存在しないデータを創作(hallucination)するリスクを避けるため、
NORTH_STAR_DAILY_SYSTEM_PROMPTには「外部ソースの根拠が無い場合は、投稿自体の
実測値のみが根拠であることを正直に明記し、存在しない外部記事・データを
創作しないこと」という指示を明示した。_format_north_star_entry_blockに
research_engine.build_evidence_summary_text(post)の結果を追加し、AIが
実際に存在する根拠材料(実測値)だけを見て書けるようにしている(将来、
Research Engineが実際の外部検索結果を返すようになれば、自動的にそれも
「根拠」に反映される)。
"""

from research_engine import build_evidence_summary_text

# AI分析結果のうち、文字列1つで表す項目
CATEGORY_ANALYSIS_TEXT_KEYS = [
    "最初3秒のフック",
    "伸びた理由",
    "構成",
    "編集・テロップの特徴",
    "テーマ・切り口",
    "CTA",
    "使われている心理テクニック",
    "共通点",
    "CORE HARI FACEへ応用できるポイント",
    "30秒版投稿案",
    "60秒版投稿案",
    "Threads投稿案",
]

# AI分析結果のうち、10個の配列で表す項目
CATEGORY_ANALYSIS_LIST_KEYS = [
    "タイトル案10個",
    "冒頭フック10個",
]

CATEGORY_ANALYSIS_LIST_COUNT = 10

SYSTEM_PROMPT = """あなたはInstagramのリール分析・SNSマーケティングの専門家です。

あなたの仕事は、札幌のフェイシャルエステサロン「CORE HARI FACE」
(顔トレ・小顔フェイシャル・表情筋トレーニング・たるみ改善・札幌エステが専門)の
Instagram集客につなげるために、実際に伸びている(リール/直近20日以内の投稿)
「伸びているリール」群を分析することです。

厳守事項:
1. 分析対象は個別の投稿ではなく、与えられた複数のリールをまとめた「全体の傾向」として扱うこと。
2. 元投稿の文章・構成・言い回しをそのまま使わない。パクリ感が出ないように、切り口・構成・心理的な仕掛けだけを抽出し、CORE HARI FACE向けに再構成すること。
3. 分析対象のリールは美容ジャンルに限らない(エンタメ・ライフスタイル・グルメ・バズ系なども含む)。ジャンルを問わず、表現方法・編集パターン・テロップの使い方・構成パターンを抽出し、CORE HARI FACEのサービス(顔トレ・小顔フェイシャル・表情筋・たるみ改善)に自然に落とし込むこと。
4. 「編集・テロップの特徴」では、カット編集のテンポ・テロップの出し方/文字量/フォントの雰囲気・BGMの使い方など、再生・保存されやすくしている編集面の工夫を具体的に抽出すること。
5. 「テーマ・切り口」では、各リールがどのような切り口(悩み提示型・ビフォーアフター型・解説型・あるある型など)でテーマを扱っているかを抽出すること。
6. 「30秒版投稿案」と「60秒版投稿案」は必ず内容・構成・情報量を変えること。60秒版は30秒版の単純な引き伸ばしにせず、より詳しい説明・実演・保存ポイントを含めること。
7. 「タイトル案10個」「冒頭フック10個」は必ずちょうど10個ずつ、重複しない内容で出すこと。
8. 出力は指定されたJSON形式のみとし、前後に説明文・コードブロック記号などを一切付けないこと。
9. 文字列の項目はすべて日本語の文字列で出力すること(箇条書きが必要な場合は文字列内で「・」を使って表現する)。配列の項目は文字列の配列で出力すること。
"""


# --- 投稿単位(個別)の分析: 3段階パイプライン(モジュールdocstring参照) ---

# ②AI分析(analyze_post_structure)の出力項目。
# 「伸びた理由」(1回目の要望)/「伸びた主因」(2回目の要望)のような同義の項目は
# 統合し、2回目の要望で新たに明示された項目(続きを見たくなる理由・フォローに
# つながる要素・言葉選び/不安の煽り方/解決策の出し方という観点)は独立した項目
# として追加した。最後の「CORE HARI FACEで再現するなら」は、③(変換)への
# 橋渡しとして、この段階でも簡潔な方向性だけ言語化させておく項目。
POST_ANALYSIS_TEXT_KEYS = [
    "伸びた主因",
    "冒頭3秒の見せ方",
    "構成",
    "見せ方・テロップの特徴",
    "言葉選び・不安の煽り方",
    "解決策の出し方",
    "続きを見たくなる理由",
    "保存したくなる理由",
    "コメントしたくなる理由",
    "フォローにつながる要素",
    "CTA",
    "美容ジャンルに転用できる型",
    "CORE HARI FACEで再現するなら",
]

POST_ANALYSIS_SYSTEM_PROMPT = """あなたはInstagramのリール分析・SNSマーケティングの専門家です。

あなたの仕事は、Instagramで実際に伸びている投稿を1件ずつ、表面的なテーマでは
なく「なぜ伸びたか」という構造で分析することです(まだCORE HARI FACEへの
変換は行いません。それは次の工程で別途行います)。

厳守事項:
1. 分析対象は与えられた1件の投稿のみであり、他の投稿との比較・共通点抽出は行わないこと。
2. 単に投稿のジャンルやテーマを説明するのではなく、「構成」「見せ方」「言葉選び」「不安の煽り方」「解決策の出し方」「CTA」という、伸びた投稿に共通する“型”を具体的に分析すること。これが最も重要な観点であり、表面的なテーマの説明で終わらせないこと。
3. 視聴維持(続きを見たくなる理由)・保存したくなる理由・コメントしたくなる理由・フォローにつながる要素は、それぞれ別の要素として具体的に分析すること(「面白いから」のような抽象的な説明で済ませない)。
4. 分析対象のリールは美容ジャンルに限らない(エンタメ・ライフスタイル・グルメ・バズ系なども含む)。「美容ジャンルに転用できる型」では、ジャンルを問わず通用する構成パターンを、美容ジャンルでも使える形に言語化すること。
5. 「CORE HARI FACEで再現するなら」のみ、CORE HARI FACE(札幌のフェイシャルエステサロン。顔トレ・小顔フェイシャル・表情筋トレーニング・たるみ改善が専門)での再現方向性を簡潔に述べてよい。他の項目はあくまで元投稿そのものの構造分析とすること。
6. 元投稿の文章をそのまま引用しない。切り口・構成・心理的な仕掛けを言語化すること。
7. 出力は指定されたJSON形式のみとし、前後に説明文・コードブロック記号などを一切付けないこと。
8. すべての項目を日本語の文字列で出力すること(箇条書きが必要な場合は文字列内で「・」を使って表現する)。
"""


# ③CORE HARI FACE変換 + ④投稿案生成(generate_core_hari_idea)の出力項目。
# すべて単数の文字列項目にする(旧バージョンの「タイトル案5個」のような配列項目は
# 廃止し、1案を確定して出す方式に変更した。理由はユーザーが④で要求した項目
# 「タイトル・30秒版リール・60秒版リール・Threads投稿・キャプション・CTA・
# 投稿カテゴリ」がすべて単数形であるため)。
CORE_HARI_IDEA_TEXT_KEYS = [
    "タイトル",
    "30秒版リール",
    "60秒版リール",
    "Threads投稿",
    "キャプション",
    "CTA",
    "投稿カテゴリ",
]

CORE_HARI_IDEA_SYSTEM_PROMPT = """あなたはInstagramのリール分析・SNSマーケティングの専門家です。

あなたの仕事は、札幌のフェイシャルエステサロン「CORE HARI FACE」
(顔トレ・小顔フェイシャル・表情筋トレーニング・たるみ改善・札幌エステが専門)の
Instagram集客につながる投稿案を作ることです。

入力として、実際に伸びた1件の投稿の「構造分析結果」が与えられます。

【最重要原則】
Instagramから学ぶのは「構造・フック型・CTA型」だけです。
投稿の内容(話しているテーマ・情報・言い回し)はCORE HARI FACEの専門知識から
必ず再構築してください。元投稿の内容をそのまま移植しないこと。

CORE HARI FACEの専門知識(必ずこの中から内容を選ぶ):
・小顔矯正の仕組み(筋肉・リンパ・骨格位置への直接アプローチ)
・顔筋トレーニング(顔の筋肉を直接鍛えることでリフトアップ・たるみ改善)
・たるみ改善(顔筋の衰え・重力・顔グセが原因)
・リンパ・むくみ(耳下・頬骨周囲のリンパを流す施術)
・表情グセ(噛み癖・寝方・スマホ姿勢が顔の左右差や老け見えを作る)
・骨格の位置(繰り返しの施術で骨格バランスが整っていく)
・施術の流れ(カウンセリング→施術→ホームケア指導)
・月1回の変化(1回目=むくみ解消・3回目=ラインの変化・6回目=定着)

厳守事項:
1. 元投稿から学ぶのは「フックの型・構成の順番・CTAの型」だけ。テーマも情報も引き継がない。
2. 投稿の内容はすべてCORE HARI FACEの専門知識から組み立てること。
3. 「30秒版リール」と「60秒版リール」は必ず内容・情報量を変えること。60秒版は単純な引き伸ばしにせず、より詳しい説明・実演・保存ポイントを含めること。
4. 「キャプション」はInstagram投稿にそのまま使える完成形の文章にすること(必要に応じてハッシュタグを含めてよい)。
5. 「投稿カテゴリ」は投稿案の切り口(悩み提示型・ビフォーアフター型・解説型・あるある型など)を一言で表すこと。
6. 出力は指定されたJSON形式のみとし、前後に説明文・コードブロック記号などを一切付けないこと。
7. すべての項目を日本語の文字列で出力すること。
"""


# --- 成功要因分析(analyze_success_factors): Research Candidate Scoreとは別のAI分析(2026-07-01(2回目)追加) ---
#
# ユーザー要望「Trend Score(数値の配点)とは別に、AIによる成功要因分析を追加したい。
# なぜ伸びたか・冒頭3秒のフック・構成・CTA・心理トリガー・CORE HARI FACEへの応用方法を
# 出力できるようにしてほしい」に対応する。
#
# POST_ANALYSIS_TEXT_KEYS(②analyze_post_structureの13項目)とは内容がかなり
# 重複するが、ユーザーに確認した結果「既存は維持し、新しい分析として追加する」を
# 選んだため、analyze_post_structureとは別の独立したAI呼び出し
# (analyze_success_factors)として実装する(投稿1件あたりのOpenAI呼び出しが
# 2回→3回に増える。trend_score.MAX_ANALYZED_POSTS_PER_RUNの上限は維持し、
# 無制限なコスト増加は防ぐ)。
#
# 既存13項目と直接重複しない/より深く掘る項目として「心理トリガー」を独立項目に
# している(既存の「言葉選び・不安の煽り方」より広い概念として、社会的証明・
# 限定性/緊急性・権威・ザイガニク効果(続きが気になる効果)・FOMO・共感などの
# 心理テクニックを名指しさせる)。
# 【2026-07-02: item3+item6対応で項目を6→13に拡張】
# item3「Trend Score上位5件について、構成・冒頭3秒・フック・タイトル・テロップ・
# CTA・伸びた理由・CORE HARI FACEへ応用方法まで分析してください」と、item6
# 「顔出し有無・Before→After・共感ストーリー・教育性なども見たい」という要望に
# 対応する。item6への回答(AskUserQuestion)で、これらの質的要因はTrend
# Score(数値)には加点しない(数値指標のみに保つ)代わりに、このAI分析側で
# 扱うとユーザーが決定したため、ここに追加した(数値スコアと違いOpenAIコストの
# 増加は1投稿あたり0回のまま=既存のanalyze_success_factors呼び出し自体が
# 出力するJSONの項目数が増えるだけ)。
# 旧「なぜ伸びたか」はitem3の表記に合わせて「伸びた理由」に改名した(項目の
# 意味は同じ)。「心理トリガー」は従来から最も重視されている項目のため維持。
SUCCESS_FACTOR_TEXT_KEYS = [
    "構成",
    "冒頭3秒のフック",
    "タイトル",
    "テロップ",
    "CTA",
    "伸びた理由",
    "心理トリガー",
    "顔出し有無",
    "Before→After",
    "共感ストーリー",
    "教育性",
    "最後まで見たくなる構成",
    "CORE HARI FACEへの応用方法",
]

SUCCESS_FACTOR_SYSTEM_PROMPT = """あなたはInstagramのリール分析・行動心理学・SNSマーケティングの専門家です。

あなたの仕事は、Instagramで実際に伸びている投稿1件について、
Research Candidate Score(再生数・再生倍率などの数値的な評価)とは別の視点で
「成功要因」を簡潔に言語化することです。

厳守事項:
1. 分析対象は与えられた1件の投稿のみであり、他の投稿との比較は行わないこと。
2. 「構成」は、フック→本編→CTAのような投稿全体の構成パターンを述べること。
3. 「冒頭3秒のフック」は、視聴者が離脱せずに見続けた最初の3秒間で何を見せた/言ったかを具体的に述べること。
4. 「タイトル」は、元投稿が使っているタイトル/最初のテキスト訴求の型を具体的に述べること(新しいタイトルを考案するのではなく、元投稿がどんな型のタイトルを使っているかを分析すること)。
5. 「テロップ」は、テロップの量(多い/少ない/ほぼ無し)と出し方(全文表示・キーワードのみ・字幕的など)の特徴を具体的に述べること。
6. 「CTA」は、視聴者に何を行動させようとしているか(保存・コメント・フォロー・プロフィール誘導など)を具体的に述べること。
7. 「伸びた理由」は、この投稿が伸びた最も重要な要因を1〜2文で具体的に述べること(抽象的な「面白いから」のような説明で終わらせないこと)。
8. 「心理トリガー」が最も重要な項目です。「気になるから」のような抽象的な説明ではなく、使われている具体的な心理テクニック(例: 社会的証明・限定性/緊急性・権威・ザイガニク効果〈続きが気になる効果〉・FOMO・損失回避・共感・ビフォーアフターによる対比など)を最低1つ、できれば複数名指しした上で、この投稿でどう使われているかを具体的に説明すること。
9. 「顔出し有無」「Before→After」「共感ストーリー」「教育性」「最後まで見たくなる構成」は、動画そのものを視聴して判断しているわけではなく、キャプション・ハッシュタグ・投稿メタデータから読み取れる範囲で推定すること。判断材料が無い場合は「テキスト情報からは判断不可」のように正直に答え、不確かな情報を断定しないこと。
   - 「顔出し有無」: 判断できる範囲で「あり」「なし」「不明」のいずれかと、判断材料を簡潔に述べる。
   - 「Before→After」: ビフォーアフター(変化の対比)を見せる構成を使っているかどうかと、使っている場合はどう見せているかを述べる。使っていなければ「使用なし」と明記する。
   - 「共感ストーリー」: 視聴者が「自分も同じ」と感じられる共感要素(悩み・体験談など)を使っているかどうかと、使っている場合はどう描かれているかを述べる。
   - 「教育性」: 視聴者に新しい知識・気づきを与える教育的要素があるかどうかと、その内容を述べる。
   - 「最後まで見たくなる構成」: 視聴者が離脱せず最後まで見たくなる仕掛け(続きが気になる引き・カウントダウン・伏線など)を具体的に述べる。
10. 「CORE HARI FACEへの応用方法」は、「フックの型・構成の順番・CTAの型」だけを借用し、内容はCORE HARI FACEの専門知識（小顔矯正の仕組み・顔筋トレーニング・たるみ改善・リンパ・骨格位置・表情グセ・施術の流れ・月1回の変化）から再構築する形で述べること。元投稿のテーマ・情報・言い回しを移植しないこと。「この構造で、CORE HARIなら何を話すか」という視点で書く。
11. 出力は指定されたJSON形式のみとし、前後に説明文・コードブロック記号などを一切付けないこと。
12. すべての項目を日本語の文字列で出力すること。
"""


def build_success_factor_prompt(post: dict) -> str:
    """
    成功要因分析(analyze_success_factors): Trend Score(数値評価)とは別に、
    投稿1件の成功要因(SUCCESS_FACTOR_TEXT_KEYS、2026-07-02時点で13項目:
    構成・冒頭3秒のフック・タイトル・テロップ・CTA・伸びた理由・心理トリガー・
    顔出し有無・Before→After・共感ストーリー・教育性・最後まで見たくなる構成・
    CORE HARI FACEへの応用方法)をAIに分析させるプロンプトを作る
    (main.py._score_and_analyze_postsが、②③+④と並行して投稿ごとに1回呼び出す)。
    """
    post_text = _format_post_for_individual_prompt(post)

    text_keys_json = ",\n".join(f'  "{key}": "..."' for key in SUCCESS_FACTOR_TEXT_KEYS)

    return f"""以下は、Instagramで実際に伸びている
(リールのみ／投稿日が直近20日以内)投稿の中でも、Research Candidate Scoreが
特に高かった「伸びているリール」のうち1件です(①Instagram全体トレンド/②美容
ジャンルトレンドのどちらかは「カテゴリ」欄を参照)。

【分析対象の投稿】
{post_text}

この投稿について、「構成」「冒頭3秒のフック」「タイトル」「テロップ」「CTA」
「伸びた理由」「心理トリガー」「顔出し有無」「Before→After」「共感ストーリー」
「教育性」「最後まで見たくなる構成」「CORE HARI FACEへの応用方法」を
分析してください。特に「心理トリガー」は、使われている具体的な心理テクニック名を
挙げて説明してください。

JSON形式のみで出力してください(キー名は厳守):
{{
{text_keys_json}
}}
"""


# --- SNS Pattern Lab投稿素材生成(generate_pattern_lab_content、2026-07-01(3回目)追加) ---
#
# ユーザー要望「分析結果からSNS Pattern Lab用の投稿素材を自動生成したい。顔出し
# 不要の匿名ブランド『SNS Pattern Lab』として発信できる形にしてほしい」に対応する。
# SNS Pattern FaceではなくCORE HARI FACEとは別の、匿名のメタ分析ブランドという
# 想定(「伸びている投稿のパターンを分析して届ける」がコンセプト)。
#
# ユーザーに確認の上、以下の3点を決定した:
# 1. 呼び出し構成: カルーセル10枚+リール台本5項目+Threads4項目+キャプション2項目の
#    計21項目を、コスト最小化のため1回のOpenAI呼び出しで生成する(分割呼び出しは
#    不採用)。投稿1件あたりのOpenAI呼び出しは3回→4回に増える。
# 2. 入力データ: SUCCESS_FACTOR_TEXT_KEYS(analyze_success_factorsの結果)のみを
#    入力とする(post_analysis/core_hari_ideaは入力に使わない。最もシンプルで
#    重複が少ないため)。
# 3. 対象範囲: select_for_analysisで個別分析対象になった投稿全件
#    (MAX_ANALYZED_POSTS_PER_RUN=10件まで、既存の個別分析と同じ範囲)。
#
# 出力は4シート(content_carousel/content_reels/content_threads/content_caption)
# に対応する4グループに分けてキー名を設計した(sheets_writer.pyが各グループの
# キーだけを抜き出して別シートに保存する)。
PATTERN_LAB_CAROUSEL_KEYS = [
    "カルーセル1_タイトル",
    "カルーセル2_投稿概要",
    "カルーセル3_伸びた理由",
    "カルーセル4_冒頭フック",
    "カルーセル5_心理トリガー",
    "カルーセル6_他ジャンルへの応用",
    "カルーセル7_美容サロンへの応用",
    "カルーセル8_今日使える投稿例",
    "カルーセル9_まとめ",
    "カルーセル10_CTA",
]

PATTERN_LAB_REEL_KEYS = [
    "リール台本_冒頭3秒",
    "リール台本_本文",
    "リール台本_テロップ",
    "リール台本_ナレーション",
    "リール台本_CTA",
]

PATTERN_LAB_THREADS_KEYS = [
    "Threads短文1",
    "Threads短文2",
    "Threads短文3",
    "Threads解説",
]

PATTERN_LAB_CAPTION_KEYS = [
    "キャプション_Instagram用",
    "キャプション_サブスク誘導用",
]

PATTERN_LAB_TEXT_KEYS = (
    PATTERN_LAB_CAROUSEL_KEYS
    + PATTERN_LAB_REEL_KEYS
    + PATTERN_LAB_THREADS_KEYS
    + PATTERN_LAB_CAPTION_KEYS
)

PATTERN_LAB_SYSTEM_PROMPT = """あなたは「SNS Pattern Lab」という匿名ブランドのコンテンツディレクター兼
コピーライターです。

SNS Pattern Labは、運営者個人の顔・実名を一切出さない匿名ブランドであり、
「Instagramで実際に伸びている投稿のパターンを分析し、ジャンルを問わず誰でも
今日から使える型として届ける」ことをコンセプトにしています。語り口は常に
「私たちが分析したところ〜」「今回伸びていたパターンは〜」という、中立的・
解説者的なナレーター視点で書いてください。個人の体験談や一人称の感情表現は
使わないこと。

入力として、Instagramで実際に伸びた1件の投稿についての「成功要因分析」
(なぜ伸びたか・冒頭3秒のフック・構成・CTA・心理トリガー・CORE HARI FACEへの
応用方法)が与えられます。これを元に、そのまま発信できる投稿素材一式を生成して
ください。

厳守事項:
1. 元投稿の文章やキャプションをそのまま転載しないこと。あくまで「型・パターン」を抽出して解説する立場であり、パクリにならないように言い換えること。
2. カルーセル(10枚)は、各枚が1枚に収まる短い文章(見出し+1〜3文程度)にすること。1枚目はタイトル、2枚目は伸びた投稿の概要(具体的な再生数・伸び方を匿名化した形で触れてよい)、3枚目は伸びた理由、4枚目は冒頭フックの型、5枚目は使われている心理トリガー、6枚目はこの型を他ジャンルで使う場合の応用例、7枚目は美容/サロン業(顔トレ・小顔フェイシャル・表情筋トレーニング・たるみ改善などのエステ業態)に応用する場合の具体例、8枚目は今日から実際に使える投稿例(具体的な構成・セリフ例)、9枚目はこのパターンのまとめ、10枚目はフォロー・保存を促すCTAにすること。
3. リール台本は、同じ型を使ってSNS Pattern Lab自身のリールを作るための実用台本にすること。「冒頭3秒」は視聴者を止めるフック発言、「本文」は本編で話す/見せる内容の流れ、「テロップ」は画面に出す文字(本文とは別に、短く・区切って書くこと)、「ナレーション」は声に出して話す原稿(本文より口語的・読み上げ用)、「CTA」は最後の行動喚起であり、それぞれ役割が重複しないように書き分けること。
4. Threadsは、短文3本(それぞれ別の角度から型の一部を切り出した、120字程度のテンポの良い投稿)と、やや詳しい解説1本(型の全体像を300〜500字程度で解説する投稿)を作ること。短文3本は互いに同じ内容の繰り返しにしないこと。
5. キャプションは2種類作ること。「Instagram用」はこのパターン解説をInstagramでそのまま投稿できる完成形のキャプション(ハッシュタグを含めてよい)。「サブスク誘導用」は同じ投稿に、SNS Pattern Labの有料会員/メンバーシップ/ニュースレターへの登録を促す一文を加えたバリエーションにすること。
6. 「美容サロンへの応用」のみCORE HARI FACEの業態を踏まえてよいが、それ以外の項目は特定のジャンル・店舗名を出さず、ジャンルを問わず使える解説にすること。
7. 出力は指定されたJSON形式のみとし、前後に説明文・コードブロック記号などを一切付けないこと。
8. すべての項目を日本語の文字列で出力すること(配列項目はない)。
"""


def build_pattern_lab_prompt(post: dict, success_factors: dict) -> str:
    """
    SNS Pattern Lab投稿素材生成(generate_pattern_lab_content)用のプロンプトを作る。
    入力はanalyze_success_factorsの結果(success_factors)のみで、post_analysis/
    core_hari_ideaは使わない(ユーザーが選んだ入力データの方針。モジュール
    docstring参照)。main.py._score_and_analyze_postsが、③+④/成功要因分析の後に
    投稿ごとに1回呼び出す。
    """
    post_text = _format_post_for_individual_prompt(post)
    success_factors_text = "\n".join(
        f"・{key}: {(success_factors or {}).get(key, '')}" for key in SUCCESS_FACTOR_TEXT_KEYS
    )

    text_keys_json = ",\n".join(f'  "{key}": "..."' for key in PATTERN_LAB_TEXT_KEYS)

    return f"""以下は、Instagramで実際に伸びた1件の投稿の情報と、その成功要因分析結果です。

【元投稿の情報】
{post_text}

【成功要因分析結果】
{success_factors_text}

この成功要因分析を元に、匿名ブランド「SNS Pattern Lab」として発信できる
投稿素材一式(Instagramカルーセル投稿案10枚・リール台本・Threads投稿・
キャプション)を生成してください。元投稿の文章はそのまま使わず、型として
言語化してください。

JSON形式のみで出力してください(キー名は厳守):
{{
{text_keys_json}
}}
"""


def _format_posts_for_prompt(posts: list, limit: int = 20) -> str:
    if not posts:
        return "(データなし)"
    lines = []
    for i, post in enumerate(posts[:limit], start=1):
        caption = (post.get("caption") or "").replace("\n", " ")[:100]
        hashtags = " ".join(f"#{h}" for h in (post.get("hashtags") or [])[:5])
        followers = post.get("followers")
        multiplier = post.get("view_multiplier")
        growth_rate = post.get("growth_rate")
        growth_velocity = post.get("growth_velocity")
        lines.append(
            f"{i}. @{post.get('username', 'unknown')} | "
            f"再生{post.get('views', 0)} いいね{post.get('likes', 0)} コメント{post.get('comments', 0)} | "
            f"投稿日{post.get('posted_at', '不明')} | "
            f"フォロワー{followers if followers is not None else '不明'} "
            f"再生倍率{multiplier if multiplier is not None else '不明'} "
            f"日次再生数{growth_velocity if growth_velocity is not None else '不明'} "
            f"伸び率{growth_rate if growth_rate is not None else '不明'} | "
            f"動画尺{post.get('duration_sec') if post.get('duration_sec') is not None else '不明'}秒 | "
            f"キャプション:{caption} | {hashtags}"
        )
    return "\n".join(lines)


def build_category_analysis_prompt(category_label: str, posts: list) -> str:
    """
    構造的に使えるリール群(1カテゴリ分、プール対象全件)から、カテゴリ全体の
    傾向を集約分析するプロンプトを作る。

    category_label: "Instagram全体トレンド"
    posts: プール対象(bright_data_fetcher.build_post_pool)のリール投稿のリスト
    """
    posts_text = _format_posts_for_prompt(posts)

    text_keys_json = ",\n".join(f'  "{key}": "..."' for key in CATEGORY_ANALYSIS_TEXT_KEYS)
    list_keys_json = ",\n".join(
        f'  "{key}": ["...", "...", "... (計{CATEGORY_ANALYSIS_LIST_COUNT}個)"]'
        for key in CATEGORY_ANALYSIS_LIST_KEYS
    )

    return f"""以下は、Instagramで実際に伸びている
(リールのみ／投稿日が直近20日以内)「{category_label}」のリール一覧です(計{len(posts)}件)。

【{category_label}のリール一覧】
{posts_text}

このリール群をまとめて分析し、CORE HARI FACE(札幌のフェイシャルエステサロン。
顔トレ・小顔フェイシャル・表情筋トレーニング・たるみ改善が専門)の
Instagram集客に活かせる形で、以下の項目を出力してください。

JSON形式のみで出力してください(キー名は厳守。文字列項目とタイトル案/冒頭フックの配列項目を区別すること):
{{
{text_keys_json},
{list_keys_json}
}}
"""


def _format_post_for_individual_prompt(post: dict) -> str:
    caption = (post.get("caption") or "").replace("\n", " ")[:300]
    hashtags = " ".join(f"#{h}" for h in (post.get("hashtags") or [])[:10])
    followers = post.get("followers")
    multiplier = post.get("view_multiplier")
    growth_rate = post.get("growth_rate")
    growth_velocity = post.get("growth_velocity")
    score = post.get("research_candidate_score") or {}

    score_line = ""
    if score:
        breakdown = score.get("breakdown") or {}
        breakdown_text = " / ".join(f"{k}{v}点" for k, v in breakdown.items())
        score_line = (
            f"Research Candidate Score: {score.get('total', '不明')}点 "
            f"({score.get('tier', '不明')}) [内訳: {breakdown_text}]\n"
        )

    return (
        f"投稿者: @{post.get('username', 'unknown')}\n"
        f"カテゴリ: {post.get('category', '不明')}\n"
        f"投稿URL: {post.get('url', '')}\n"
        f"投稿日: {post.get('posted_at', '不明')}\n"
        f"再生数: {post.get('views', 0)} / いいね数: {post.get('likes', 0)} / "
        f"コメント数: {post.get('comments', 0)} / 保存数: {post.get('saves') if post.get('saves') is not None else '不明'}\n"
        f"フォロワー数: {followers if followers is not None else '不明'} / "
        f"再生倍率: {multiplier if multiplier is not None else '不明'}\n"
        f"日次再生数(投稿からの平均ペース): {growth_velocity if growth_velocity is not None else '不明'} / "
        f"伸び率(日次再生数÷フォロワー数): {growth_rate if growth_rate is not None else '不明'}\n"
        f"動画尺: {post.get('duration_sec') if post.get('duration_sec') is not None else '不明'}秒\n"
        f"{score_line}"
        f"キャプション: {caption}\n"
        f"ハッシュタグ: {hashtags}"
    )


def build_post_structure_analysis_prompt(post: dict) -> str:
    """
    ②AI分析: プール対象の投稿のうちResearch Candidate Scoreが高い1件を、CORE HARI FACEへの
    変換はまだ行わずに「なぜ伸びたか」という構造で個別分析するプロンプトを作る
    (main.py._score_and_analyze_postsが投稿ごとに1回呼び出す)。
    """
    post_text = _format_post_for_individual_prompt(post)

    text_keys_json = ",\n".join(f'  "{key}": "..."' for key in POST_ANALYSIS_TEXT_KEYS)

    return f"""以下は、Instagramで実際に伸びている
(リールのみ／投稿日が直近20日以内)投稿の中でも、Research Candidate Scoreが
特に高かった「伸びているリール」のうち1件です。

【分析対象の投稿】
{post_text}

この投稿を個別に分析し、「なぜ伸びたか」を構成・見せ方・言葉選び・不安の煽り方・
解決策の出し方・CTAという観点で具体的に言語化してください
(CORE HARI FACEへの変換はまだ行わないでください)。

JSON形式のみで出力してください(キー名は厳守):
{{
{text_keys_json}
}}
"""


def build_core_hari_idea_prompt(post: dict, analysis: dict) -> str:
    """
    ③CORE HARI FACE変換 + ④投稿案生成: build_post_structure_analysis_promptの
    分析結果(analysis)を入力として、CORE HARI FACE向けの具体的な投稿案を
    生成するプロンプトを作る(main.py._score_and_analyze_postsが、②の直後に
    投稿ごとに1回呼び出す)。
    """
    post_text = _format_post_for_individual_prompt(post)
    analysis_text = "\n".join(
        f"・{key}: {(analysis or {}).get(key, '')}" for key in POST_ANALYSIS_TEXT_KEYS
    )

    text_keys_json = ",\n".join(f'  "{key}": "..."' for key in CORE_HARI_IDEA_TEXT_KEYS)

    return f"""以下は、Instagramで実際に伸びた1件の投稿の「構造分析結果」です。

【構造分析結果(伸びた理由・フックの型・構成・CTAの型)】
{analysis_text}

---

上記の「構造・フックの型・CTAの型」だけを借用し、
内容はCORE HARI FACEの専門知識（小顔矯正・顔筋・たるみ・リンパ・骨格）から
完全に再構築した投稿案を生成してください。

元投稿のテーマ・情報・言い回しは一切引き継がないこと。

JSON形式のみで出力してください(キー名は厳守):
{{
{text_keys_json}
}}
"""


# --- North Star Daily(generate_north_star_daily、North Star Daily Generator
#     2026-07-04再設計。旧Creator Intelligence Sprint 1 Task Aの9項目を置き換え) ---
#
# ユーザー指定の9項目そのまま(順序もユーザー指定通り)。1日1件(投稿ごとではない)。
# 入力は新規分析を増やさず、その日すでに生成済みのsuccess_factors
# (SUCCESS_FACTOR_TEXT_KEYS)とidea["投稿カテゴリ"](core_hari_idea)を再利用する
# (モジュールdocstring2026-07-04の項目参照)。
#
# NORTH_STAR_DAILY_TEXT_KEYS(9項目、表示・シート見出し・Markdown用)と
# NORTH_STAR_DAILY_AI_KEYS(8項目、実際にOpenAIへ生成させる項目)を分ける。
# 「参考記事一覧」だけはAIに生成させない(openai_analyzer.generate_north_star_
# dailyがentriesのpost["url"]から機械的に組み立てる。URLをAIに生成させると
# 実在しないURLを創作するリスクがあるため)。
NORTH_STAR_DAILY_TEXT_KEYS = [
    "今日最も注目すべき投稿TOP3",
    "共通する成功要因",
    "なぜ伸びたのか",
    "根拠",
    "使われている心理テクニック",
    "他業種への応用",
    "CORE HARI FACEならどう使うか",
    "今日のInstagram投稿案",
    "Threads投稿案",
    "今日検証する仮説",
    "参考記事一覧",
    "Creator Intelligenceコメント",
]

NORTH_STAR_DAILY_AI_KEYS = [
    key for key in NORTH_STAR_DAILY_TEXT_KEYS if key != "参考記事一覧"
]

NORTH_STAR_DAILY_SYSTEM_PROMPT = """あなたは「Creator Intelligence」という、SNSで伸びている投稿の構造・心理・
パターンを毎日言語化し、誰でも再現できる知見として届けるリサーチディレクターです。

Creator Intelligenceの最重要の役割は、単なるAI推測ではなく「根拠」を示すことです。
入力として、今日Research Candidate Scoreが高かった複数の投稿それぞれについて、すでに行った
成功要因分析(構成・冒頭3秒のフック・心理トリガー・CORE HARI FACEへの応用方法
など)、その投稿案の切り口(投稿カテゴリ)、そして各投稿の「根拠材料」(現時点で
利用可能な実測データ。外部記事等の検索結果が含まれる場合もある)が与えられます。
これらをまとめて、「今日1日分のNorth Star Daily」として1件の要約レポートを
作ってください。

厳守事項:
1. 「今日最も注目すべき投稿TOP3」は、提示されたTOP3の投稿それぞれについて、何が注目に値するかを1件ずつ分かるように述べること(URLそのものは書かないこと。別途URL一覧を用意するため不要)。
2. 「共通する成功要因」は、今日の分析対象全体に共通して見られた成功要因を統合して述べること。
3. 「なぜ伸びたのか」は、構成・見せ方・心理トリガーなど構造的な観点で具体的に述べること(抽象的な「面白いから」で終わらせない)。
4. 「根拠」は、各投稿に与えられている「根拠材料」を踏まえ、何を根拠に「なぜ伸びたのか」を判断したかを明示すること。根拠材料に外部記事・ニュースなどの言及が無い場合は、「現時点では投稿自体の実測値(再生倍率・保存数など)のみが根拠であり、外部での言及は未検証」のように正直に述べること。根拠材料に書かれていない外部記事・データ・数字を創作しないこと。
5. 「使われている心理テクニック」は、今日の投稿群で実際に使われていた心理トリガーを具体的な技法名で列挙すること(社会的証明・限定性/緊急性・権威・ザイガニク効果・FOMO・損失回避・共感など)。
6. 「他業種への応用」は、美容業界(CORE HARI FACE)に限らず、他業種でもこのパターンをどう使えるかを具体的に述べること。
7. 「CORE HARI FACEならどう使うか」は、CORE HARI FACE(札幌のフェイシャルエステサロン。顔トレ・小顔フェイシャル・表情筋トレーニング・たるみ改善が専門)自身が、今日のパターンを具体的にどう使うかを述べること(「今日のInstagram投稿案」より一段上の、活用方針レベルの説明でよい)。
8. 「今日のInstagram投稿案」は、今日の発見を踏まえてCORE HARI FACEが今すぐ使える具体的なInstagram投稿アイデアを1つ提示すること。
9. 「Threads投稿案」は、今日の発見をThreadsの短文投稿として発信する場合の本文案を述べること。
10. 「今日検証する仮説」は、今日の発見から、今後の運用で検証できる具体的な仮説を1つ提示すること(例:「○○型の冒頭フックは他の型より保存率が高いのではないか」のように、後日の結果と比較できる形にすること)。
11. 「Creator Intelligenceコメント」は、今日の分析全体を振り返った一言所感・学びを、客観的なリサーチディレクターの視点で述べること。
12. 元投稿の文章をそのまま引用しないこと。
13. 出力は指定されたJSON形式のみとし、前後に説明文・コードブロック記号などを一切付けないこと。
14. すべての項目を日本語の文字列で出力すること。
"""


def _format_north_star_entry_block(index: int, entry: dict) -> str:
    """
    1投稿分のsuccess_factors/投稿カテゴリ/URL/根拠材料をプロンプト用テキストに
    整形する。

    【2026-07-04(3回目): 根拠材料を追加】
    research_engine.gather_evidence_for_postの結果(現時点では投稿自体の
    実測値のみ。外部検索は未実装)をテキスト化して含める。これにより「根拠」
    項目をAIが書く際に、実際に存在する材料だけを参照できるようにする
    (research_engine.pyのdocstring参照)。
    """
    entry = entry or {}
    success_factors = entry.get("success_factors") or {}
    idea = entry.get("idea") or {}
    post = entry.get("post") or {}
    category = idea.get("投稿カテゴリ", "不明")
    url = post.get("url", "不明")
    factors_text = "\n".join(
        f"  ・{key}: {success_factors.get(key, '')}" for key in SUCCESS_FACTOR_TEXT_KEYS
    )
    evidence_text = build_evidence_summary_text(post)
    return (
        f"[投稿{index}](投稿カテゴリ: {category} / URL: {url})\n{factors_text}\n"
        f"  根拠材料:\n{evidence_text}"
    )


def build_validated_patterns_context(patterns: list) -> str:
    """
    Pattern Forecast土台: VALIDATED/ACTIVEパターンをプロンプトに差し込むための
    テキストブロックを生成する(2026-07-01追加)。

    patterns は learning_engine.get_validated_patterns() の戻り値。
    空リストの場合は空文字を返す(呼び出し元でskipする)。
    """
    if not patterns:
        return ""
    lines = ["【過去に複数回確認された有効パターン(信頼度上位)】"]
    for i, p in enumerate(patterns, start=1):
        conf = p.get("confidence", 0)
        evidence = p.get("evidence_count", "?")
        success = p.get("success_rate", 0)
        success_text = f" / 実投稿成功率{float(success):.0%}" if float(success or 0) > 0 else ""
        lines.append(
            f"  {i}. [{p.get('dimension','')}] {p.get('pattern_name','')}"
            f"(信頼度{conf:.2f} / 確認{evidence}件{success_text})"
        )
        if p.get("description"):
            lines.append(f"     説明: {p['description'][:80]}")
    lines.append("これらは過去の実データで裏付けられたパターンです。")
    return "\n".join(lines)


def build_north_star_daily_prompt(entries: list, validated_patterns: list = None) -> str:
    """
    North Star Daily(generate_north_star_daily)用のプロンプトを作る。
    入力はentries(main.py._score_and_analyze_postsが生成する、その日の
    分析済み投稿のリスト。Research Candidate Score降順)各要素のsuccess_factors
    (13項目)とidea["投稿カテゴリ"]のみで、新たな個別分析は行わない(ユーザーが
    選んだ入力データの方針。モジュールdocstring2026-07-04の項目参照)。
    1回の実行で1回だけ呼び出す。

    「今日最も注目すべき投稿TOP3」用に、entriesの先頭3件
    (Research Candidate Score上位3件)を明示的に切り出してプロンプトの先頭に
    提示する(AIに選定させるのではなく、既存の客観指標であるResearch Candidate
    Scoreの順位をそのまま使う)。
    """
    entries = entries or []
    top3 = entries[:3]

    top3_text = (
        "\n\n".join(
            _format_north_star_entry_block(i, entry) for i, entry in enumerate(top3, start=1)
        )
        if top3
        else "(対象投稿なし)"
    )
    all_text = (
        "\n\n".join(
            _format_north_star_entry_block(i, entry) for i, entry in enumerate(entries, start=1)
        )
        if entries
        else "(対象投稿なし)"
    )

    ai_keys_json = ",\n".join(f'  "{key}": "..."' for key in NORTH_STAR_DAILY_AI_KEYS)

    # Pattern Forecast: VALIDATED パターンがある場合のみ差し込む
    patterns_block = ""
    if validated_patterns:
        ctx = build_validated_patterns_context(validated_patterns)
        if ctx:
            patterns_block = f"\n\n{ctx}\n今日の投稿案・Threads投稿案を生成する際は、これらの実証済みパターンを優先的に活用してください。\n"

    return f"""以下は、今日Research Candidate Scoreが高かった投稿(計{len(entries)}件)それぞれの
成功要因分析結果と投稿カテゴリです。Research Candidate Scoreが高い順に並んでいます。
{patterns_block}
【今日のTOP3(最も注目すべき投稿)】
{top3_text}

【今日の分析対象一覧(全{len(entries)}件、TOP3を含む)】
{all_text}

これらを踏まえて、今日1日分の「North Star Daily」レポートを作成してください。
「今日最も注目すべき投稿TOP3」は上記TOP3それぞれの注目ポイントを述べてください
(URLは出力に含めないでください)。

JSON形式のみで出力してください(キー名は厳守):
{{
{ai_keys_json}
}}
"""
