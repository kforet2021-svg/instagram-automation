"""
main.py
Creator Intelligence Platform — エントリーポイント。

このシステムの目的はInstagram投稿を自動化することではなく、
専門家の思考をAIが学び、発信・提案・教育・コンテンツ作成を支援すること。
CORE HARI FACEは最初の実証実験（First Vertical）。

参照: PROJECT_PRINCIPLES.md

【プール条件(2026-06-30: 採用/不採用の二値フィルタを廃止。下記参照)】
bright_data_fetcher.build_post_poolが除外するのは、データとして分析に
使えない投稿のみ:
1. 取得失敗
2. リール以外
3. 投稿日が直近20日より古い
再生数・再生倍率・フォロワー数の有無による除外は行わない。代わりに
research_candidate_score.py(連続スコア。2026-07-05にtrend_score.pyから
リネーム)で評価し、スコアが高い投稿から優先的にAI個別分析の対象にする。

データの流れ:
accounts.py に管理されている取得対象アカウント(ANTENNA_ACCOUNTS、ジャンル不問)
  を読み込む (STEP0)
  -> Bright Data(Reels - Discover by URL)で各アカウントの直近リールを取得 (STEP1)
  -> 構造的に使える投稿全件をプールとして抜き出す (bright_data_fetcher.build_post_pool)
  -> フィルター前の取得投稿全件(除外理由付き)をraw_fetch_logシートに常時保存する
  -> 取得した投稿(フィルタ前の全件)のキャプションから新しいアンテナアカウント候補を
     抽出し、複数のアンテナアカウントから言及されたものは人の承認なしに自動で
     accounts.pyのANTENNA_ACCOUNTSへ追加する (_grow_antenna_accounts)
  -> プール対象の投稿をスプレッドシートに保存 (reelsシート)
  -> ランキングシートを作成 (Instagram全体トレンドTOP20 / 再生倍率TOP20 / 伸び率TOP20 / 保存率TOP20)
  -> プール対象の投稿"全件"についてResearch Candidate Score(0〜100点、
     research_candidate_score.py)を計算し、Research Candidate Score順に
     並べ替えてresearch_candidatesシートに記録する (_score_and_analyze_posts)
  -> Research Candidate Scoreが80点以上(必ず分析+投稿案候補)の投稿だけ、
     投稿ごとに②構造分析(analyze_post_structure)→③+④CORE HARI FACE投稿案生成
     (generate_core_hari_idea)の2段階で個別AI分析し、分析結果をpost_analysis
     シート、投稿案をcore_hari_ideasシートに保存する
     (_score_and_analyze_posts。詳細はresearch_candidate_score.py・
     prompts.pyのdocstring参照)
  -> OpenAIに集約分析を依頼(構成・冒頭・CTA・編集・テロップ・テーマなどを抽出し、
     CORE HARI FACE向けの投稿案に変換)
  -> 分析結果をtrend_analysisシートに保存
  -> 最後に取得・除外・プール件数のログを表示する

【2026-06-29 設計変更(2回目): 候補アカウントの人による採用判断を廃止】
以前は、新規アカウント候補をcandidate_accountsシートに出力し、ユーザーが
「採用/除外」を手入力する半自動フローだった。しかし目的は「Instagram全体で
伸びている投稿を毎日分析し、CORE HARI FACEの投稿案を自動生成すること」であり、
日々の人の判断作業はできる限り無くしたい。そのため、以下のように変更した。
- 複数の異なるアンテナアカウントから言及された候補(accounts.AUTO_PROMOTE_MIN_
  SOURCE_ACCOUNTS件以上、複数の実行をまたいで累積カウント)は、人の承認なしに
  自動的にANTENNA_ACCOUNTSへ追加される(_grow_antenna_accounts → accounts_writer.add_accounts)
- しきい値未満の候補はaccount_mention_trackerシートに記録し、次回以降の実行に持ち越す
- 自動追加された履歴はauto_added_accountsシートにログとして残る(操作不要)
- 明らかに無関係なアカウントが自動追加された場合のみ、ユーザーがaccounts.pyの
  BLOCKED_ACCOUNTSにまれに追記する(日次の判断作業ではない)
あわせて、採用された上位5件(再生数順、現在は伸び率順。下記2026-06-29(4回目)参照)
については投稿ごとの個別AI分析・投稿案生成(_analyze_top_posts)も行うようにした。
集約分析(_analyze_and_save_trend)は維持する。
sync_adopted_accounts.pyは廃止した(ロジックはaccounts_writer.add_accountsに移行)。

【2026-06-29 設計変更(4回目): 採用順を再生数→伸び率に変更】
ユーザーから「アカウント管理より投稿単位の分析を優先し、再生数・投稿日時・
フォロワー数から伸び率を評価してほしい」との要望があったため、
bright_data_fetcher.filter_and_adoptの最終ソートを「再生数が多い順」から
「伸び率(growth_rate = 日次再生数÷フォロワー数)が高い順」に変更した。
これにより、_analyze_top_posts(個別AI分析の対象)とランキングシートの並び順は
「単に再生数が多い投稿」ではなく「フォロワー規模に対して伸びている投稿」を
優先するようになった。詳細は bright_data_fetcher._compute_growth_metrics()
のdocstringを参照。

調査の結果、Bright Data(およびApify含む他社サービス)には、ハッシュタグや
キーワードを起点に「未知の投稿」をInstagram全体から無条件に発見する機能は
存在しない(Instagram自体が公開の全体トレンドAPIを提供していないため)。
そのため、起点アカウントは依然として必要だが、上記の自動拡張フローで
少しずつ広げていく方式にしている。
apify_fetcher.py / competitor_discovery.py は削除せずバックアップとして
残しているが、main.pyからは一切importしておらず、Apifyへの通信は発生しない。
※ サンプル/ダミーデータは一切使用しない。すべて実際のAPIから取得した実データを使う。

【2026-06-29(5回目): 投稿単位のTrend Score評価 + CORE HARI FACE投稿案への変換】
ユーザー要望「投稿単位の評価」と「CORE HARI FACE向け投稿案への変換」に対応し、
以下を追加した。

1. trend_score.py(新規)が、採用された投稿1件ごとにTrend Score(0〜100点)を
   計算する。
2. スコアに応じた判定(ユーザー指定の目安):
   - 90点以上: 必ず分析
   - 80点以上: 投稿案候補
   - 80点未満: 保存のみ(AI個別分析は行わずコストを抑える。70〜79点の扱いに
     ついてはtrend_score.pyのdocstringに判断の経緯を明記している)
3. AI個別分析の呼び出し対象を「上位5件固定」から「Trend Score 80点以上」に
   変更した(_score_and_analyze_posts)。OpenAI呼び出し件数の急増を防ぐため、
   trend_score.MAX_ANALYZED_POSTS_PER_RUN件までという上限も設けている。
4. スプレッドシートにtrend_posts(採用投稿全件のTrend Score記録)・
   core_hari_ideas(投稿案のみ)を新規追加した。詳細はsheets_writer.pyのdocstring参照。
5. 上記はすべて既存のpython3 main.py 1コマンドの実行フローに追加しただけであり、
   新しいエントリーポイントは作っていない。

【2026-06-29(6回目): 開発優先順位を分析精度優先に変更し、3段階AIパイプラインへ再設計】
ユーザーが「データ取得機能は現状で十分。データ取得よりも分析精度を優先してほしい」
と明示し、Trend Score・AI分析パイプラインを以下のように再設計した。

1. trend_score.py: 評価項目のうち2つのキーワードヒューリスティック
   (保存されやすそうな構成・美容以外でも応用できる型)を、実測可能な
   動画時間・投稿頻度に置き換えた(詳細はtrend_score.pyのdocstring参照)。
   閾値・判定ラベル(90/80点)自体は変更していない。
2. trend_score.sort_by_score()を追加し、_score_and_analyze_postsの中で
   Trend Score順(降順)に並べ替えてからtrend_postsシートに保存するように
   した(ユーザー要望「Trend Score順に並べられるようにしてください」)。
3. 投稿単位のAI分析を、1回の呼び出しで分析+投稿案を同時に出す方式
   (openai_analyzer.analyze_single_post)から、明確な3段階に分離した
   (prompts.py・openai_analyzer.pyのdocstring参照)。
   - ②openai_analyzer.analyze_post_structure(post): 元投稿の構造分析
     (なぜ伸びたか・冒頭3秒の見せ方・構成・言葉選び・不安の煽り方・
     解決策の出し方・続きを見たくなる理由・保存/コメント/フォローにつながる
     要素・CTA・美容ジャンルへの転用可能性・CORE HARI FACEで再現するなら)
   - ③+④openai_analyzer.generate_core_hari_idea(post, analysis): ②の結果を
     入力として、CORE HARI FACE向けの具体的な投稿案(タイトル・30秒版リール・
     60秒版リール・Threads投稿・キャプション・CTA・投稿カテゴリ)を生成する
   1投稿あたりのOpenAI呼び出しが1回→2回に増えるが、ユーザーが「データ取得
   よりも分析精度を優先してほしい」と明示したため、コスト最小化より分析の
   多面性・具体性を優先する判断とした(trend_score.MAX_ANALYZED_POSTS_PER_RUNの
   上限は維持し、無制限なコスト増加は防ぐ)。
4. sheets_writer.py: post_analysisシートの保存項目を②の全13項目に、
   core_hari_ideasシートの保存項目を④の全7項目に揃えた(詳細はsheets_writer.py
   のdocstring参照)。
5. bright_data_fetcher.py: trend_score.pyの「投稿頻度」項目の入力として、
   post["account_post_count_window"](今回の取得窓内で同じアカウントから
   取得できた投稿数)を新たに付与するようにした。データ取得方式自体(Bright
   Data・取得件数・バッチ設定)は変更していない(ユーザー要望「データ取得機能は
   現状で十分」のため)。

【2026-06-30: 採用/不採用の二値フィルタを廃止し、Trend Score順位方式に統一】
実データで実行したところ、取得27件中25件が「再生数10万以上」条件で除外され、
採用0件という事態が発生した。ユーザーから次の3点の明確な指示があり対応した。
1. フィルター前のデータ全件(URL・投稿日・再生数・いいね数・フォロワー数・
   再生倍率・除外理由)を確認できるようにする → raw_fetch_logシートに常時
   保存するようにした(sheets_writer.save_raw_fetch_log)。
2. 再生数条件を緩和する → 「緩和」ではなく、3で完全に廃止した。
3. 採用/不採用の二値フィルタをやめ、Trend Score順に並べて分析対象を決める
   設計に変更する → bright_data_fetcher.filter_and_adoptを廃止し、
   build_post_poolに置き換えた。除外するのは「取得失敗・リール以外・投稿日が
   古い」の構造的な3条件のみで、再生数・再生倍率・フォロワー数による除外は
   一切行わない。プールに残った投稿は全件trend_score.score_posts/sort_by_
   scoreでスコアリング・ランキングされ、AI個別分析の対象選定(trend_score.
   select_for_analysis、80点以上)は引き続きスコアベースのまま変更していない
   (この部分は5回目で既にスコア順位方式だったため)。
   旧TARGET_ADOPTED_COUNT(上位20件への絞り込み)も廃止し、プールに残った
   投稿は全件をtrend_postsシートに記録するようにした。

【2026-07-01: trend_score_debugシートへの保存をSTEP6に追加】
ユーザーから「25件取得したのにTrend Score80点以上が0件だった。配点を
確認したい」との要望があり、_score_and_analyze_posts内でsave_trend_posts
の直後にsave_trend_score_debug(posts)を呼ぶようにした。各投稿の生値
(再生数・フォロワー数・再生倍率・いいね率・コメント率・投稿日など)と
得点をセットでtrend_score_debugシートに記録する(詳細はsheets_writer.py・
trend_score.pyのdocstring参照)。Sheets書き込みの一括化(429エラー対策)も
同時に行った(sheets_writer.pyのdocstring参照。main.py側の呼び出し方は
変更していない)。

【2026-07-01(2回目): 成功要因分析(analyze_success_factors)を追加】
Trend Score(数値配点)とは別に、AIによる「成功要因分析」(なぜ伸びたか・
冒頭3秒のフック・構成・CTA・心理トリガー・CORE HARI FACEへの応用方法)を
個別AI分析の3つ目のOpenAI呼び出しとして追加した。既存のanalyze_post_
structure/generate_core_hari_ideaは変更せず、analyze_success_factors(post)
を並行して呼び出し、結果をsuccess_factorsシートに保存する(ユーザーが
「既存は維持し、新しい分析として追加する」ことを選んだため。詳細は
openai_analyzer.py・prompts.py・sheets_writer.pyのdocstring参照)。
1投稿あたりのOpenAI呼び出しは2回→3回に増える。

【2026-07-01(3回目): SNS Pattern Lab投稿素材生成(generate_pattern_lab_content)を追加】
ユーザー要望「分析結果からSNS Pattern Lab用の投稿素材を自動生成したい」に
対応し、個別AI分析の4つ目のOpenAI呼び出しとしてgenerate_pattern_lab_content
(post, success_factors)を追加した。analyze_success_factorsの結果(success_
factors)のみを入力とし(post_analysis/core_hari_ideaの結果は使わない。
ユーザーが選んだ入力データの方針)、顔出し不要の匿名ブランド「SNS Pattern
Lab」として発信できる投稿素材(Instagramカルーセル10枚・リール台本・
Threads投稿・キャプション、計21項目)を1回の呼び出しでまとめて生成する
(コスト重視。ユーザーが「1回の呼び出しに統合」を選択)。対象はTrend
Score80点以上で個別分析される投稿と同じ全件(最大MAX_ANALYZED_POSTS_PER_
RUN件)。生成結果はcontent_carousel/content_reels/content_threads/
content_captionの4シートに分けて保存する(sheets_writer.pyのdocstring
参照)。1投稿あたりのOpenAI呼び出しは3回→4回に増える。

【2026-07-02: 実用レベルへの8項目改善(item1〜8)】
ユーザーから「動いてはいるが実用レベルではない」として8項目の改善要望が
あり、AskUserQuestionで3点(後述)を確認した上で以下を実装した。

1. (item1) bright_data_fetcher._describe_error_itemが、Bright Dataの
   per-itemエラー(例: "Cannot read properties of undefined (reading
   'match')")のtargetをinputのdictそのまま出していた点を修正し、URLだけを
   抽出するようにした(_extract_error_item_url。既にクラッシュせず対象投稿
   だけスキップする実装だったので、これはログの読みやすさの修正)。
2. (item2) trend_score.select_for_analysisの「Trend Score80点以上」という
   しきい値ゲートを廃止し、常に上位TOP_N_FOR_ANALYSIS件(5件)を選ぶ固定
   選定に変更した。80点以上が0件の日でもAI分析が実行されるようにした
   (詳細はtrend_score.pyのdocstring参照)。
3. (item3+item6) prompts.SUCCESS_FACTOR_TEXT_KEYSを6→13項目に拡張し、
   構成・冒頭3秒のフック・タイトル・テロップ・CTA・伸びた理由・心理トリガー
   に加え、顔出し有無・Before→After・共感ストーリー・教育性・最後まで
   見たくなる構成も分析するようにした(item6でユーザーに確認した結果、
   これらの質的要因はTrend Score(数値)には加点せず、このAI分析側で扱う
   方針を選んだ。OpenAI呼び出し回数は増えない)。
4. (item4) Trend Score上位5件の投稿案から、その日実際に使う「30秒リール
   1本・60秒リール1本・Threads投稿1本」を選ぶ_select_daily_content_picksを
   新設した。AskUserQuestionで確認し「上位5件から切り口(投稿カテゴリ)が
   異なる3本を選定」する方式を採用。直近7日分のdaily_content_picksシート
   履歴(sheets_writer.get_recent_pick_categories)を見て、同じ切り口の
   重複を避ける。新規daily_content_picksシートに保存する。
5. (item5) accounts.ANTENNA_ACCOUNTS_BEAUTY(美容ジャンルアカウント)を
   追加し、bright_data_fetcher.apply_beauty_categoryで、1回の取得結果
   (raw_posts)のうち美容ジャンルアカウント由来の投稿だけを事後的に
   category="美容ジャンルトレンド"に再分類するようにした(Bright Dataへの
   再取得は発生せず、取得コストは増えない)。①Instagram全体トレンドと
   ②美容ジャンルトレンドは、Trend Score・個別AI分析では統合したプールとして
   扱い(=上位5件には両カテゴリが混在しうる)、OpenAIの集約分析
   (_analyze_and_save_trend)だけはカテゴリごとに別々に実行する。
6. (item7) sheets_writer.save_trend_analysisを「実行ごとの集計1行」から
   「投稿ごとの1行」に再設計した。旧版はsave_category_trend_summaryに改名し、
   保存先もtrend_analysis_summaryシートに変更した(trend_analysisシート名は
   そのまま、内容だけ投稿ごとに変わったため、既存タブは次回実行前に手動で
   一度クリアする必要がある。sheets_writer.pyのdocstring参照)。
7. (item8) 上記すべて、コードの美しさよりも「毎日必ず動くこと」「分析の質」
   「投稿案の質」を優先する判断を一貫させた(例: item2でしきい値ゲートを
   廃止したのも、item4で候補が足りない場合でもクラッシュせず可能な範囲で
   3本を返すようにしたのも、この方針に基づく)。

【2026-07-03: Creator Intelligence Sprint 1(Task A/B/C基盤の追加)】
ユーザーから「Creator Intelligence Sprint 1 開発指示書を現在のコードベースに
反映してほしい」との要望があった。指示書そのものは見つからず、ユーザーの
メッセージ本文を仕様として扱うことと、3点の設計判断をAskUserQuestionで確認した:
1. North Star Dailyの単位は「1日1件」(投稿ごとではない)。
2. 入力データは新規分析を追加せず、既存のsuccess_factors/idea(core_hari_idea)
   の結果を再利用する(OpenAI呼び出しは1回の実行あたり+1回のみ)。
3. 6つのライブラリ系シート(knowledge_library等)は雛形(タブ+ヘッダー行)
   のみ作成し、自動データ投入は次のスプリント以降に判断する。

既存の取得・解析・保存フロー(Bright Data取得・レスポンス解析・raw_fetch_log/
trend_posts/trend_score_debug保存・AI集約分析保存)は一切変更していない。
追加点のみ:
- north_star_index.compute_north_star_indexを新設し、_score_and_analyze_posts
  の個別分析ループ内でentryごとに計算してentries各要素に追加した(新規の
  OpenAI呼び出しは発生しない。trend_score内訳とsuccess_factorsのテキストのみ
  から計算するヒューリスティック。詳細はnorth_star_index.pyのdocstring参照)。
- generate_north_star_daily(entries)を_score_and_analyze_postsの最後で1回だけ
  呼び出し、save_north_star_dailyでnorth_star_dailyシートに1行保存するように
  した。
- main()の冒頭でensure_creator_intelligence_library_sheets()を呼び、6つの
  ライブラリ系シートの雛形を保証するようにした。

「いきなり大規模リファクタリングしない」というユーザーの指示に従い、
creator_intelligence構成へのディレクトリ整理は今回は行っていない(ユーザーが
動作確認後に判断する予定)。

【2026-07-04: North Star Daily Generator — 出力9項目の再設計+Markdown保存追加】
ユーザーから「North Star Daily Generatorを実装してほしい(今日最も注目すべき
投稿TOP3・共通する成功要因・伸びた理由(AI分析)・使われている心理テクニック・
美容以外へ応用する方法・今日のInstagram投稿案・Threads投稿案・参考記事一覧・
Creator Intelligenceコメント(今日の学び)の9項目。Markdown形式でも保存)」との
要望があった。AskUserQuestionで2点確認した:
1. 2026-07-03時点の旧9項目は今回の9項目で完全に置き換える(並行追加ではない)。
2. 「参考記事一覧」は外部記事のWeb検索ではなく、分析対象になった元投稿のURLを
   そのまま列挙する(新規のWeb検索・OpenAI呼び出しは追加しない)。

既存の取得・解析・保存フロー(Bright Data取得・trend_posts/trend_score_debug
保存・各種AI分析保存)は一切変更していない。追加・変更点:
- prompts.NORTH_STAR_DAILY_TEXT_KEYS(表示用9項目)とNORTH_STAR_DAILY_AI_KEYS
  (OpenAIに生成させる8項目)を分離した。「参考記事一覧」はopenai_analyzer.
  generate_north_star_dailyがentriesのpost["url"]から機械的に組み立てる
  (URLをAIに生成させないことで実在しないURLの創作を防ぐ)。
- north_star_report.pyを新規作成。generate_north_star_dailyの結果を
  reports/north_star_daily/YYYY-MM-DD.md に1日1ファイルとして保存する
  (sheets_writer.save_north_star_dailyによるシート保存とは別の出力経路)。
  _score_and_analyze_postsの末尾、save_north_star_dailyの直後に追加で呼ぶ
  (既存の分析・保存処理が終わった後に追加実行する、というユーザーの指示通り)。
"""

import sys

from config import validate_config
from accounts import (
    ANTENNA_ACCOUNTS,
    ANTENNA_ACCOUNTS_BEAUTY,
    BLOCKED_ACCOUNTS,
    AUTO_PROMOTE_MIN_SOURCE_ACCOUNTS,
)

# --- 取得プロバイダ (INSTAGRAM_FETCH_PROVIDER で brightdata/apify を切り替え) ---
from instagram_fetcher import fetch_trend_posts
from bright_data_fetcher import (
    build_post_pool,
    apply_beauty_category,
    CATEGORY_ALL,
    CATEGORY_BEAUTY,
)

from accounts_writer import add_accounts
from candidate_discovery import build_candidates, classify_candidates
from openai_analyzer import (
    analyze_category_trend,
    analyze_post_structure,
    generate_core_hari_idea,
    analyze_success_factors,
    generate_pattern_lab_content,
    generate_north_star_daily,
    generate_trend_continuity_report,
    generate_editorial_comment,
    generate_editorial_v2,
)
from sheets_writer import (
    save_raw_fetch_log,
    save_adopted_posts,
    save_rankings,
    save_trend_analysis,
    save_trend_analysis_no_data,
    save_run_log,
    save_category_trend_summary,
    save_daily_content_picks,
    get_recent_pick_categories,
    save_research_candidates,
    save_research_candidate_score_debug,
    save_post_analyses,
    save_core_hari_ideas,
    save_success_factors,
    save_content_carousel,
    save_content_reels,
    save_content_threads,
    save_content_caption,
    save_auto_added_accounts,
    get_mention_tracker,
    upsert_mention_tracker,
    remove_from_mention_tracker,
    save_north_star_daily,
    get_recent_success_factors,
    save_trend_continuity_report,
    save_editorial_comment,
    save_editorial_v2,
    save_research_sources,
    ensure_creator_intelligence_library_sheets,
    ensure_manual_post_results_sheet,
    ensure_evidence_sheets,
    ensure_thought_library_sheet,
    seed_thought_library,
)
from north_star_index import compute_north_star_index
from north_star_report import save_north_star_daily_markdown
from learning_engine import run_learning_engine, transition_stale_units, get_validated_patterns
from feedback_collector import run_feedback_collector
from creator_studio import (
    generate_creator_studio_daily, print_creator_studio_summary,
    generate_phase1_daily, print_phase1_summary,
)
from research_candidate_score import (
    score_posts,
    sort_by_score,
    select_for_analysis,
    split_by_views_availability,
    sort_no_views_by_engagement,
    limit_per_account,
    compute_account_stats,
    interleave_by_account,
    TOP_N_FOR_ANALYSIS,
    MAX_POSTS_PER_ACCOUNT,
    MIN_ACCOUNTS_FOR_TREND,
    TIER_MUST_ANALYZE,
    TIER_CANDIDATE,
    TIER_PENDING,
    TIER_SAVE_ONLY,
    filter_by_window,
    RESEARCH_WINDOW_DAYS,
    MIN_CANDIDATE_POSTS,
    ANALYSIS_MIN_SCORE,
)

STATS_LOG_ORDER = [
    ("fetched", "取得件数"),
    ("excluded_fetch_error", "取得失敗件数(Instagramにブロックされた可能性)"),
    ("excluded_not_reel", "リール以外で除外件数"),
    ("excluded_date", "投稿日で除外件数"),
    ("no_followers_count", "フォロワー数未取得件数(除外はせず再生倍率0点扱い)"),
    ("pool_count", "Research Candidate Scoreの対象プール件数(旧:採用件数)"),
]


def _print_stats(label: str, stats: dict) -> None:
    print(f"--- {label} ---")
    for key, jp_label in STATS_LOG_ORDER:
        print(f"{jp_label}: {stats.get(key, 0)}")


def _print_pool_exclusion_summary(stats: dict, raw_posts: list, pool: list) -> None:
    """
    build_post_pool 後の除外理由集計とResearch Candidate残留アカウント別件数を表示する。
    【2026-07-20追加】
    """
    print()
    print("=" * 60)
    print("【除外理由の集計】")
    labels = [
        ("excluded_date",             "期間外（投稿日が古い）"),
        ("excluded_not_reel",         "リール以外"),
        ("excluded_pr",               "PR投稿"),
        ("excluded_product_reviewer", "商品レビュー主体"),
        ("excluded_fetch_error",      "取得失敗"),
    ]
    for key, label in labels:
        cnt = stats.get(key, 0)
        if cnt:
            print(f"  {label}: {cnt}件")

    print()
    print("【Research Candidateへ残った件数】")
    print(f"  合計: {stats.get('pool_count', 0)}件")

    # アカウント別残留件数
    acct_counts: dict[str, int] = {}
    for p in pool:
        acct = (p.get("source_account") or p.get("username") or "").strip()
        if acct:
            acct_counts[acct] = acct_counts.get(acct, 0) + 1
    if acct_counts:
        print("  アカウント別:")
        for acct, cnt in sorted(acct_counts.items(), key=lambda x: -x[1]):
            print(f"    {acct}: {cnt}件")

    # スコア不足は select_for_analysis で決まるため pool 段階ではまだ計算できない
    # → ここでは pool 件数まで表示してスコア不足は後段ログに委ねる

    print("=" * 60)
    print()


def _run_log_from_snapshot_meta(
    snapshot_meta: list,
    accounts: list,
    fetched_count: int,
    pool_count: int,
    post_generated: bool,
    registered_count: int = 0,
) -> None:
    """
    2026-07-18: snapshot_metaの各バッチ情報をもとにrun_logへ保存する。
    回収完了(recovered=True)のバッチは _run_log_recovered で別途処理するため
    ここでは除外する。

    snapshot_metaが空の場合(全バッチ未着手など)は1行だけ保存する。

    【2026-07-20】実行モード・登録アカウント数・バッチ統計をrun_logに追加。
    """
    import bright_data_fetcher as _bdf
    mode_label = "テスト" if _bdf.TEST_MODE else "本番"
    total_batches = len(snapshot_meta)
    completed_batches = sum(1 for m in snapshot_meta if m.get("bd_status") == "ready")
    failed_batches = sum(1 for m in snapshot_meta if m.get("bd_status") not in ("ready", "recovered"))

    non_recovered = [m for m in snapshot_meta if not m.get("recovered")]
    if not non_recovered:
        # snapshot_metaが完全に空(アカウント0件など)でも1行保存する
        try:
            save_run_log({
                "処理種別": "通常実行",
                "対象アカウント": f"{len(accounts)}アカウント",
                "snapshot_id": "-",
                "Bright Data status": "アカウント0件",
                "取得件数": fetched_count,
                "保存件数": pool_count,
                "未回収": "なし",
                "エラー内容": "-",
                "次回確認が必要か": "いいえ",
                "投稿生成を実行したか": "はい" if post_generated else "いいえ",
                "実行モード": mode_label,
                "登録アカウント数": registered_count or len(accounts),
                "対象アカウント数": len(accounts),
                "実行バッチ数": total_batches,
                "完了バッチ数": completed_batches,
                "失敗バッチ数": failed_batches,
            })
        except Exception as e:
            print(f"run_log保存中にエラーが発生しました: {e}")
        return

    for meta in non_recovered:
        bd_status = meta.get("bd_status", "")
        snapshot_id = meta.get("snapshot_id") or "-"
        error_msg = meta.get("error_msg", "")

        if bd_status == "ready":
            処理種別 = "通常実行"
            未回収 = "なし"
            次回確認 = "いいえ"
        elif bd_status == "running":
            処理種別 = "Instagram取得0件（未回収）"
            未回収 = "はい"
            次回確認 = "はい"
            if not error_msg:
                error_msg = "Bright Dataジョブはstatus=runningのまま待機時間を超過。結果未回収"
        elif bd_status == "failed":
            処理種別 = "Instagram取得0件（APIエラー）"
            未回収 = "なし"
            次回確認 = "いいえ"
            if not error_msg:
                error_msg = "Bright Data APIエラー（status=failed）"
        elif bd_status == "trigger_failed":
            処理種別 = "Instagram取得0件（trigger失敗）"
            未回収 = "なし"
            次回確認 = "いいえ"
            if not error_msg:
                error_msg = "Bright Data triggerに失敗（snapshot_id未取得）"
        else:
            処理種別 = f"Instagram取得0件（{bd_status}）"
            未回収 = "不明"
            次回確認 = "いいえ"

        try:
            save_run_log({
                "処理種別": 処理種別,
                "対象アカウント": f"{len(meta.get('accounts', []))}アカウント",
                "snapshot_id": snapshot_id,
                "Bright Data status": bd_status,
                "取得件数": fetched_count,
                "保存件数": pool_count,
                "未回収": 未回収,
                "エラー内容": error_msg or "-",
                "次回確認が必要か": 次回確認,
                "投稿生成を実行したか": "はい" if post_generated else "いいえ",
                "実行モード": mode_label,
                "登録アカウント数": registered_count or len(accounts),
                "対象アカウント数": len(accounts),
                "実行バッチ数": total_batches,
                "完了バッチ数": completed_batches,
                "失敗バッチ数": failed_batches,
            })
        except Exception as e:
            print(f"run_log保存中にエラーが発生しました: {e}")


def _run_log_recovered(snapshot_meta: list) -> None:
    """
    2026-07-18: 前回pending→今回ready(回収完了)になったバッチを
    run_logに「回収完了」行として追記する。元のsnapshot_idとの関連が分かるよう記録する。
    """
    recovered = [m for m in snapshot_meta if m.get("recovered")]
    for meta in recovered:
        snapshot_id = meta.get("snapshot_id") or "-"
        count = meta.get("recovered_count", 0)
        try:
            save_run_log({
                "処理種別": "回収完了（前回pending→今回ready）",
                "対象アカウント": f"{len(meta.get('accounts', []))}アカウント",
                "snapshot_id": snapshot_id,
                "Bright Data status": "recovered",
                "取得件数": count,
                "保存件数": count,
                "未回収": "なし",
                "エラー内容": f"前回未回収snapshot_id={snapshot_id}を今回回収完了",
                "次回確認が必要か": "いいえ",
                "投稿生成を実行したか": "いいえ",
            })
        except Exception as e:
            print(f"run_log(回収完了)保存中にエラーが発生しました: {e}")


def _fetch_raw_posts(label: str, fetch_func) -> tuple:
    """
    (posts: list, snapshot_meta: list, bd_outage: bool, outage_reason: str) の4要素タプルを返す。
    fetch_func が dict {"posts": ..., "snapshot_meta": ..., "bd_outage": ...} を返す場合は展開。
    list を返す旧形式にも後方互換で対応する。
    bd_outage=True のとき Bright Data 障害モード（Instagram取得なしで続行）。
    """
    print(f"{label}の投稿を取得中...")
    try:
        result = fetch_func()
        if isinstance(result, dict):
            bd_outage = result.get("bd_outage", False)
            outage_reason = result.get("outage_reason", "")
            return (
                result.get("posts", []),
                result.get("snapshot_meta", []),
                bd_outage,
                outage_reason,
            )
        return result, [], False, ""  # 旧形式後方互換
    except Exception as e:
        print(f"{label}投稿の取得中にエラーが発生しました: {e}")
        sys.exit(1)


def _grow_antenna_accounts(raw_posts: list, known_accounts: list) -> None:
    """
    取得した投稿(フィルタ前の全件)のキャプションから、未知のアカウント候補を
    抽出し、人の承認なしに自動でANTENNA_ACCOUNTSを拡張する。

    - 複数の異なるアンテナアカウントから言及された候補(累積でAUTO_PROMOTE_MIN_
      SOURCE_ACCOUNTS件以上)は、accounts_writer.add_accounts()でaccounts.pyに
      自動追記し、auto_added_accountsシートにログを残す
    - しきい値未満の候補はaccount_mention_trackerシートに記録し、次回以降の
      実行に持ち越す(複数回の実行をまたいで累積カウントするため)
    - accounts.BLOCKED_ACCOUNTSに含まれる候補は、しきい値に関わらず追加しない

    この処理が失敗しても本来の分析フロー(採用・保存・AI分析)は止めない。
    """
    try:
        candidates = build_candidates(raw_posts, known_accounts)
    except Exception as e:
        print(f"アカウント候補の抽出中にエラーが発生しました: {e}")
        return

    if not candidates:
        return

    try:
        previous_sources = {
            username: data["source_accounts"]
            for username, data in get_mention_tracker().items()
        }
    except Exception as e:
        print(f"累積言及データの読み込み中にエラーが発生しました: {e}")
        previous_sources = {}

    classified = classify_candidates(
        candidates,
        previous_sources,
        BLOCKED_ACCOUNTS,
        min_source_accounts=AUTO_PROMOTE_MIN_SOURCE_ACCOUNTS,
    )

    if classified["blocked"]:
        blocked_names = ", ".join(c["username"] for c in classified["blocked"])
        print(f"BLOCKED_ACCOUNTSに該当するため自動追加をスキップした候補: {blocked_names}")

    promoted_usernames = []
    if classified["to_promote"]:
        try:
            promoted_usernames = add_accounts(
                [c["username"] for c in classified["to_promote"]]
            )
        except Exception as e:
            print(f"accounts.pyへのアカウント自動追記中にエラーが発生しました: {e}")

    if promoted_usernames:
        promoted_entries = [
            c for c in classified["to_promote"] if c["username"] in promoted_usernames
        ]
        print(
            f"複数のアンテナアカウントから言及されたため、{len(promoted_usernames)}件を"
            f"ANTENNA_ACCOUNTSへ自動追加しました: {', '.join(promoted_usernames)}"
        )
        try:
            save_auto_added_accounts(promoted_entries)
        except Exception as e:
            print(f"auto_added_accountsシートへのログ保存中にエラーが発生しました: {e}")
        try:
            remove_from_mention_tracker(promoted_usernames)
        except Exception as e:
            print(f"account_mention_trackerからの削除中にエラーが発生しました: {e}")

    if classified["to_track"]:
        try:
            upsert_mention_tracker(classified["to_track"])
            print(
                f"しきい値未満の候補{len(classified['to_track'])}件をaccount_mention_tracker"
                "シートに記録しました(次回以降の実行で累積)"
            )
        except Exception as e:
            print(f"account_mention_trackerシートへの記録中にエラーが発生しました: {e}")


def _score_and_analyze_posts(posts: list) -> None:
    """
    プール対象の投稿"全件"についてResearch Candidate Score(0〜100点。
    research_candidate_score.py)を計算し、Research Candidate Score順(降順)に
    並べ替えてからresearch_candidatesシートに記録する(2026-06-29(6回目):
    ユーザー要望「Trend Score順に並べられるようにしてください」に対応。
    2026-07-05にtrend_score.pyからresearch_candidate_score.pyへリネーム)。

    【2026-07-05変更】ユーザー要望「Trend Scoreを廃止してResearch Candidate
    Scoreを追加し、研究対象として価値がある投稿だけをAI分析対象にしてほしい」
    に対応し、2026-07-02に廃止していた「ANALYSIS_MIN_SCORE(80点)以上」という
    しきい値ゲートを復活させた。ANALYSIS_MIN_SCORE未満の投稿しかない日は、
    個別AI分析の対象が0件になる(=その日はAI分析を実行しない。これは
    エラーではなく、「研究対象として価値がある投稿だけを分析する」という
    今回の方針どおりの想定内の挙動。詳細はresearch_candidate_score.
    select_for_analysisのdocstring参照)。

    個別AI分析は4段階(2026-07-01(3回目)時点):
    ②analyze_post_structureで元投稿の構造を分析し、③+④generate_core_hari_idea
    でその分析結果を入力としてCORE HARI FACE向けの投稿案を生成する。
    分析結果はpost_analysisシート、投稿案はcore_hari_ideasシートに保存する。
    さらにanalyze_success_factors(post)で成功要因分析(success_factorsシート、
    2026-07-02時点で13項目)、generate_pattern_lab_content(post,
    success_factors)でSNS Pattern Lab投稿素材(content_carousel/content_reels/
    content_threads/content_captionの4シート)を生成・保存する。

    さらに投稿ごとのtrend_analysisシート保存(item7)と、その日実際に使う
    30秒リール/60秒リール/Threads投稿の3本選定・daily_content_picksシート保存
    (item4)もこの関数の最後で行う。

    対象外(上位N件に入らない)の投稿は「保存のみ」(AI分析は行わない)とし、
    OpenAI呼び出しコストを抑える。1件の分析が失敗しても、残りの投稿の分析は
    継続する。
    """
    if not posts:
        return []

    # 2026-07-01: 実行開始時にSTALE自動遷移を行う(last_seen_at >= 30日前のVALIDATEDをSTALEに)
    try:
        transition_stale_units()
    except Exception as e:
        print(f"STALE自動遷移中にエラーが発生しました: {e}")

    # 2026-07-18: ① スコア計算は全件に対して行い、その後で期間フィルタを適用する
    score_posts(posts)

    # 2026-07-18: ① 分析対象を直近RESEARCH_WINDOW_DAYS日以内の投稿に絞り込む
    within_posts, period_excluded = filter_by_window(posts, RESEARCH_WINDOW_DAYS)

    # 2026-07-18: ④ 再生数あり/なしに分類し、再生数なし投稿に除外理由を付与
    sort_by_score(within_posts)
    with_views_posts, without_views_posts = split_by_views_availability(within_posts)
    for p in without_views_posts:
        if not p.get("pool_exclusion_reason"):
            p["pool_exclusion_reason"] = "再生数未取得"

    # 2026-07-18: 同一アカウント上限(最大2件/アカウント)を再生数あり投稿のみに適用
    accepted_posts, acct_excluded = limit_per_account(with_views_posts, MAX_POSTS_PER_ACCOUNT)
    if acct_excluded:
        print(
            f"同一アカウント上限({MAX_POSTS_PER_ACCOUNT}件/アカウント)により"
            f"{len(acct_excluded)}件を除外しました"
        )

    # スコア不足投稿に除外理由を付与（AI分析ゲートを通らない投稿）
    # 最低再生数不足は select_for_analysis() 内で付与されるため、ここでは
    # normalized_score 不足のみを "正規化スコア不足" として付与する。
    for p in accepted_posts:
        norm_score = (p.get("research_candidate_score") or {}).get("normalized_score", 0.0)
        if norm_score < ANALYSIS_MIN_SCORE and not p.get("pool_exclusion_reason"):
            p["pool_exclusion_reason"] = "正規化スコア不足"

    # ⑧ ランキング表示用にアカウントが連続しないよう並び替え
    interleaved_posts = interleave_by_account(accepted_posts)

    # 2026-07-18: ⑥ 集計表示（6項目）
    total_fetched = len(posts)
    total_within = len(within_posts)
    total_with_views = len(with_views_posts)
    views_rate = total_with_views / total_within * 100 if total_within else 0.0
    acct_stats = compute_account_stats(accepted_posts)
    print(
        f"\n--- Research Candidate 集計 ---\n"
        f"  取得投稿数:       {total_fetched}件\n"
        f"  期間外除外:       {len(period_excluded)}件（直近{RESEARCH_WINDOW_DAYS}日より前）\n"
        f"  再生数取得率:     {total_with_views}/{total_within}件 ({views_rate:.1f}%)\n"
        f"  分析対象投稿数:   {len(accepted_posts)}件\n"
        f"  対象アカウント数: {acct_stats['account_count']}アカウント"
    )
    if len(accepted_posts) < MIN_CANDIDATE_POSTS:
        print(
            f"  ⚠ 分析対象が目標件数({MIN_CANDIDATE_POSTS}件)に達していません: "
            f"{len(accepted_posts)}件"
        )
    if not acct_stats["has_min_accounts"]:
        print(
            f"  ⚠ サンプル不足: 分析アカウント数が{acct_stats['account_count']}件です"
            f"（最低{MIN_ACCOUNTS_FOR_TREND}アカウント必要）"
        )
    if acct_stats["total_posts"] > 0:
        pct = acct_stats["max_ratio"] * 100
        print(
            f"  最大アカウント占有率: {acct_stats['max_account']} "
            f"{acct_stats['max_count']}/{acct_stats['total_posts']}件 {pct:.1f}%"
        )
        if acct_stats["has_bias"]:
            print(
                f"  ⚠ 偏りあり: {acct_stats['max_account']}が全体の{pct:.1f}%を占めています（20%超）"
            )

    # Research Candidatesシートに採用+除外の全件を保存
    all_for_sheet = interleaved_posts + acct_excluded + without_views_posts + period_excluded
    try:
        save_research_candidates(all_for_sheet)
        print(
            f"research_candidatesシートに全{len(all_for_sheet)}件を保存しました"
            f"（採用{len(interleaved_posts)}件 / 除外{len(all_for_sheet) - len(interleaved_posts)}件）"
        )
    except Exception as e:
        print(f"research_candidatesシートへの保存中にエラーが発生しました: {e}")

    # 配点内訳は採用済み投稿のみ（スコア計算済みのもの）
    try:
        save_research_candidate_score_debug(accepted_posts)
        print(f"配点内訳を{len(accepted_posts)}件分research_candidate_score_debugシートに保存しました")
    except Exception as e:
        print(f"research_candidate_score_debugシートへの保存中にエラーが発生しました: {e}")

    # tier集計表示
    tier_counts = {TIER_MUST_ANALYZE: 0, TIER_CANDIDATE: 0, TIER_SAVE_ONLY: 0, TIER_PENDING: 0}
    for post in accepted_posts:
        tier = post["research_candidate_score"].get("tier", TIER_SAVE_ONLY)
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    print(
        f"Research Candidate Score判定: "
        f"{TIER_MUST_ANALYZE}{tier_counts[TIER_MUST_ANALYZE]}件 / "
        f"{TIER_CANDIDATE}{tier_counts[TIER_CANDIDATE]}件 / "
        f"{TIER_SAVE_ONLY}{tier_counts[TIER_SAVE_ONLY]}件 / "
        f"{TIER_PENDING}(再生数なし){len(without_views_posts)}件"
    )
    print(f"  → Research Candidate Ranking: {len(with_views_posts)}件 / Engagement参考候補: {len(without_views_posts)}件")

    # 2026-07-17: トレンド継続性分析 — 直近10日間のsuccess_factorsデータを読み込み、
    # 継続トレンド/一時的な話題/飽和度を分析してtrend_continuityシートに保存する。
    # individual AI分析のゲート(ANALYSIS_MIN_SCORE)とは独立して毎実行1回呼ばれる
    # (データ不足時は空dictを保存してスキップ、エラーで他処理をブロックしない)。
    try:
        sf_data = get_recent_success_factors(days=10)
        if sf_data.get("total_posts", 0) > 0:
            print(f"トレンド継続性分析: 直近10日間 {sf_data['total_posts']}件のsuccess_factors → AI分析中...")
            tc_result = generate_trend_continuity_report(
                sf_data["entries_by_day"], sf_data["total_posts"]
            )
            save_trend_continuity_report(sf_data["period"], sf_data["total_posts"], tc_result)
            print("トレンド継続性分析をtrend_continuityシートに保存しました")
        else:
            print("トレンド継続性分析: 直近10日間のsuccess_factorsデータが不足のためスキップ")
    except Exception as e:
        print(f"トレンド継続性分析中にエラーが発生しました: {e}")

    targets = select_for_analysis(accepted_posts)
    score_below_threshold = len(accepted_posts) - len(targets)
    if score_below_threshold > 0:
        print(f"  正規化スコア不足・再生数条件未達・商品販売系: {score_below_threshold}件 → AI分析対象外")
    if not targets:
        # 2026-07-05: しきい値ゲート復活により、ANALYSIS_MIN_SCORE以上の投稿が
        # 1件もない日はここで0件になる。これはエラーではなく、「研究対象として
        # 価値がある投稿だけを分析する」という方針どおりの想定内の挙動なので、
        # 例外を投げずにこの実行のAI分析だけをスキップする。
        print("本日はResearch Candidate Scoreのしきい値を超える投稿がなかったため、AI個別分析はスキップしました")
        return accepted_posts

    print(f"Research Candidate Score上位{len(targets)}件を個別にAI分析中(構造分析→投稿案生成→成功要因分析→SNS Pattern Lab素材生成)...")
    entries = []
    for post in targets:
        try:
            analysis = analyze_post_structure(post)
            idea = generate_core_hari_idea(post, analysis)
            # 2026-07-01(2回目): Trend Score(数値配点)とは別のAI分析「成功要因
            # 分析」(なぜ伸びたか・冒頭3秒のフック・構成・CTA・心理トリガー・
            # CORE HARI FACEへの応用方法)。analyze_post_structure/generate_
            # core_hari_ideaとは独立した3つ目のOpenAI呼び出し(post_analysisとは
            # 別にsuccess_factorsシートへ保存する。ユーザーの選択により既存の
            # post_analysisは置き換えていない)。
            success_factors = analyze_success_factors(post)
            # 2026-07-01(3回目): 成功要因分析の結果を入力として、匿名ブランド
            # 「SNS Pattern Lab」向けの投稿素材(カルーセル10枚・リール台本・
            # Threads投稿・キャプション、計21項目)を1回のOpenAI呼び出しで生成
            # する(post_analysis/core_hari_ideaは入力に使わない。ユーザーが
            # 選んだ入力データの方針)。
            pattern_lab = generate_pattern_lab_content(post, success_factors)
            # 2026-07-03(Creator Intelligence Sprint 1 Task C): North Star
            # Index(仮配点、0〜100点)を計算する。新規のOpenAI呼び出しは発生
            # しない(trend_score内訳とsuccess_factorsのテキストのみから計算する
            # ヒューリスティック。詳細はnorth_star_index.pyのdocstring参照)。
            # 2026-07-03時点ではどのシートにも保存せず、ログ表示のみ(土台)。
            north_star_index = compute_north_star_index(post, success_factors)
            entries.append({
                "post": post,
                "analysis": analysis,
                "idea": idea,
                "success_factors": success_factors,
                "pattern_lab": pattern_lab,
                "north_star_index": north_star_index,
            })
        except Exception as e:
            print(f"投稿({post.get('url', '不明')})の個別分析中にエラーが発生しました: {e}")

    if not entries:
        return accepted_posts

    try:
        save_post_analyses(entries)
        print(f"{len(entries)}件の分析結果をpost_analysisシートに保存しました")
    except Exception as e:
        print(f"post_analysisシートへの保存中にエラーが発生しました: {e}")

    try:
        save_core_hari_ideas(entries)
        print(f"{len(entries)}件の投稿案をcore_hari_ideasシートに保存しました")
    except Exception as e:
        print(f"core_hari_ideasシートへの保存中にエラーが発生しました: {e}")

    try:
        save_success_factors(entries)
        print(f"{len(entries)}件の成功要因分析をsuccess_factorsシートに保存しました")
    except Exception as e:
        print(f"success_factorsシートへの保存中にエラーが発生しました: {e}")

    try:
        save_content_carousel(entries)
        print(f"{len(entries)}件のSNS Pattern Labカルーセル素材をcontent_carouselシートに保存しました")
    except Exception as e:
        print(f"content_carouselシートへの保存中にエラーが発生しました: {e}")

    try:
        save_content_reels(entries)
        print(f"{len(entries)}件のSNS Pattern Labリール台本をcontent_reelsシートに保存しました")
    except Exception as e:
        print(f"content_reelsシートへの保存中にエラーが発生しました: {e}")

    try:
        save_content_threads(entries)
        print(f"{len(entries)}件のSNS Pattern Lab Threads素材をcontent_threadsシートに保存しました")
    except Exception as e:
        print(f"content_threadsシートへの保存中にエラーが発生しました: {e}")

    try:
        save_content_caption(entries)
        print(f"{len(entries)}件のSNS Pattern Labキャプションをcontent_captionシートに保存しました")
    except Exception as e:
        print(f"content_captionシートへの保存中にエラーが発生しました: {e}")

    # 2026-07-02(item7): 投稿ごとのTrend Score・成功要因分析をtrend_analysis
    # シートに保存する(実行ごとの集計1行ではなく、投稿1件ごとに1行)。
    try:
        save_trend_analysis(entries)
        print(f"{len(entries)}件の投稿別分析をtrend_analysisシートに保存しました")
    except Exception as e:
        print(f"trend_analysisシートへの保存中にエラーが発生しました: {e}")

    # 2026-07-02(item4): 上位TOP_N_FOR_ANALYSIS件の投稿案から、その日実際に
    # 使う30秒リール1本・60秒リール1本・Threads投稿1本を選び、
    # daily_content_picksシートに保存する。
    try:
        picks = _select_daily_content_picks(entries)
        if picks:
            save_daily_content_picks(picks)
            print(f"本日の投稿案{len(picks)}件をdaily_content_picksシートに保存しました")
        else:
            print("本日の投稿案を選定できませんでした(候補不足)")
    except Exception as e:
        print(f"daily_content_picksシートへの保存中にエラーが発生しました: {e}")

    # 2026-07-03(Creator Intelligence Sprint 1 Task C): North Star Indexの
    # 内訳をログに要約表示する(土台のみ。シート保存はまだ行わない)。
    for entry in entries:
        nsi = entry.get("north_star_index") or {}
        url = (entry.get("post") or {}).get("url", "不明")
        print(f"North Star Index({url}): 合計{nsi.get('total', 0)}点 内訳{nsi.get('breakdown', {})}")

    # 2026-07-03(Creator Intelligence Sprint 1 Task A): その日のentries全体を
    # 入力に、North Star Dailyを1回だけ生成しnorth_star_dailyシートに保存する
    # (投稿件数に関わらずOpenAI呼び出しは+1回。詳細はopenai_analyzer.
    # generate_north_star_dailyのdocstring参照)。
    # 2026-07-01: Pattern Forecast土台 — VALIDATED/ACTIVEパターンを取得してNorth Star Dailyに差し込む
    try:
        validated_patterns = get_validated_patterns(top_n=3)
        if validated_patterns:
            print(f"Pattern Forecast: VALIDATED/ACTIVEパターン {len(validated_patterns)}件をNorth Star Dailyプロンプトに差し込みます")
    except Exception as e:
        validated_patterns = []
        print(f"Pattern Forecast取得中にエラーが発生しました: {e}")

    try:
        north_star_daily_result = generate_north_star_daily(entries, validated_patterns=validated_patterns)
        save_north_star_daily(entries, north_star_daily_result)
        print("North Star Dailyをnorth_star_dailyシートに保存しました")
    except Exception as e:
        north_star_daily_result = None
        print(f"North Star Dailyの生成・保存中にエラーが発生しました: {e}")

    # 2026-07-17: Research Candidate Sheet改善⑥ 編集長コメント(1回/実行、+1 OpenAI)
    # qualifying投稿全件のsuccess_factors結果を入力に、4項目を生成してeditorial_commentシートに保存。
    try:
        editorial_result = generate_editorial_comment(entries)
        save_editorial_comment(entries, editorial_result)
        print("編集長コメントをeditorial_commentシートに保存しました")
    except Exception as e:
        print(f"編集長コメントの生成・保存中にエラーが発生しました: {e}")

    # 2026-07-29: AI編集長 v2 — Hook5案生成・採点・最優秀案採用・修正版生成(+1 OpenAI)
    try:
        v2_results = generate_editorial_v2(entries)
        save_editorial_v2(entries, v2_results)
        print(f"AI編集長 v2 をeditorial_v2シートに保存しました({len(v2_results)}件)")
    except Exception as e:
        print(f"AI編集長 v2 の生成・保存中にエラーが発生しました: {e}")

    # 2026-07-04(6回目、Sprint2④「North Star Dailyの根拠表示を強化」):
    # North Star Dailyの「根拠」項目はAIがテキストで要約するが、その元になった
    # 根拠材料(出典名/URL/概要/取得日。research_engine.gather_evidence_for_post)
    # 自体はこれまでシートに保存されておらず、人が後から検証できなかった。
    # save_research_sources(既存・未配線だったsheets_writer関数)をここで呼び、
    # 今日のentries全件分の根拠材料そのものをresearch_sourcesシートに保存する
    # ことで、AIの要約だけでなく元データも追える状態にする(新規OpenAI呼び出しは
    # 増やさない。既に持っているTrend Score実測値をそのまま記録するだけ)。
    try:
        save_research_sources(entries)
        print("根拠材料(research_sources)を保存しました")
    except Exception as e:
        print(f"research_sourcesシートへの保存中にエラーが発生しました: {e}")

    # 2026-07-04: シート保存(上記)に加えて、同じ結果をMarkdownファイルとしても
    # 保存する(ユーザー要望「Markdown形式で保存し、north_star_dailyシートにも
    # 保存してください」)。シート保存が失敗していてもMarkdown保存は独立して
    # 試みる(north_star_daily_resultがNoneの場合のみスキップする)。
    if north_star_daily_result is not None:
        try:
            md_path = save_north_star_daily_markdown(entries, north_star_daily_result)
            print(f"North Star DailyをMarkdownファイルに保存しました: {md_path}")
        except Exception as e:
            print(f"North Star DailyのMarkdown保存中にエラーが発生しました: {e}")

    # 2026-07-01: Learning Engine — 分析結果からKnowledgeUnitを抽出し蓄積する。
    # 既存の保存処理が全て終わった後に追加実行する(失敗しても他処理に影響しない)。
    try:
        run_learning_engine(entries)
    except Exception as e:
        print(f"Learning Engineの実行中にエラーが発生しました: {e}")

    # 2026-07-01: Feedback Collector — manual_post_resultsの未処理行を読み込み
    # knowledge_unitsのsuccess_rateを更新する(フィードバックループ)。
    try:
        run_feedback_collector()
    except Exception as e:
        print(f"Feedback Collectorの実行中にエラーが発生しました: {e}")

    return accepted_posts


def _select_daily_content_picks(entries: list) -> list:
    """
    Research Candidate Score上位{TOP_N_FOR_ANALYSIS}件の個別分析結果(entries)から、その日
    実際に使う「30秒リール1本・60秒リール1本・Threads投稿1本」を選ぶ。

    【2026-07-02(item4): AskUserQuestionでの確認結果】
    「上位5件から切り口(投稿カテゴリ)が異なる3本を選定」する方式を採用した
    (「#1の投稿だけを使う」方式は不採用)。直近7日分のdaily_content_picksシート
    履歴(sheets_writer.get_recent_pick_categories)に出てきていないカテゴリを
    優先し、同じ切り口の投稿案が3日連続で似てしまうことを避ける。

    候補が3件未満、またはカテゴリの種類が3種類未満でもクラッシュさせず、
    可能な範囲で1〜3件を返す(item8: 「毎日必ず動くこと」を優先)。

    「切り口」はidea["投稿カテゴリ"](generate_core_hari_ideaが生成する、
    悩み提示型・ビフォーアフター型・解説型・あるある型などの一言ラベル。
    prompts.CORE_HARI_IDEA_TEXT_KEYS参照)を指す。post["category"]
    (Instagram全体トレンド/美容ジャンルトレンドの取得元区分)とは別物なので
    混同しないこと。

    各entryのidea(generate_core_hari_ideaの結果)は"タイトル"/"30秒版リール"/
    "60秒版リール"/"Threads投稿"/"キャプション"/"CTA"/"投稿カテゴリ"を持つ
    1階層のテキスト項目であり(post1件につき1案。3パターンのバリエーションでは
    ない)、"30秒版リール"/"60秒版リール"/"Threads投稿"キーの値を1件ずつ別の
    投稿に割り当てる(3件未満の場合は割り当てられたスロットのみ返す)。
    """
    if not entries:
        return []

    try:
        recent_categories = get_recent_pick_categories()
    except Exception:
        recent_categories = set()

    def _category_of(entry: dict) -> str:
        return (entry.get("idea") or {}).get("投稿カテゴリ", "")

    # 1. 直近7日に使っていないカテゴリの投稿を優先し、Research Candidate Scoreの高い順を保つ
    fresh = [e for e in entries if _category_of(e) not in recent_categories]
    stale = [e for e in entries if _category_of(e) in recent_categories]
    ordered = fresh + stale

    # 2. 切り口(カテゴリ)が異なる投稿を優先しつつ、最大3件選ぶ
    chosen = []
    used_categories = set()
    for entry in ordered:
        if len(chosen) >= 3:
            break
        category = _category_of(entry)
        if category and category in used_categories:
            continue
        chosen.append(entry)
        if category:
            used_categories.add(category)

    # 3. 異なる切り口だけで3件に届かない場合は、残りから埋める(重複カテゴリ許容)
    if len(chosen) < 3:
        for entry in ordered:
            if len(chosen) >= 3:
                break
            if entry in chosen:
                continue
            chosen.append(entry)

    slot_defs = [
        ("30秒リール", "30秒版リール"),
        ("60秒リール", "60秒版リール"),
        ("Threads投稿", "Threads投稿"),
    ]

    picks = []
    for entry, (post_type, idea_key) in zip(chosen, slot_defs):
        idea = entry.get("idea") or {}
        body = idea.get(idea_key)
        if not body:
            continue
        post = entry.get("post") or {}
        picks.append({
            "post_type": post_type,
            "category": _category_of(entry),
            "post": post,
            "score": post.get("research_candidate_score") or {},
            "title": idea.get("タイトル", ""),
            "body": body,
            "caption": idea.get("キャプション", ""),
            "cta": idea.get("CTA", ""),
        })

    return picks


def _compute_reel_stats(reel_posts: list) -> dict:
    """カテゴリ集約分析用のリール統計値を計算する(2026-07-18追加)。"""
    n = len(reel_posts)
    if not n:
        return {}
    accts = {
        (p.get("source_account") or p.get("username") or "").strip().lower()
        for p in reel_posts
        if (p.get("source_account") or p.get("username") or "").strip()
    }
    total_views = sum((p.get("views") or 0) for p in reel_posts)
    like_rates, comment_rates = [], []
    for p in reel_posts:
        followers = p.get("followers") or 0
        if followers:
            like_rates.append((p.get("likes") or 0) / followers)
            comment_rates.append((p.get("comments") or 0) / followers)
    return {
        "reel_count": n,
        "account_count": len(accts),
        "avg_views": round(total_views / n),
        "avg_like_rate_pct": round(sum(like_rates) / len(like_rates) * 100, 2) if like_rates else "",
        "avg_comment_rate_pct": round(sum(comment_rates) / len(comment_rates) * 100, 3) if comment_rates else "",
    }


# 2026-07-18: リール最低分析条件
TREND_MIN_REELS    = 20   # リール本数
TREND_MIN_ACCOUNTS = MIN_ACCOUNTS_FOR_TREND  # アカウント数(=10)


def _analyze_and_save_trend(category_label: str, posts: list) -> None:
    if not posts:
        print(f"{category_label}: プール対象の投稿が無いため分析をスキップしました")
        return

    # 2026-07-18: リールのみ集計対象(カルーセル・通常投稿は除外)
    reel_posts = [p for p in posts if p.get("is_reel", False)]

    # 2026-07-18: 最低分析条件チェック
    reel_stats = _compute_reel_stats(reel_posts)
    n_reels = reel_stats.get("reel_count", 0)
    n_accts = reel_stats.get("account_count", 0)
    if n_reels < TREND_MIN_REELS or n_accts < TREND_MIN_ACCOUNTS:
        print(
            f"{category_label}: ⚠ リール分析データ不足 "
            f"（リール{n_reels}本 / アカウント{n_accts} — "
            f"最低{TREND_MIN_REELS}本・{TREND_MIN_ACCOUNTS}アカウント必要）"
            f"— カテゴリ集約分析をスキップしました"
        )
        return

    print(
        f"{category_label}のリールをAIで集約分析中… "
        f"（リール{n_reels}本 / {n_accts}アカウント / "
        f"平均再生数{reel_stats.get('avg_views',0):,} / "
        f"平均いいね率{reel_stats.get('avg_like_rate_pct','')}% / "
        f"平均コメント率{reel_stats.get('avg_comment_rate_pct','')}%）"
    )
    try:
        # 2026-07-18: reel_postsのみをAI分析に渡す（カルーセル・通常投稿は除外済み）
        analysis = analyze_category_trend(category_label, reel_posts)
    except Exception as e:
        print(f"{category_label}の分析中にエラーが発生しました: {e}")
        return

    try:
        save_category_trend_summary(category_label, reel_posts, analysis, reel_stats=reel_stats)
        print(f"{category_label}の分析結果をスプレッドシートに保存しました")
    except Exception as e:
        print(f"{category_label}の分析結果の保存中にエラーが発生しました: {e}")


def _ceo_review(cs_record: dict, pool_count: int, analyzed_count: int) -> None:
    """
    Creator Intelligence Platform — CEO REVIEW。
    実行データをもとに7つの軸で今回の実行を評価する。
    AI呼び出し・外部通信なし（コストゼロ）。
    """
    import os, pathlib

    # ── データ収集 ─────────────────────────────────────────────────
    # Thought Library の状態
    tl_entries = []
    try:
        import sheets_writer as _sw
        tl_entries = _sw.get_thought_library()
    except Exception:
        pass

    tl_types = {e.get("knowledge_type", "") for e in tl_entries if e.get("knowledge_type")}
    universal_types = {"Observation", "Question", "Evidence", "Experience",
                       "Perspective", "Advice", "Research", "ContentAsset"}
    tl_type_coverage = len(tl_types & universal_types)

    # Creator Studio の実行状態
    cs_ran       = bool(cs_record)
    cs_from_tl   = cs_ran and bool(cs_record.get("thought_library_used"))
    cs_em_match  = cs_ran and cs_record.get("qa_passed", False)

    # Vertical 抽象化の確認（垂直ファイル存在チェック）
    try:
        _here = pathlib.Path(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        _here = pathlib.Path(os.getcwd())
    verticals_dir = _here / "creator_intelligence" / "verticals"
    vertical_count = len([p for p in verticals_dir.iterdir() if p.is_dir() and not p.name.startswith("_")]) if verticals_dir.exists() else 0

    # ── 判定ロジック ───────────────────────────────────────────────
    def _verdict(cond_pass, cond_partial):
        if cond_pass:   return "✅ PASS"
        if cond_partial: return "🔶 PARTIAL"
        return "❌ FAIL"

    checks = []

    # 1. Mission Check
    v = _verdict(
        cs_ran and pool_count > 0,
        cs_ran or pool_count > 0,
    )
    note = ""
    if "PARTIAL" in v:
        note = "→ Creator Studio または投稿取得のいずれかが機能していない。両方が動いてこそMissionに近い。"
    if "FAIL" in v:
        note = "→ Creator Studioも投稿取得も動いていない。パイプライン全体を確認すること。"
    checks.append(("Mission Check", "Creator Intelligenceに近づいているか？", v, note))

    # 2. Generalization Check
    v = _verdict(
        vertical_count >= 1 and tl_type_coverage >= 3,
        vertical_count >= 1,
    )
    note = ""
    if "PARTIAL" in v:
        note = f"→ Vertical抽象化はあるが、Thought Libraryのknowledge_type多様性が低い（{tl_type_coverage}/8種）。"
    if "FAIL" in v:
        note = "→ creator_intelligence/verticals/ にVerticalが存在しない。汎用化が未着手。"
    checks.append(("Generalization Check", "CORE HARI以外の専門家にも使える設計か？", v, note))

    # 3. Asset Check
    v = _verdict(
        len(tl_entries) >= 5 and tl_type_coverage >= 3,
        len(tl_entries) >= 1,
    )
    note = ""
    if "PARTIAL" in v:
        note = f"→ Thought Libraryに{len(tl_entries)}件あるが、knowledge_typeの多様性が足りない（{tl_type_coverage}/8種）。"
    if "FAIL" in v:
        note = "→ Thought Libraryが空。思考資産がゼロの状態では投稿しか残らない。"
    checks.append(("Asset Check", "投稿ではなく、思考資産（Observation/Perspective等）が増えているか？", v, note))

    # 4. 10-Year Check
    # Instagram依存度を確認（将来的な他SNS展開の準備ができているか）
    sheets_module = _here / "sheets_writer.py"
    insta_only = True
    try:
        content = sheets_module.read_text()
        insta_only = "threads" not in content.lower() and "youtube" not in content.lower()
    except Exception:
        pass
    v = _verdict(
        not insta_only and tl_type_coverage >= 3,
        tl_type_coverage >= 2,
    )
    note = ""
    if "PARTIAL" in v:
        note = "→ Thought Libraryの設計は汎用だが、出力先がInstagramに依存している。SNS非依存の出力レイヤーが将来の課題。"
    if "FAIL" in v:
        note = "→ Instagram専用設計のまま。思考資産の蓄積なしでは10年後の価値が残らない。"
    checks.append(("10-Year Check", "10年後も価値が残る設計か？", v, note))

    # 5. Monetization Check
    v = _verdict(
        vertical_count >= 2,  # 2つ目のVerticalが存在すれば「横展開可能」と判断
        vertical_count >= 1 and len(tl_entries) >= 5,
    )
    note = ""
    if "PARTIAL" in v:
        note = "→ First Verticalは動いているが、他業種への展開がまだない。2つ目のVerticalが商品化の証明になる。"
    if "FAIL" in v:
        note = "→ Vertical設計・Thought Libraryの両方が不足。他者に売れる状態ではない。"
    checks.append(("Monetization Check", "将来的に商品化できる価値があるか？", v, note))

    # 6. WOW Check
    # Thought Library × Editorial Meeting × Creator Studio の連動が動いているか
    v = _verdict(
        cs_ran and len(tl_entries) >= 3 and cs_em_match,
        cs_ran and len(tl_entries) >= 1,
    )
    note = ""
    if "PARTIAL" in v:
        note = "→ 各機能は動いているが、Editorial Meeting→Thought Library→Creator Studioの完全連動がまだ浅い。"
    if "FAIL" in v:
        note = "→ Creator Studioが動いていない。WOW体験を生み出す中核機能が停止している。"
    checks.append(("WOW Check", "他社が簡単に真似できない価値があるか？", v, note))

    # 7. Kill Check
    # 「Creator Studioを削除したら何が残るか？」— InstagramデータのみならKILL
    v = _verdict(
        cs_ran and len(tl_entries) >= 3,
        cs_ran,
    )
    note = ""
    if "PARTIAL" in v:
        note = "→ Creator Studioは動いているが、Thought Libraryが薄いためInstagram分析ツールに見える。"
    if "FAIL" in v:
        note = "→ Creator Studioが動いていない。削除しても何も変わらない状態 = Creator Intelligenceではない。"
    checks.append(("Kill Check", "この機能を削除したらCreator Intelligenceらしさが失われるか？", v, note))

    # ── 出力 ──────────────────────────────────────────────────────
    print()
    print("=" * 34)
    print("       CEO REVIEW")
    print("=" * 34)

    pass_count    = sum(1 for _, _, v, _ in checks if "PASS" in v)
    partial_count = sum(1 for _, _, v, _ in checks if "PARTIAL" in v)
    fail_count    = sum(1 for _, _, v, _ in checks if "FAIL" in v)

    for name, question, verdict, note in checks:
        print(f"\n【{name}】")
        print(f"  {question}")
        print(f"  {verdict}")
        if note:
            print(f"  {note}")

    print()
    print(f"  Summary: PASS {pass_count} / PARTIAL {partial_count} / FAIL {fail_count}")
    print()

    if fail_count > 0:
        print("  ⚠️  FAILが残っています。次のスプリントで最優先で対処してください。")
    elif partial_count >= 3:
        print("  📋 PARTIALが多い。Creator Intelligence Platformへの移行を加速してください。")
    else:
        print("  🟢 Creator Intelligence Platformとして正しい方向に進んでいます。")

    print()
    print("  Ref: PROJECT_PRINCIPLES.md")
    print("=" * 34)
    print()


def main(fallback_mode: bool = False) -> None:
    try:
        validate_config()
    except EnvironmentError as e:
        print(f"設定エラー: {e}")
        sys.exit(1)

    # 2026-07-03(Creator Intelligence Sprint 1 Task B): north_star_daily +
    # 6つのライブラリ系シート(雛形・ヘッダーのみ)が無ければ作成する。
    # データ行の書き込みはまだ行わない(自動収集ロジックは次のスプリント以降)。
    try:
        ensure_creator_intelligence_library_sheets()
    except Exception as e:
        print(f"Creator Intelligenceライブラリシートの作成中にエラーが発生しました: {e}")

    # 2026-07-01: フィードバックループ用シート(手入力専用)を起動時に作成する
    try:
        ensure_manual_post_results_sheet()
    except Exception as e:
        print(f"manual_post_resultsシートの作成中にエラーが発生しました: {e}")

    # 2026-07-01(Sprint3): Evidence Layer シートを起動時に作成する
    try:
        ensure_evidence_sheets()
    except Exception as e:
        print(f"evidence_registry/evidence_linksシートの作成中にエラーが発生しました: {e}")

    # 2026-07-02(10回目): Thought Library シートを起動時に作成 + 初回のみシード投入
    try:
        ensure_thought_library_sheet()
        from creator_studio import _THOUGHT_LIBRARY_SEED
        seed_thought_library(_THOUGHT_LIBRARY_SEED)
    except Exception as e:
        print(f"thought_libraryシートの初期化中にエラーが発生しました: {e}")

    # グローバル10分デッドライン(2026-07-02(10回目): タイムアウト対策)
    import time as _time
    _RUN_START = _time.monotonic()
    _RUN_BUDGET_SEC = 570  # 9.5分。残り30秒はCreator Studio出力に確保

    def _budget_remaining() -> float:
        return _RUN_BUDGET_SEC - (_time.monotonic() - _RUN_START)

    def _budget_ok(label: str = "") -> bool:
        remaining = _budget_remaining()
        if remaining <= 0:
            print(f"[GLOBAL TIMEOUT] 10分予算を超過しました。{label}をスキップして終了します。")
            return False
        return True

    # 0. accounts.pyで管理している取得対象アカウント(ジャンル不問)を読み込む
    accounts = list(ANTENNA_ACCOUNTS)
    if not accounts:
        print(f"{CATEGORY_ALL}: accounts.pyにアカウントが0件のため、この実行ではリール取得をスキップします")

    # 1. Instagram全体トレンドの投稿を取得(①全体トレンド+②美容ジャンルトレンドを
    #    1回の取得でまとめて行う。2026-07-02(item5): Bright Dataへの取得を増やさず、
    #    美容ジャンルアカウント由来の投稿だけを事後的にCATEGORY_BEAUTYへ再分類する)
    raw_posts, snapshot_meta, _bd_outage, _outage_reason = _fetch_raw_posts(
        CATEGORY_ALL, lambda: fetch_trend_posts(accounts)
    )

    # ── Bright Data 障害モード ─────────────────────────────────────────────
    if _bd_outage:
        if not fallback_mode:
            print()
            print("=" * 70)
            print("Instagramデータ取得失敗")
            print()
            print("  取得件数: 0")
            print("  Research Candidate: 0")
            print()
            print("  本日の投稿生成は中止しました。")
            print()
            print("  理由:")
            print("  Instagramの実データを取得できなかったため、")
            print("  トレンドに基づく投稿は生成しません。")
            print()
            print(f"  ({_outage_reason})")
            print()
            print("  Bright Dataの復旧後に再実行してください。")
            print("  ※ --fallback オプションを付けると取得なしで投稿生成できます。")
            print("=" * 70)
            _run_log_from_snapshot_meta(
                snapshot_meta=snapshot_meta,
                accounts=accounts,
                fetched_count=0,
                pool_count=0,
                post_generated=False,
                registered_count=len(list(ANTENNA_ACCOUNTS)),
            )
            sys.exit("NO_INSTAGRAM_DATA")

        # --fallback 指定時のみ Instagram根拠なしで Creator Studio を実行
        print()
        print("=" * 70)
        print("【--fallback モード】Bright Data 障害 — Instagram取得なしで続行します")
        print(_outage_reason)
        print("=" * 70)
        print()
        try:
            if _budget_ok("Creator Studio（fallbackモード）"):
                cs_result = generate_creator_studio_daily(instagram_fetched=0)
                if cs_result:
                    print_creator_studio_summary(cs_result)
        except Exception as e:
            print(f"Creator Studio（fallbackモード）実行中にエラーが発生しました: {e}")
        _run_log_from_snapshot_meta(
            snapshot_meta=snapshot_meta,
            accounts=accounts,
            fetched_count=0,
            pool_count=0,
            post_generated=False,
            registered_count=len(list(ANTENNA_ACCOUNTS)),
        )
        print()
        print("すべての処理が完了しました（--fallback モード）")
        sys.exit(0)

    apply_beauty_category(raw_posts, ANTENNA_ACCOUNTS_BEAUTY)

    # 2. 構造的に使える投稿だけをプールとして抜き出す
    #    (2026-06-30: 再生数・再生倍率による採用/不採用の二値フィルタは廃止した。
    #    詳細はbright_data_fetcher.build_post_poolのdocstring参照)
    result = build_post_pool(raw_posts)
    posts = result["pool"]
    _pool_stats = result["stats"]

    print(
        f"{CATEGORY_ALL}: 取得{_pool_stats['fetched']}件中"
        f"{_pool_stats['pool_count']}件をResearch Candidate Scoreの対象プールにしました"
    )

    # ── 除外理由集計ログ ─────────────────────────────────────────────────────
    _print_pool_exclusion_summary(_pool_stats, raw_posts, posts)

    # 2.5 フィルター前の取得投稿"全件"(除外理由付き)をraw_fetch_logシートに
    #     常時保存する(2026-06-30追加。build_post_poolがpost["pool_exclusion_
    #     reason"]を付与した直後に呼ぶ必要がある)
    try:
        save_raw_fetch_log(raw_posts)
        print("フィルター前の取得投稿全件をraw_fetch_logシートに保存しました(除外理由付き)")
    except Exception as e:
        print(f"raw_fetch_logシートへの保存中にエラーが発生しました: {e}")

    # 3. 取得済み投稿(フィルタ前の全件)から新しいアンテナアカウント候補を抽出し、
    #    複数のアンテナアカウントから言及されたものは人の承認なしに自動追加する
    _grow_antenna_accounts(raw_posts, accounts)

    if not posts:
        fetched_count = result["stats"].get("fetched", 0)
        pool_count = result["stats"].get("pool_count", 0)

        if fetched_count == 0:
            no_data_reason = "Bright Data取得0件（タイムアウト・API障害の可能性）"
        else:
            no_data_reason = f"取得{fetched_count}件だがフィルタ後0件（リール以外・投稿日が古いなど）"

        # スプレッドシートに0件ステータスを保存
        try:
            save_trend_analysis_no_data(reason=no_data_reason)
        except Exception as e:
            print(f"trend_analysis 0件ステータス保存中にエラーが発生しました: {e}")

        # snapshot_metaからrun_log用の情報を抽出
        _run_log_from_snapshot_meta(
            snapshot_meta=snapshot_meta,
            accounts=accounts,
            fetched_count=fetched_count,
            pool_count=0,
            post_generated=False,
            registered_count=len(list(ANTENNA_ACCOUNTS)),
        )
        _run_log_recovered(snapshot_meta)

        if fetched_count == 0 and not fallback_mode:
            # Research Candidate 0件 → 投稿生成を中止
            print()
            print("=" * 70)
            print("Instagramデータ取得失敗")
            print()
            print("  取得件数: 0")
            print("  Research Candidate: 0")
            print()
            print("  本日の投稿生成は中止しました。")
            print()
            print("  理由:")
            print("  Instagramの実データを取得できなかったため、")
            print("  トレンドに基づく投稿は生成しません。")
            print()
            print("  Bright Dataの復旧後に再実行してください。")
            print("  ※ --fallback オプションを付けると取得なしで投稿生成できます。")
            print("=" * 70)
            sys.exit("NO_INSTAGRAM_DATA")

        # fetched_count > 0 だがフィルタ後0件、または --fallback 指定時はそのまま続行
        print()
        print("=" * 60)
        if fetched_count == 0:
            print("【--fallback モード】Instagramデータ取得0件 — fallbackで続行します")
        else:
            print("【データ不足】フィルタ後にプール対象の投稿が0件のため、トレンド分析は実行できません")
            print(f"  取得: {fetched_count}件 → フィルタ後: 0件（リール以外・投稿日が古いなど）")
        print("=" * 60)
        print()

        print("===== 取得・プールログ =====")
        _print_stats(CATEGORY_ALL, result["stats"])
        phase1_result = {}
        try:
            phase1_result = generate_phase1_daily(instagram_fetched=fetched_count) or {}
            if phase1_result:
                print_phase1_summary(phase1_result)
        except Exception as e:
            print(f"Phase 1の実行中にエラーが発生しました: {e}")
        return

    # 4. プール対象の投稿をスプレッドシートに保存(構造的に使えない投稿は保存しない)
    try:
        save_adopted_posts(posts)
        print("プール対象の投稿をスプレッドシートに保存しました")
    except Exception as e:
        print(f"投稿データのシート保存中にエラーが発生しました: {e}")

    # 5. ランキングシートを作成
    try:
        save_rankings(posts)
        print("ランキングシートを保存しました")
    except Exception as e:
        print(f"ランキングシートの保存中にエラーが発生しました: {e}")

    # 6. プール対象の投稿全件(①全体トレンド+②美容ジャンルトレンドが混在した
    #    1つのプール)のResearch Candidate Scoreを計算・記録し、スコア上位件だけ
    #    個別AI分析する
    analysis_posts = []
    if _budget_ok("ステップ6: Research Candidate Score + AI個別分析"):
        analysis_posts = _score_and_analyze_posts(posts) or []
    else:
        print("ステップ6をスキップ: OpenAI個別分析なしでCreator Studioへ進みます")

    # 7. OpenAIに集約分析を依頼(2026-07-02(item5): ①と②はResearch Candidate
    #    Score・個別AI分析では統合プールとして扱うが、この集約分析
    #    (analyze_category_trend)だけはカテゴリごとに分けて実行する)
    if _budget_ok("ステップ7: カテゴリ集約分析"):
        _ap = analysis_posts if analysis_posts else posts
        posts_all = [p for p in _ap if p.get("category") == CATEGORY_ALL]
        posts_beauty = [p for p in _ap if p.get("category") == CATEGORY_BEAUTY]
        _analyze_and_save_trend(CATEGORY_ALL, posts_all)
        _analyze_and_save_trend(CATEGORY_BEAUTY, posts_beauty)
    else:
        print("ステップ7をスキップ: カテゴリ集約分析なしでCreator Studioへ進みます")

    # 8. 取得・除外・プール件数のログを表示
    print()
    print("===== 取得・プールログ =====")
    _print_stats(CATEGORY_ALL, result["stats"])

    # Phase 1: Topic Candidates まで生成してSTOP（投稿生成はPhase 2以降）
    _ig_fetched_today = _pool_stats.get("fetched", 0)
    try:
        phase1_result = generate_phase1_daily(instagram_fetched=_ig_fetched_today) or {}
        if phase1_result:
            print_phase1_summary(phase1_result)
    except Exception as e:
        print(f"Phase 1の実行中にエラーが発生しました: {e}")

    # 2026-07-18: 実行完了をrun_logシートに記録
    _run_log_from_snapshot_meta(
        snapshot_meta=snapshot_meta,
        accounts=accounts,
        fetched_count=result["stats"].get("fetched", 0),
        pool_count=result["stats"].get("pool_count", 0),
        post_generated=False,
        registered_count=len(list(ANTENNA_ACCOUNTS)),
    )
    _run_log_recovered(snapshot_meta)

    print()
    print("すべての処理が完了しました")


if __name__ == "__main__":
    import argparse as _argparse
    _parser = _argparse.ArgumentParser(add_help=False)
    _parser.add_argument("--thumbnail",   action="store_true", help="サムネイル分析モードで実行")
    _parser.add_argument("--test",        action="store_true", help="テストモード（3件のみ）")
    _parser.add_argument("--dry-run",     action="store_true", dest="dry_run",
                         help="APIを呼ばずプロンプトと保存先のみ表示")
    _parser.add_argument("--batch-size",  type=int, default=None, dest="batch_size",
                         help="1ジョブあたりのアカウント数を上書き (例: --batch-size 2)")
    _parser.add_argument("--fallback",       action="store_true",
                         help="Instagram取得0件でも投稿生成を続行する（通常は使用しない）")
    _parser.add_argument("--pending-status", action="store_true", dest="pending_status",
                         help="pending一覧をAPI確認して表示（投稿生成・新規triggerなし）")
    _parser.add_argument("--cleanup-stale",  action="store_true", dest="cleanup_stale",
                         help="6時間以上runningのsnapshotをarchiveへ移動（自動再triggerなし）")
    _parser.add_argument("--retry-stale",    action="store_true", dest="retry_stale",
                         help="6時間以上runningのsnapshotのみ明示的に再trigger")
    _args, _unknown = _parser.parse_known_args()

    # dry-run フラグを creator_studio と bright_data_fetcher へ伝達
    if _args.dry_run:
        import creator_studio as _cs
        _cs._DRY_RUN = True
        import bright_data_fetcher as _bdf
        _bdf.DRY_RUN = True

    # バッチサイズ上書き
    if _args.batch_size is not None:
        import bright_data_fetcher as _bdf2
        if 1 <= _args.batch_size <= 10:
            _bdf2.ACCOUNTS_PER_BATCH = _args.batch_size
            print(f"[設定] バッチサイズを {_args.batch_size} アカウント/ジョブ に変更しました")
        else:
            print(f"[警告] --batch-size は 1〜10 の範囲で指定してください（指定値: {_args.batch_size}）")

    # pending 系 CLI は投稿生成・AI分析を行わず単独実行
    if _args.pending_status:
        import bright_data_fetcher as _bdf_ps
        _bdf_ps.run_pending_status()
        import sys as _sys
        _sys.exit(0)

    if _args.cleanup_stale:
        import bright_data_fetcher as _bdf_cs
        _bdf_cs.run_cleanup_stale()
        import sys as _sys
        _sys.exit(0)

    if _args.retry_stale:
        import bright_data_fetcher as _bdf_rs
        _bdf_rs.RETRY_STALE = True
        _bdf_rs.run_retry_stale(dry_run=_args.dry_run)
        import sys as _sys
        _sys.exit(0)

    if _args.thumbnail:
        # ── サムネイル分析モード ──────────────────────────────────────────
        try:
            from thumbnail_analyzer import run_thumbnail_analysis, save_report
            from sheets_writer import save_thumbnail_analysis

            result = run_thumbnail_analysis(test_mode=_args.test)

            # シート保存
            if result["analyses"]:
                save_thumbnail_analysis(result["analyses"])

            # レポート保存
            if result["report_md"]:
                save_report(result["report_md"])
                print("\n" + "=" * 60)
                print(result["report_md"][:3000])
                if len(result["report_md"]) > 3000:
                    print("... （続きはレポートファイルを参照）")

            print(f"\n[完了] 分析: {result['analyzed']}件 / 失敗: {len(result['skipped_urls'])}件")
        except Exception as _e:
            import traceback
            print(f"サムネイル分析エラー: {_e}")
            traceback.print_exc()
    else:
        main(fallback_mode=_args.fallback)
