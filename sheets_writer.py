"""
sheets_writer.py
プール対象(構造的に使えるリール、bright_data_fetcher.build_post_pool)の
分析結果をGoogleスプレッドシートに保存するモジュール。

【2026-06-30: 「採用された投稿のみ保存する」という前提を変更】
旧版は採用条件を満たした投稿のみを保存していたが、bright_data_fetcher.py
の【2026-06-30】セクションで採用/不採用の二値フィルタを廃止したため、
reels/trend_postsシートに保存されるのは「構造的に分析対象として成立する
投稿(取得失敗・リール以外・投稿日超過を除く)全件」になった。さらに、
フィルター前の生データ(除外された投稿も含む全件)をraw_fetch_logシートに
常時保存するようにした(下記参照)。

【2026-07-05: Trend Score → Research Candidate Scoreへのリネーム】
ユーザー要望「Trend Scoreを廃止してください。代わりにResearch Candidate Score
を追加してください」に対応し、trend_score.py → research_candidate_score.py、
trend_postsシート → research_candidatesシート、trend_score_debugシート →
research_candidate_score_debugシートにリネームした(採点項目・配点は変更
していない。詳細はresearch_candidate_score.pyのdocstring参照)。
【注意】旧trend_posts/trend_score_debugタブは過去の実行データとしてシート自体は
残るが、これ以降の実行では書き込まれない(_get_or_create_worksheetはシート名が
無ければ新規作成する仕様のため、新しいシート名research_candidates/research_
candidate_score_debugが新規タブとして作成される)。

1つのスプレッドシート(GOOGLE_SHEET_ID)の中に、以下のシート(タブ)を
必要に応じて自動作成する。

- raw_fetch_log               : フィルター(プール選別)前の取得投稿"全件"を、
                                URL・投稿日・再生数・いいね数・フォロワー数・
                                再生倍率・除外理由付きで記録する(2026-06-30
                                追加)。「再生数で25件除外・採用0件」のような
                                事態が起きた際に、何件中何件がどの理由で外れた
                                のかを確認するためのデバッグ用ログ。
- reels                      : Instagram全体トレンドでプール対象になったリールの分析項目
- trend_analysis             : AI集約分析結果(実行ごとに1行)
- research_candidates        : 採用された投稿"全件"について、Research Candidate
                                Score(0〜100点、research_candidate_score.py)の
                                合計・項目別得点・判定(必ず分析/投稿案候補/
                                保存のみ)を記録する透明性ログ(2026-06-29(5回目)
                                追加、2026-07-05にtrend_postsからリネーム)
- research_candidate_score_debug : research_candidatesと同じ投稿全件について、
                                各評価項目の生値(再生数・フォロワー数・再生倍率・
                                いいね数/率・コメント数/率・投稿日・動画尺・
                                投稿頻度)と得点をセットで記録する(2026-07-01
                                追加、2026-07-05にtrend_score_debugからリネーム)。
                                配点しきい値を調整するためのデバッグ用シート
                                (下記参照)。
- post_analysis               : Research Candidate Scoreが80点以上(必ず分析+
                                投稿案候補)の投稿について、なぜ伸びたか・冒頭フック・
                                構成・テロップの型・CTA・CORE HARI FACEへの応用方法
                                などの「分析」結果のみを保存する(2026-06-29(5回目):
                                投稿案そのものはcore_hari_ideasシートに分離した)
- core_hari_ideas             : post_analysisと同じ対象投稿について、実際にCORE HARI
                                FACEで使える投稿案(30秒版/60秒版/Threads版・タイトル案・
                                冒頭フック案)を保存する(2026-06-29(5回目)追加)
- success_factors             : post_analysisと同じ対象投稿について、Research
                                Candidate Score(数値配点)とは別のAI分析
                                「成功要因分析」(なぜ伸びたか・
                                冒頭3秒のフック・構成・CTA・心理トリガー・CORE HARI FACE
                                への応用方法)を保存する(2026-07-01(2回目)追加。
                                post_analysisと内容は一部重複するが、置き換えではなく
                                新規の独立した分析として追加した)
- content_carousel            : success_factorsと同じ対象投稿について、匿名ブランド
                                「SNS Pattern Lab」として発信できるInstagramカルーセル
                                投稿案(10枚分)を保存する(2026-07-01(3回目)追加)
- content_reels               : 同じ対象投稿について、SNS Pattern Lab用のリール台本
                                (冒頭3秒・本文・テロップ・ナレーション・CTA)を保存する
                                (2026-07-01(3回目)追加)
- content_threads             : 同じ対象投稿について、SNS Pattern Lab用のThreads投稿案
                                (短文3本+やや詳しい解説1本)を保存する(2026-07-01(3回目)追加)
- content_caption             : 同じ対象投稿について、SNS Pattern Lab用のキャプション
                                (Instagram用・サブスク誘導用)を保存する(2026-07-01(3回目)追加)
- Instagram全体トレンドTOP20 : プール対象のリールを再生数順にランキング
- 再生倍率TOP20              : プール対象のリールを再生倍率(再生数÷フォロワー数)順にランキング
- 伸び率TOP20                : プール対象のリールを伸び率(日次再生数÷フォロワー数)順にランキング
                                (2026-06-29(4回目)追加。2026-06-30以降はbuild_post_pool
                                自体は並び順を決めず、Research Candidate Score順位がそれに代わった)
- 保存率TOP20                : 保存数が取得できたプール対象リールを保存率順にランキング
                                (保存数が1件も取得できなかった場合はシート自体を作成しない)
- auto_added_accounts        : 複数のアンテナアカウントからの言及により自動追加された
                                アカウントの履歴ログ(人の操作は不要。記録のみ)
- account_mention_tracker     : しきい値未満の候補アカウントの、複数実行をまたいだ
                                累積言及元アカウント数を保持するワーキングシート
                                (しきい値に達すると自動追加され、この表からは削除される)
- north_star_daily            : North Star Daily Generator(2026-07-04再設計。
                                旧Creator Intelligence Sprint 1 Task Aの9項目を
                                置き換え)。その日分析した投稿群を横断的に要約した
                                North Star Dailyレポート(今日最も注目すべき投稿
                                TOP3・共通する成功要因・伸びた理由(AI分析)・
                                使われている心理テクニック・美容以外へ応用する
                                方法・今日のInstagram投稿案・Threads投稿案・
                                参考記事一覧・Creator Intelligenceコメント(今日の
                                学び))を、実行(=1日)ごとに1行保存する。
                                【注意】2026-07-03時点で旧9項目のヘッダー行を
                                すでに書き込んだシートが存在する場合、
                                _get_or_create_worksheetはヘッダーが「無ければ」
                                作成する仕様のため、古いヘッダー行は自動更新
                                されない。新ヘッダーで運用するには、その
                                north_star_dailyシートのヘッダー行(1行目)を
                                ユーザーが手動で一度クリアする必要がある。
- knowledge_library / success_patterns / psychology_patterns / hook_library /
  cta_library / research_sources : Creator Intelligence Sprint 1 Task B
                                (2026-07-03追加)。雛形(タブ+ヘッダー行)のみ。
                                自動データ投入は次のスプリント以降で判断する。

- シート(タブ)が無ければ自動作成する
- ヘッダーが無ければ自動作成する
- 既存ヘッダーがあれば末尾に追記する

【2026-06-29: 美容ジャンル/Instagram全体トレンドの2カテゴリを統合】
従来あった beauty_reels / general_reels / 美容ジャンルTOP20 シートは、
過去の実行データとして残るが、これ以降の実行では作成しない
(reels / Instagram全体トレンドTOP20 に一本化した)。

【2026-06-29: 候補アカウントの人による採用/除外判断を廃止】
従来のcandidate_accountsシート(採用ステータス列にユーザーが「採用」「除外」を
手入力し、sync_adopted_accounts.pyで取り込む半自動フロー)は廃止した。
過去の実行データとしてシート自体は残る場合があるが、これ以降の実行では
書き込まない。代わりに、auto_added_accounts(ログ)とaccount_mention_tracker
(累積カウント用ワーキングシート)を使い、人の判断なしに自動でANTENNA_ACCOUNTS
が拡張される。

【2026-06-29: 投稿単位(個別)の分析を追加】
採用された上位5件(再生数順、現在は伸び率順)について、投稿ごとに個別のAI分析・
投稿案生成を行い、post_analysisシートに保存する。集約分析(trend_analysis)は
別途維持する。

【2026-06-29(4回目): 伸び率(日次再生数÷フォロワー数)の列・ランキングを追加】
ユーザーの要望「再生数・投稿日時・フォロワー数から伸び率を評価する」に対応し、
reels/post_analysisシートに「日次再生数」「伸び率」列を追加し、新たに
伸び率TOP20シートを追加した。

【2026-06-29(5回目): Trend Score・trend_posts・core_hari_ideasを追加】
ユーザーの要望「投稿単位の評価とCORE HARI FACE向け投稿案への変換」に対応し、
以下を変更した。
- trend_postsシートを新規追加。採用された投稿"全件"について、trend_score.py
  が計算したTrend Score(合計・7項目の内訳・判定)を記録する。AI分析するかどうか
  に関わらず全件を記録するため、「なぜこの投稿はAI分析されなかったのか」を後から
  確認できる透明性ログになる。
- post_analysisシートの保存対象を「上位5件(伸び率順)固定」から「Trend Scoreが
  80点以上(必ず分析+投稿案候補)の投稿」に変更した(main.py参照)。
- core_hari_ideasシートを新規追加。post_analysisと同じ対象投稿について、
  実際の投稿案を保存する。post_analysis(なぜ伸びたかの分析)とcore_hari_ideas
  (実際に使える投稿案)を分けることで、「分析結果」と「そのまま使える素材」を
  別シートで管理できる。

【2026-06-29(6回目): post_analysis/core_hari_ideasの保存項目を3段階パイプラインに合わせて更新】
ユーザーが投稿単位のAI分析を3段階(②構造分析→③CORE HARI FACE変換→④投稿案
生成)に再設計した(prompts.py・openai_analyzer.pyのdocstring参照)ことに伴い、
以下を変更した。
- post_analysisシートの保存項目を、prompts.POST_ANALYSIS_TEXT_KEYS(13項目、
  ②analyze_post_structureの全出力)に揃えた。以前は6項目に絞っていたが、
  ユーザーが「伸びた理由」を多面的に分析するよう明示的に要望したため、
  分析結果は絞らず全項目を保存する。
- core_hari_ideasシートの保存項目を、prompts.CORE_HARI_IDEA_TEXT_KEYS(7項目、
  ④generate_core_hari_ideaの全出力。タイトル・30秒版リール・60秒版リール・
  Threads投稿・キャプション・CTA・投稿カテゴリ)に揃えた。すべて単数の文字列
  項目になったため、旧バージョンにあった配列項目(タイトル案5個など)の
  改行展開ロジックは不要になった。
- save_post_analyses/save_core_hari_idesが受け取るentriesの形式を
  {"post":..., "analysis":..., "idea":...} に変更した(②と③+④が別々のAI
  呼び出し・別々の戻り値になったため、1つの"analysis"キーで両方を表現できなく
  なった)。

【2026-07-01: Sheets書き込みの一括化(429エラー対策) + trend_score_debug追加】
1. 実運用でGoogle Sheets APIの書き込みリクエスト数上限を超えて429エラーが
   発生した。原因は、本ファイルの保存関数がすべて「投稿1件ごとにappend_row
   (=1件1リクエスト)」をループしていたことで、取得件数が増えるほど
   リクエスト数が線形に増加していた(例: 25件取得時、reels・raw_fetch_log・
   trend_posts・4種のランキングシートだけで100件以上のリクエストになり得る)。
   対応として、すべての保存関数を「1回のappend_rows(複数行を1リクエストで
   追記)」に変更した。upsert_mention_tracker()のみ、既存行の更新(個別の
   worksheet.update)が混在していたため、新規行はappend_rows・既存行の更新は
   batch_update(複数range更新を1リクエストにまとめるgspreadのAPI)に分けて
   それぞれ1回のリクエストに統一した。
2. ユーザーから「25件取得したのにTrend Score80点以上が0件だった。配点を
   確認するため、各投稿の項目別の生値と得点をシートに出力してほしい」との
   要望があり、trend_score_debugシートとsave_trend_score_debug()を新設した。
   trend_postsシートには得点(点数のみ)しかなく、「何回再生されていたから
   何点になったのか」を確認できなかったため、生値と得点をセットで並べる
   構成にした(詳細はsave_trend_score_debugのdocstring・TREND_SCORE_DEBUG_
   HEADERS参照)。

【2026-07-01(2回目): success_factorsシートを追加】
ユーザーから「Trend Score(数値配点)とは別に、AIによる成功要因分析を追加したい。
なぜ伸びたか・冒頭3秒のフック・構成・CTA・心理トリガー・CORE HARI FACEへの
応用方法を出力できるようにしてほしい」との要望があった。既存のpost_analysis
(analyze_post_structureの13項目)と内容が重複する部分があったため、置き換える
か新規追加するかをユーザーに確認したところ「既存は維持し、新しい分析として
追加する」ことを選んだ。そのため、save_success_factors()・success_factors
シート・SUCCESS_FACTOR_HEADERSを新設した(既存のpost_analysis/core_hari_ideas
は変更していない)。

【2026-07-01(3回目): content_carousel/content_reels/content_threads/content_caption
シートを追加(SNS Pattern Lab投稿素材生成)】
ユーザーから「分析結果から、顔出し不要の匿名ブランド『SNS Pattern Lab』として
発信できる投稿素材を自動生成したい」との要望があった。
openai_analyzer.generate_pattern_lab_content(success_factorsの結果を入力に、
カルーセル10枚+リール台本5項目+Threads4項目+キャプション2項目の計21項目を
1回のOpenAI呼び出しで生成)の出力を、出力タイプごとに4つの別シートに分けて
保存する(1シートに21列まとめると見づらいため。詳細はprompts.pyのPATTERN_LAB_*
のdocstring参照)。対象は成功要因分析と同じ投稿全件(個別分析対象、最大10件)。

【2026-07-03: Creator Intelligence Sprint 1(Task B)— north_star_daily +
6つのライブラリ系シート(雛形)を追加】
ユーザー要望「スプレッドシートにnorth_star_daily, knowledge_library,
success_patterns, psychology_patterns, hook_library, cta_library,
research_sourcesを追加してほしい」に対応する。AskUserQuestionで確認した結果、
6つのライブラリ系シートは2026-07-03時点では「雛形(タブ+ヘッダー行のみ)を
作成」にとどめ、自動でデータを書き込むロジックは次のスプリント以降に判断する
ことが確定した。そのため:
- north_star_daily: openai_analyzer.generate_north_star_dailyの結果を、実行ごとに
  1行保存する(save_north_star_daily、Task A参照)。
- knowledge_library/success_patterns/psychology_patterns/hook_library/
  cta_library/research_sources: ensure_creator_intelligence_library_sheets()が
  起動時に毎回呼ばれ、タブとヘッダー行が無ければ作成するだけ(データ行は
  書き込まない)。各シートの列構成はユーザー指定ではなく、私の判断による
  プレースホルダー設計(*_LIBRARY_HEADERS定義の直前コメント参照)。

【2026-07-04: North Star Daily Generatorの出力9項目を再設計(旧9項目を置き換え)】
ユーザー要望によりprompts.NORTH_STAR_DAILY_TEXT_KEYSの内容自体が変わった
(詳細はprompts.pyのdocstring2026-07-04の項目参照)。NORTH_STAR_DAILY_HEADERSは
そのキー一覧を動的に参照しているだけなので、sheets_writer.py側のコード変更は
不要(["実行日時", "対象投稿数"] + NORTH_STAR_DAILY_TEXT_KEYS という構造は
変わらない)。ただし、2026-07-03時点の旧9項目でヘッダー行を書き込んだ
north_star_dailyシートが既に存在する場合は、_get_or_create_worksheetの
「ヘッダーが無ければ作成する」仕様により古いヘッダーは自動更新されない
(north_star_dailyシートの説明コメント参照)。

【2026-07-04(4回目): Creator Intelligence Sprint 2(Task3+4)—
knowledge_libraryを「単なる雛形」から「重複排除型のナレッジDB」に強化】
ユーザー要望「knowledge_libraryを会社の知識DBとして強化してほしい。項目は
成功パターン/心理トリガー/CTAパターン/フック/再利用可能な構成/参考記事/
参考URL/信頼度/初回発見日/最後に確認した日/使用回数/実績。知識が重複しない
設計を希望する」「同じ成功要因は重複登録しないでください(Task4)」に対応する。

1. KNOWLEDGE_LIBRARY_HEADERSを、旧6列(登録日時/カテゴリ/タイトル/内容/
   出典投稿URL/タグ。Sprint 1 Task Bでの私の判断によるプレースホルダー)から、
   ユーザー指定の12列に全面差し替えた。【注意】2026-07-03時点で旧6列のヘッダー
   行を既に書き込んだknowledge_libraryシートが存在する場合、_get_or_create_
   worksheetの「ヘッダーが無ければ作成する」仕様により古いヘッダーは自動更新
   されない。新ヘッダーで運用するには、knowledge_libraryシートのヘッダー行
   (1行目)をユーザーが手動で一度クリアする必要がある(north_star_dailyの
   既存の注意書きと同じ事情)。
2. 重複排除(Task3「知識が重複しない設計」・Task4「同じ成功要因は重複登録
   しない」)は、新規ファイルknowledge_registry.pyが担当する(列の読み書きの
   基盤だけを本ファイルに用意する)。本ファイルにはget_knowledge_library_rows
   (既存データ行を{"row":行番号, "values":{列名:値}}の形で読み込む)・
   append_knowledge_library_row(新規パターンを1行追記する)・update_knowledge_
   library_row(既存パターンの行を更新する)の3関数のみを追加した。「どの
   パターンが既に登録済みか」の判定ロジック自体(成功パターン名の組み立て・
   一致判定)はknowledge_registry.py側に置き、sheets_writer.pyはあくまで
   Google Sheetsへの読み書きのみを担当する設計にした(将来、保存先がSheets
   以外(DB等)に変わっても、knowledge_registry.py側のロジックは変更不要にする
   ため)。
3. research_sourcesシートについても、Sprint 1 Task Bでは雛形のみ(自動投入
   ロジックなし)だったが、Sprint 2 Task1のresearch_engine.gather_evidence_
   for_postが「投稿自体の実測値」という、常に実在する(ハルシネーションの
   リスクがない)根拠データを返すようになったため、save_research_sources()を
   新設して実データを投入するようにした。
"""

import datetime
import json
import os

import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials

from config import GOOGLE_SHEET_ID, GOOGLE_SERVICE_ACCOUNT_JSON
from prompts import (
    CATEGORY_ANALYSIS_TEXT_KEYS,
    CATEGORY_ANALYSIS_LIST_KEYS,
    POST_ANALYSIS_TEXT_KEYS,
    CORE_HARI_IDEA_TEXT_KEYS,
    SUCCESS_FACTOR_TEXT_KEYS,
    PATTERN_LAB_CAROUSEL_KEYS,
    PATTERN_LAB_REEL_KEYS,
    PATTERN_LAB_THREADS_KEYS,
    PATTERN_LAB_CAPTION_KEYS,
    NORTH_STAR_DAILY_TEXT_KEYS,
)
from research_candidate_score import BREAKDOWN_KEYS as RESEARCH_CANDIDATE_SCORE_BREAKDOWN_KEYS
from research_engine import gather_evidence_for_post

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_RAW_FETCH_LOG = "raw_fetch_log"
SHEET_REELS = "reels"
SHEET_TREND_ANALYSIS = "trend_analysis"
# 2026-07-02追加(item7): 旧trend_analysis(カテゴリ単位の集計、実行ごとに1行)を
# この名前に退避した。SHEET_TREND_ANALYSIS("trend_analysis")自体は投稿ごとの
# 形式に再設計した(save_trend_analysis/save_category_trend_summaryのdocstring参照)。
SHEET_CATEGORY_TREND_SUMMARY = "trend_analysis_summary"
SHEET_DAILY_CONTENT_PICKS = "daily_content_picks"
SHEET_CREATOR_STUDIO_DAILY = "creator_studio_daily"  # 2026-07-01 Creator Studio MVP
SHEET_RESEARCH_CANDIDATES = "research_candidates"
SHEET_RESEARCH_CANDIDATE_SCORE_DEBUG = "research_candidate_score_debug"
SHEET_POST_ANALYSIS = "post_analysis"
SHEET_CORE_HARI_IDEAS = "core_hari_ideas"
SHEET_SUCCESS_FACTORS = "success_factors"
SHEET_CONTENT_CAROUSEL = "content_carousel"
SHEET_CONTENT_REELS = "content_reels"
SHEET_CONTENT_THREADS = "content_threads"
SHEET_CONTENT_CAPTION = "content_caption"
SHEET_RANK_ALL = "Instagram全体トレンドTOP20"
SHEET_RANK_MULTIPLIER = "再生倍率TOP20"
SHEET_RANK_GROWTH = "伸び率TOP20"
SHEET_RANK_SAVE_RATE = "保存率TOP20"
SHEET_AUTO_ADDED_ACCOUNTS = "auto_added_accounts"
SHEET_ACCOUNT_MENTION_TRACKER = "account_mention_tracker"

# Creator Intelligence Sprint 1(2026-07-03追加)
SHEET_NORTH_STAR_DAILY = "north_star_daily"
SHEET_KNOWLEDGE_LIBRARY = "knowledge_library"
SHEET_SUCCESS_PATTERNS = "success_patterns"
SHEET_PSYCHOLOGY_PATTERNS = "psychology_patterns"
SHEET_HOOK_LIBRARY = "hook_library"
SHEET_CTA_LIBRARY = "cta_library"
SHEET_RESEARCH_SOURCES = "research_sources"
# 2026-07-01: Learning Engine — KnowledgeUnitの永続化シート
SHEET_KNOWLEDGE_UNITS = "knowledge_units"
# 2026-07-01: フィードバックループ — CORE HARIの実投稿結果を手入力するシート
SHEET_MANUAL_POST_RESULTS = "manual_post_results"
# 2026-07-01(Sprint3): Evidence Layer
SHEET_EVIDENCE_REGISTRY = "evidence_registry"
SHEET_EVIDENCE_LINKS = "evidence_links"
# 2026-07-01: CORE HARI専門知識DB（Creator Studioがコンテンツを生成する唯一の知識源）
SHEET_CORE_HARI_KB = "core_hari_kb"
# 2026-07-02(10回目): Thought Library — 考え方・話し方・例え話のデータベース
SHEET_THOUGHT_LIBRARY = "thought_library"

RANK_TOP_N = 20

# raw_fetch_logシートのヘッダー(2026-06-30追加)。
# bright_data_fetcher.build_post_poolが付与するpost["pool_exclusion_reason"]
# (空文字列なら除外なし=プール入り)をそのまま「除外理由」列に書き出す。
RAW_FETCH_LOG_HEADERS = [
    "実行日時",
    "投稿者",
    "投稿URL",
    "投稿日",
    "再生数",
    "いいね数",
    "フォロワー数",
    "再生倍率",
    "除外理由",
]

# 投稿1件あたりの分析項目(実行日時を除く)
POST_COLUMNS = [
    "投稿URL",
    "投稿日",
    "再生数",
    "いいね数",
    "コメント数",
    "保存数",
    "シェア数",
    "フォロワー数",
    "再生倍率",
    "日次再生数",
    "伸び率(日次再生数÷フォロワー数)",
    "動画尺(秒)",
    "キャプション全文",
    "使用ハッシュタグ",
    "投稿ジャンル",
]

REEL_SHEET_HEADERS = ["実行日時"] + POST_COLUMNS
RANK_SHEET_HEADERS = ["実行日時", "順位"] + POST_COLUMNS

# 2026-07-02改名(item7): 旧TREND_ANALYSIS_HEADERS。trend_analysis_summary
# シート(カテゴリ単位の集計、実行ごとに1行)用のヘッダー。
CATEGORY_TREND_SUMMARY_HEADERS = (
    ["実行日時", "対象カテゴリ", "分析対象投稿数"]
    + CATEGORY_ANALYSIS_TEXT_KEYS
    + CATEGORY_ANALYSIS_LIST_KEYS
)

# 2026-07-02新設(item7): trend_analysisシート(投稿ごと、1投稿1行)用のヘッダー。
# SUCCESS_FACTOR_FIELDS定義より後でしか使えないため、本リストの実体は
# SUCCESS_FACTOR_FIELDS定義の直後で組み立てる(TREND_ANALYSIS_HEADERS参照)。

# daily_content_picksシート(item4: 毎日「30秒リール1本・60秒リール1本・
# Threads投稿1本」を保存する)のヘッダー。
DAILY_CONTENT_PICKS_HEADERS = [
    "実行日時",
    "投稿タイプ",
    "投稿カテゴリ",
    "投稿URL",
    "投稿者",
    "Research Candidate Score",
    "タイトル",
    "本文",
    "キャプション",
    "CTA",
]

# creator_studio_daily シートのヘッダー (2026-07-01 Creator Studio MVP)
CREATOR_STUDIO_DAILY_HEADERS = [
    "date",
    "source_type",
    "source_url",
    "today_mission",
    "theme",
    "video_title",       # 2026-07-01(3回目): そのまま使える動画タイトル
    "why_today",
    "target",
    "hook",
    "script_15_30s",     # 後方互換のため残す（= script_full の要約版）
    "script_full",       # 2026-07-01(3回目): 読み上げ用セリフ全文
    "shot_sequence",     # 2026-07-01(3回目): 番号付き具体的撮影順序
    "shooting_location",
    "shooting_cuts",     # 後方互換のため残す（= shot_sequence の要約版）
    "b_roll",
    "editing_notes",     # 2026-07-01(3回目): 今日の具体的編集メモ（旧4フィールド統合）
    "cta",
    "caption",
    "threads_text",
    "brand_score",
    "brand_notes",
    "feedback_url_placeholder",
]

RESEARCH_CANDIDATES_HEADERS = (
    ["実行日時"]
    + POST_COLUMNS
    + ["Research Candidate Score合計"]
    + RESEARCH_CANDIDATE_SCORE_BREAKDOWN_KEYS
    + ["判定"]
)

# research_candidate_score_debugシートのヘッダー(2026-07-01追加。2026-07-05に
# trend_score_debugからリネーム)。
# research_candidatesシートには得点の内訳(点数のみ)しか出ないため、「なぜこの
# 点数になったか」を確認できるよう、各評価項目の生値と得点をセットで並べる
# (生値の列名には_点を付けず、得点の列名には末尾に_点を付けて区別する)。
RESEARCH_CANDIDATE_SCORE_DEBUG_HEADERS = [
    "実行日時", "投稿URL", "投稿者", "Research Candidate Score合計", "判定",
    "再生数", "再生数_点",
    "フォロワー数",
    "再生倍率", "再生倍率_点",
    "いいね数", "いいね率", "いいね率_点",
    "コメント数", "コメント率", "コメント率_点",
    "投稿日", "投稿からの日数_点",
    "動画尺(秒)", "動画時間_点",
    "投稿頻度(取得窓内の同アカウント投稿数)", "投稿頻度_点",
]

# post_analysisシートには、②analyze_post_structureの全出力(13項目、
# prompts.POST_ANALYSIS_TEXT_KEYS)をそのまま保存する(2026-06-29(6回目))。
POST_ANALYSIS_FIELDS = list(POST_ANALYSIS_TEXT_KEYS)

POST_ANALYSIS_HEADERS = (
    [
        "実行日時", "投稿URL", "投稿者", "再生数", "再生倍率",
        "伸び率(日次再生数÷フォロワー数)", "Research Candidate Score", "判定",
    ]
    + POST_ANALYSIS_FIELDS
)

# core_hari_ideasシートには、④generate_core_hari_ideaの全出力(7項目、
# prompts.CORE_HARI_IDEA_TEXT_KEYS)をそのまま保存する(2026-06-29(6回目))。
# すべて単数の文字列項目のため、配列項目の改行展開は不要になった。
CORE_HARI_IDEAS_TEXT_FIELDS = list(CORE_HARI_IDEA_TEXT_KEYS)

CORE_HARI_IDEAS_HEADERS = (
    ["実行日時", "投稿URL", "投稿者", "Research Candidate Score", "判定"]
    + CORE_HARI_IDEAS_TEXT_FIELDS
)

# success_factorsシートには、openai_analyzer.analyze_success_factorsの全出力
# (6項目、prompts.SUCCESS_FACTOR_TEXT_KEYS)をそのまま保存する(2026-07-01(2回目)
# 追加)。Trend Score(数値配点)とは別の、AIによる質的な「成功要因分析」。
SUCCESS_FACTOR_FIELDS = list(SUCCESS_FACTOR_TEXT_KEYS)

SUCCESS_FACTOR_HEADERS = (
    ["実行日時", "投稿URL", "投稿者", "Research Candidate Score", "判定"]
    + SUCCESS_FACTOR_FIELDS
)

# 2026-07-02新設(item7): trend_analysisシート(投稿ごと、1投稿1行)のヘッダー。
# 「カテゴリ」(Instagram全体トレンド/美容ジャンルトレンド。item5対応)を含む点が
# success_factorsシートとの唯一の構造的な違い(値の出どころは同じentries)。
TREND_ANALYSIS_HEADERS = (
    ["実行日時", "カテゴリ", "投稿URL", "投稿者", "Research Candidate Score", "判定"]
    + SUCCESS_FACTOR_FIELDS
)

# content_carousel/content_reels/content_threads/content_captionシートには、
# openai_analyzer.generate_pattern_lab_contentの出力(計21項目)を、出力タイプ
# ごとに4分割して保存する(2026-07-01(3回目)追加。詳細はprompts.pyの
# PATTERN_LAB_*のdocstring参照)。
CONTENT_CAROUSEL_FIELDS = list(PATTERN_LAB_CAROUSEL_KEYS)
CONTENT_REELS_FIELDS = list(PATTERN_LAB_REEL_KEYS)
CONTENT_THREADS_FIELDS = list(PATTERN_LAB_THREADS_KEYS)
CONTENT_CAPTION_FIELDS = list(PATTERN_LAB_CAPTION_KEYS)

CONTENT_CAROUSEL_HEADERS = (
    ["実行日時", "投稿URL", "投稿者", "Research Candidate Score", "判定"] + CONTENT_CAROUSEL_FIELDS
)
CONTENT_REELS_HEADERS = (
    ["実行日時", "投稿URL", "投稿者", "Research Candidate Score", "判定"] + CONTENT_REELS_FIELDS
)
CONTENT_THREADS_HEADERS = (
    ["実行日時", "投稿URL", "投稿者", "Research Candidate Score", "判定"] + CONTENT_THREADS_FIELDS
)
CONTENT_CAPTION_HEADERS = (
    ["実行日時", "投稿URL", "投稿者", "Research Candidate Score", "判定"] + CONTENT_CAPTION_FIELDS
)

# north_star_dailyシートのヘッダー(Creator Intelligence Sprint 1 Task A、
# 2026-07-03追加)。投稿1件ごとではなく実行(=1日)ごとに1行保存する
# (AskUserQuestionで確認した「1日1件」方針。save_north_star_daily参照)。
NORTH_STAR_DAILY_HEADERS = (
    ["実行日時", "対象投稿数"] + NORTH_STAR_DAILY_TEXT_KEYS
)

# 以下6シート(knowledge_library/success_patterns/psychology_patterns/
# hook_library/cta_library/research_sources)は、Creator Intelligence
# Sprint 1 Task B(2026-07-03追加)。ユーザーの指示は「これらのシートを
# 追加する」ことのみで、列構成までは指定されていない。AskUserQuestionで
# 確認した結果、Sprint 1では雛形(タブ+ヘッダー行のみ)を作成するだけで
# データの自動投入は行わないことが確定したため、各シートの列は将来の
# 自動投入ロジック設計を見据えた私の判断によるプレースホルダーである
# (ユーザー指定ではない。次のスプリントで実際の自動投入ロジックを設計する際に
# 見直してよい)。共通して「登録日時」「出典投稿URL」を持たせ、後から
# どの投稿/分析が元になったかを追跡できるようにしている。
#
# 【2026-07-04(4回目)】knowledge_libraryのみ、Sprint 2 Task3でユーザー指定の
# 12列に全面差し替えた(下記KNOWLEDGE_LIBRARY_HEADERS参照。もはや私の判断による
# プレースホルダーではない)。残り5シート(success_patterns/psychology_patterns/
# hook_library/cta_library/research_sources)は列構成自体は変更していないが、
# research_sourcesのみ自動データ投入が始まった(save_research_sources参照。
# 他4シートは引き続き雛形のみ)。
KNOWLEDGE_LIBRARY_HEADERS = [
    "成功パターン",
    "心理トリガー",
    "CTAパターン",
    "フック",
    "再利用可能な構成",
    "参考記事",
    "参考URL",
    "信頼度",
    "初回発見日",
    "最後に確認した日",
    "使用回数",
    "実績",
]
SUCCESS_PATTERNS_HEADERS = ["登録日時", "パターン名", "説明", "適用ジャンル", "出典投稿URL", "タグ"]
PSYCHOLOGY_PATTERNS_HEADERS = ["登録日時", "心理トリガー名", "説明", "使用例", "出典投稿URL", "タグ"]
HOOK_LIBRARY_HEADERS = ["登録日時", "フック文", "型", "使用例", "出典投稿URL", "タグ"]
CTA_LIBRARY_HEADERS = ["登録日時", "CTA文", "型", "使用例", "出典投稿URL", "タグ"]
RESEARCH_SOURCES_HEADERS = ["登録日時", "出典名", "URL", "概要", "取得日", "タグ"]

# 2026-07-01: フィードバックループ — CORE HARIの実投稿結果手入力シート(13列)
# ユーザーが毎回手入力する。viewed_at / checked_at 以外は投稿直後に入力し、
# checked_at は30日後などに成果を確認してから入力する運用を想定。
# result_status は "success" / "partial" / "none" の3値で評価する。
#   success : フォロワー増・保存多数・予約につながった等、明確な成果あり
#   partial : 再生数は伸びたが直接的な集客成果は不明
#   none    : 反応が薄く成果なし
MANUAL_POST_RESULTS_HEADERS = [
    "posted_url",       # 実際に投稿したInstagram/Threads等のURL
    "posted_at",        # 投稿日(YYYY-MM-DD)
    "source_idea_id",   # 参考にしたcore_hari_ideasのID or タイトル(任意)
    "source_pattern_id",# 参照したknowledge_unitsのunit_id(例: Hook:問題提示型)
    "platform",         # Instagram / Threads / TikTok 等
    "notes",            # 自由メモ(工夫点・変更点など)
    "checked_at",       # 成果を確認した日(YYYY-MM-DD)。空欄=未確認
    "views",            # 再生数(数値)
    "likes",            # いいね数(数値)
    "comments",         # コメント数(数値)
    "saves",            # 保存数(数値)
    "follows_delta",    # この投稿後のフォロワー増減(数値、増加=正)
    "result_status",    # success / partial / none(空欄=未評価)
]

# 2026-07-01: Learning Engine — KnowledgeUnitスキーマ(13列)
# unit_id = "dimension:pattern_name" で一意性を保つ。
# confidence / evidence_count / reproduced_count / success_rate / last_seen_at が
# Confidence Scoreの5フィールド。success_rateはフィードバックループ実装まで0.0固定。
KNOWLEDGE_UNITS_HEADERS = [
    "unit_id",          # "Hook:問題提示型冒頭" などの一意キー
    "dimension",        # Hook / Structure / Psychology / Visual / CTA
    "pattern_name",     # 短い正規化パターン名(重複判定キー)
    "description",      # AIが生成した説明テキスト(最大200字)
    "status",           # BORN / VALIDATED / ACTIVE / STALE / EVOLVED
    "version",          # 1始まり、EVOLVEDで増加
    "confidence",       # 0.0〜1.0 (Confidence Score)
    "evidence_count",   # このパターンを確認できた投稿数
    "reproduced_count", # CORE HARIの投稿案に使われた回数(フィードバックループ実装後に増加)
    "success_rate",     # 0.0〜1.0(フィードバックループ実装まで0.0固定)
    "last_seen_at",     # 最終確認日(YYYY-MM-DD)
    "first_seen_at",    # 初回発見日(YYYY-MM-DD)
    "evidence_urls",    # カンマ区切りの出典投稿URLリスト(最大10件)
]

# 2026-07-01(Sprint3): Evidence Layer ヘッダー
EVIDENCE_REGISTRY_HEADERS = [
    "evidence_id",       # hash(type:url) or hash(type:url:observed_at) の先頭10文字
    "evidence_type",     # instagram_post / comment_signal / core_hari_result / article / etc.
    "source_url",        # 出典URL(投稿URL等)
    "source_title",      # 出典タイトル(投稿者名・記事タイトル等)
    "platform",          # instagram / x / note / web 等
    "observed_at",       # 観察日(YYYY-MM-DD)
    "summary",           # 内容の短い要約(最大200字)
    "reliability_score", # 0.0〜1.0(データ信頼性)
    "created_at",        # 初回登録日時(ISO8601)
]

EVIDENCE_LINKS_HEADERS = [
    "link_id",           # hash(unit_id:evidence_id) の先頭10文字
    "unit_id",           # knowledge_units.unit_id
    "evidence_id",       # evidence_registry.evidence_id
    "support_strength",  # 0.0〜1.0(このEvidenceがUnitをどれだけ支持するか)
    "support_reason",    # 短い理由テキスト
    "created_at",        # 登録日時(ISO8601)
]

# ensure_creator_intelligence_library_sheets()が起動時にループする
# (シート名, ヘッダー)の一覧。
_CREATOR_INTELLIGENCE_LIBRARY_SHEETS = [
    (SHEET_KNOWLEDGE_LIBRARY, KNOWLEDGE_LIBRARY_HEADERS),
    (SHEET_SUCCESS_PATTERNS, SUCCESS_PATTERNS_HEADERS),
    (SHEET_PSYCHOLOGY_PATTERNS, PSYCHOLOGY_PATTERNS_HEADERS),
    (SHEET_HOOK_LIBRARY, HOOK_LIBRARY_HEADERS),
    (SHEET_CTA_LIBRARY, CTA_LIBRARY_HEADERS),
    (SHEET_RESEARCH_SOURCES, RESEARCH_SOURCES_HEADERS),
    (SHEET_KNOWLEDGE_UNITS, KNOWLEDGE_UNITS_HEADERS),  # 2026-07-01: Learning Engine
]

# CORE HARI専門知識DB (core_hari_kb) スキーマ
#
# 【Knowledge_type 値】
#   mechanism  : 施術・身体の仕組み（なぜそうなるか）
#   symptom    : お客様が感じる症状・悩み
#   outcome    : 施術・継続の効果・変化
#   process    : 手順・フロー（施術の流れなど）
#   faq        : よくある質問と正直な回答
#   self_care  : お客様が自分でできること
#
# 【content_role 値】
#   hook       : 動画冒頭フックで使える（問いかけ・共感）
#   body       : 本編説明・解説で使える
#   proof      : 信頼性・根拠として使える
#   universal  : どのパートでも使える
#
# 【tags】
#   creator_intelligence/verticals/core_hari/structure_patterns.py の
#   StructurePattern.required_kb_tags と対応させること。
#   例: "仕組み,施術,リンパ"
CORE_HARI_KB_HEADERS = [
    "topic",            # 知識のトピック（例: 顔筋の役割）
    "knowledge_type",   # mechanism / symptom / outcome / process / faq / self_care
    "content_role",     # hook / body / proof / universal
    "fact",             # 実際の知識・事実（オーナーが記入する核心。1〜3文）
    "example_sentence", # この知識をどう話すか（オーナーが書く例文。任意）
    "tags",             # カンマ区切りタグ（StructurePatternのrequired_kb_tagsと対応）
    "source",           # 出典（オーナー確認済み / 施術マニュアル / 体験談 等）
    "verified",         # yes / no（no=候補段階、Step2では使わない）
    "added_at",         # 追加日（YYYY-MM-DD）
    "notes",            # 補足・注意事項（任意）
]

# 2026-07-02(10回目): Thought Library — 考え方・話し方・例え話のデータベース
# 「単語」ではなく「考え方」を保存する。Creator Studio はここから台本を組み立てる。
# Thought Library — Creator Intelligence Platform 汎用スキーマ
# knowledge_type は KNOWLEDGE_TYPES の値:
#   Observation / Question / Evidence / Experience / Perspective / Advice / Research / ContentAsset
THOUGHT_LIBRARY_HEADERS = [
    "id",               # 一意識別子（例: TL-001）
    "topic",            # テーマの短い識別子
    "knowledge_type",   # Observation/Question/Evidence/Experience/Perspective/Advice/Research/ContentAsset
    "content",          # 知識の核心（専門家が記載する。1〜3文）
    "speaker_words",    # 専門家がこの知識をどう語るか（複数のセリフ例。改行区切り）
    "evidence_level",   # A: 研究・文献あり / B: 実践経験に基づく / C: 仮説・探求中
    "verified",         # TRUE / FALSE
    "updated_at",       # 最終更新日（YYYY-MM-DD）
]

AUTO_ADDED_ACCOUNTS_HEADERS = [
    "追加日時",
    "ユーザー名",
    "累積言及元アカウント数",
    "言及元アカウント(累積)",
    "参考ハッシュタグ",
    "サンプルキャプション",
]

ACCOUNT_MENTION_TRACKER_HEADERS = [
    "ユーザー名",
    "初回検出日時",
    "最終検出日時",
    "累積言及元アカウント数",
    "言及元アカウント(累積)",
    "直近サンプルキャプション",
    "直近参考ハッシュタグ",
]

_spreadsheet = None
_worksheet_cache = {}


def _load_credentials() -> Credentials:
    """
    GOOGLE_SERVICE_ACCOUNT_JSON は
    - サービスアカウントJSONファイルへのパス
    - サービスアカウントJSONの文字列そのもの
    のいずれでも動作するようにする。
    """
    value = GOOGLE_SERVICE_ACCOUNT_JSON
    if not value:
        raise EnvironmentError("GOOGLE_SERVICE_ACCOUNT_JSON が設定されていません。")

    if os.path.exists(value):
        return Credentials.from_service_account_file(value, scopes=SCOPES)

    try:
        info = json.loads(value)
    except json.JSONDecodeError:
        raise EnvironmentError(
            "GOOGLE_SERVICE_ACCOUNT_JSON はファイルパスまたはJSON文字列である必要があります。"
            f"(指定値: {value})"
        )
    return Credentials.from_service_account_info(info, scopes=SCOPES)


def _get_spreadsheet():
    global _spreadsheet
    if _spreadsheet is not None:
        return _spreadsheet

    if not GOOGLE_SHEET_ID:
        raise EnvironmentError("GOOGLE_SHEET_ID が設定されていません。")

    print("[API START] Google Sheets 接続")
    creds = _load_credentials()
    gc = gspread.authorize(creds)
    _spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
    print("[API END] Google Sheets 接続")
    return _spreadsheet


def _get_or_create_worksheet(sheet_name: str, headers: list):
    if sheet_name in _worksheet_cache:
        return _worksheet_cache[sheet_name]

    spreadsheet = _get_spreadsheet()
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=sheet_name, rows=1000, cols=max(len(headers), 10)
        )

    existing_header = worksheet.row_values(1)
    if not existing_header:
        worksheet.append_row(headers, value_input_option="USER_ENTERED")

    _worksheet_cache[sheet_name] = worksheet
    return worksheet


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _blank_if_none(value):
    return "" if value is None else value


def _post_row(post: dict) -> list:
    return [
        post.get("url", ""),
        post.get("posted_at", ""),
        post.get("views", 0),
        post.get("likes", 0),
        post.get("comments", 0),
        _blank_if_none(post.get("saves")),
        _blank_if_none(post.get("shares")),
        _blank_if_none(post.get("followers")),
        _blank_if_none(post.get("view_multiplier")),
        _blank_if_none(post.get("growth_velocity")),
        _blank_if_none(post.get("growth_rate")),
        _blank_if_none(post.get("duration_sec")),
        post.get("caption", ""),
        "、".join(post.get("hashtags") or []),
        post.get("category", ""),
    ]


def _save_reels(posts: list, sheet_name: str) -> None:
    """
    プール対象リールの分析項目を1シートに保存する。プールが0件なら何もしない。

    【2026-07-01: append_rowのループをappend_rowsの一括呼び出しに変更】
    Google Sheets APIの書き込みリクエスト数(1分あたりの上限)を超えて429
    エラーになる事象が発生したため、本ファイルの全保存関数で「1件ずつ
    append_row」を「全件まとめてappend_rows(1回のAPIリクエスト)」に統一した。
    """
    if not posts:
        return

    worksheet = _get_or_create_worksheet(sheet_name, REEL_SHEET_HEADERS)
    now = _now()
    rows = [[now] + _post_row(post) for post in posts]
    worksheet.append_rows(rows, value_input_option="USER_ENTERED")


def save_raw_fetch_log(posts: list) -> None:
    """
    フィルター(プール選別)前の取得投稿"全件"を、除外理由付きでraw_fetch_log
    シートに保存する(2026-06-30追加)。

    目的: 「取得27件中25件が再生数で除外・採用0件」のような事態が起きた際に、
    どの投稿がどの理由で外れたのかをreels/trend_postsシート(プール入りした
    投稿のみ)だけでは確認できなかった問題に対応する。

    posts: bright_data_fetcher.build_post_pool呼び出し後の全件
           (post["pool_exclusion_reason"]が付与されている前提。
           空文字列なら除外なし=プール入り)。fetch_errorのアイテムも含む。
    """
    if not posts:
        return

    worksheet = _get_or_create_worksheet(SHEET_RAW_FETCH_LOG, RAW_FETCH_LOG_HEADERS)
    now = _now()

    rows = [
        [
            now,
            post.get("username", "") or post.get("source_account", ""),
            post.get("url", ""),
            post.get("posted_at", ""),
            post.get("views", 0),
            post.get("likes", 0),
            _blank_if_none(post.get("followers")),
            _blank_if_none(post.get("view_multiplier")),
            post.get("pool_exclusion_reason", ""),
        ]
        for post in posts
    ]
    worksheet.append_rows(rows, value_input_option="USER_ENTERED")


def save_adopted_posts(posts: list) -> None:
    """Instagram全体トレンドでプール対象になった投稿(構造的に使える全件)をreelsシートに保存する。"""
    _save_reels(posts, SHEET_REELS)


def _save_ranking(posts: list, sheet_name: str, sort_key, top_n: int = RANK_TOP_N) -> None:
    """postsをsort_keyの降順に並べ、上位top_n件をランキングシートに保存する。"""
    ranked = sorted(posts, key=sort_key, reverse=True)[:top_n]
    if not ranked:
        return

    worksheet = _get_or_create_worksheet(sheet_name, RANK_SHEET_HEADERS)
    now = _now()
    rows = [[now, rank] + _post_row(post) for rank, post in enumerate(ranked, start=1)]
    worksheet.append_rows(rows, value_input_option="USER_ENTERED")


def save_rankings(posts: list) -> None:
    """
    4種類のランキングシートを作成する。
    - Instagram全体トレンドTOP20: 採用リールを再生数順
    - 再生倍率TOP20: 採用リールを再生倍率(再生数÷フォロワー数)順
    - 伸び率TOP20: 採用リールを伸び率(日次再生数÷フォロワー数)順
      (2026-06-29(4回目)追加)
    - 保存率TOP20: 保存数が取得できた採用リールのみを保存率順(データが無ければ作成しない)
    """
    _save_ranking(posts, SHEET_RANK_ALL, sort_key=lambda p: p.get("views", 0))
    _save_ranking(
        posts,
        SHEET_RANK_MULTIPLIER,
        sort_key=lambda p: p.get("view_multiplier") or 0,
    )
    _save_ranking(
        posts,
        SHEET_RANK_GROWTH,
        sort_key=lambda p: p.get("growth_rate") or 0,
    )

    save_rate_posts = [p for p in posts if p.get("save_rate") is not None]
    if save_rate_posts:
        _save_ranking(
            save_rate_posts,
            SHEET_RANK_SAVE_RATE,
            sort_key=lambda p: p.get("save_rate") or 0,
        )


def save_research_candidates(posts: list) -> None:
    """
    プール対象の投稿"全件"について、research_candidate_score.pyが計算した
    Research Candidate Score(合計・7項目の内訳・判定)をresearch_candidates
    シートに保存する(2026-07-05: trend_postsからリネーム)。

    AI個別分析(post_analysis/core_hari_ideas)が実行されたかどうかに関わらず
    全件を記録するため、「なぜこの投稿はAI分析されなかったのか」を後から
    確認できる透明性ログになる。

    posts: 各要素が "research_candidate_score" キー
           (research_candidate_score.compute_research_candidate_scoreの
           戻り値: {"total", "breakdown", "tier"})を持っていること
           (main.pyがresearch_candidate_score.score_posts()で付与してから渡す)。
    """
    if not posts:
        return

    worksheet = _get_or_create_worksheet(SHEET_RESEARCH_CANDIDATES, RESEARCH_CANDIDATES_HEADERS)
    now = _now()

    rows = []
    for post in posts:
        score = post.get("research_candidate_score") or {}
        breakdown = score.get("breakdown") or {}

        row = [now] + _post_row(post) + [score.get("total", 0)]
        for key in RESEARCH_CANDIDATE_SCORE_BREAKDOWN_KEYS:
            row.append(breakdown.get(key, 0))
        row.append(score.get("tier", ""))
        rows.append(row)

    worksheet.append_rows(rows, value_input_option="USER_ENTERED")


def save_research_candidate_score_debug(posts: list) -> None:
    """
    各投稿のResearch Candidate Score配点内訳を、生値(実測値)と得点をセットで
    research_candidate_score_debugシートに保存する(2026-07-01追加。2026-07-05に
    trend_score_debugからリネーム)。

    背景: 取得25件中、Research Candidate Score 80点以上(AI分析対象)が0件
    という事態が発生したが、research_candidatesシートには合計点と項目別の
    得点しかなく、「再生数が何回だったから何点になったのか」「いいね率が
    何%だったのか」といった生値が見えず、配点しきい値の調整判断ができなかった。
    本シートは生値と得点を1行に並べることで、配点(research_candidate_score.py
    の_score_*関数群)を調整するための判断材料を提供する。

    posts: research_candidate_score.score_posts()済み
           (post["research_candidate_score"]を持つ)投稿。
    """
    if not posts:
        return

    worksheet = _get_or_create_worksheet(SHEET_RESEARCH_CANDIDATE_SCORE_DEBUG, RESEARCH_CANDIDATE_SCORE_DEBUG_HEADERS)
    now = _now()

    rows = []
    for post in posts:
        score = post.get("research_candidate_score") or {}
        breakdown = score.get("breakdown") or {}

        views = post.get("views", 0) or 0
        likes = post.get("likes", 0) or 0
        comments = post.get("comments", 0) or 0
        like_rate = round(likes / views, 4) if views else 0
        comment_rate = round(comments / views, 4) if views else 0

        rows.append([
            now,
            post.get("url", ""),
            post.get("username", ""),
            score.get("total", 0),
            score.get("tier", ""),
            views,
            breakdown.get("再生数", 0),
            _blank_if_none(post.get("followers")),
            _blank_if_none(post.get("view_multiplier")),
            breakdown.get("再生倍率", 0),
            likes,
            like_rate,
            breakdown.get("いいね率", 0),
            comments,
            comment_rate,
            breakdown.get("コメント率", 0),
            post.get("posted_at", ""),
            breakdown.get("投稿からの日数", 0),
            _blank_if_none(post.get("duration_sec")),
            breakdown.get("動画時間", 0),
            _blank_if_none(post.get("account_post_count_window")),
            breakdown.get("投稿頻度", 0),
        ])

    worksheet.append_rows(rows, value_input_option="USER_ENTERED")


def save_category_trend_summary(category_label: str, posts: list, analysis: dict) -> None:
    """
    【2026-07-02改名(item7)】旧save_trend_analysis。カテゴリ単位のAI集約分析
    結果をtrend_analysis_summaryシートに1行保存する(実行ごとに1行)。
    タイトル案10個/冒頭フック10個は、改行区切りの番号付きテキストとして保存する。

    旧trend_analysisシート名はSHEET_CATEGORY_TREND_SUMMARY
    ("trend_analysis_summary")に変更した。旧名"trend_analysis"は、ユーザー
    要望(item7: 投稿ごとのTrend Score・分析内容・伸びた理由・CORE HARI FACEへの
    応用を保存したい)に対応するため、投稿ごとの形式に再設計したsave_trend_
    analysis()に明け渡した(下記参照)。

    【2026-07-02(item5)】Instagram全体トレンド/美容ジャンルトレンドの
    2カテゴリ分、main.pyから1回ずつ(category_labelを変えて)呼ばれる想定。
    """
    worksheet = _get_or_create_worksheet(SHEET_CATEGORY_TREND_SUMMARY, CATEGORY_TREND_SUMMARY_HEADERS)

    row = [_now(), category_label, len(posts)]
    for key in CATEGORY_ANALYSIS_TEXT_KEYS:
        row.append(analysis.get(key, ""))
    for key in CATEGORY_ANALYSIS_LIST_KEYS:
        items = analysis.get(key) or []
        row.append("\n".join(f"{i}. {text}" for i, text in enumerate(items, start=1)))

    worksheet.append_row(row, value_input_option="USER_ENTERED")


def save_trend_analysis(entries: list) -> None:
    """
    【2026-07-02新設(item7)】trend_analysisシートを「実行ごとの集計1行」から
    「投稿ごとの1行」に再設計したことに伴う新しい保存関数。

    ユーザー要望「trend_analysisシートに、投稿ごとのTrend Score・分析内容・
    伸びた理由・CORE HARI FACEへの応用を保存してほしい」に対応する。内容は
    save_success_factors()と同じentries(openai_analyzer.analyze_success_
    factorsの結果)を使うが、こちらは「カテゴリ」列を含む投稿ごとの統合ビュー
    として、success_factorsシートとは別にtrend_analysisシートへ保存する。

    【注意】既存のtrend_analysisタブには旧フォーマット(対象カテゴリ・分析対象
    投稿数などの集計列)の行が残っている場合がある。次回実行前に一度手動で
    タブの内容をクリアしておくこと(以後はこの新フォーマットに統一される)。

    entries: save_post_analyses()/save_success_factors()と同じ形式
             ([{"post":..., "success_factors":...}, ...])。
    """
    if not entries:
        return

    worksheet = _get_or_create_worksheet(SHEET_TREND_ANALYSIS, TREND_ANALYSIS_HEADERS)
    now = _now()

    rows = []
    for entry in entries:
        post = entry.get("post") or {}
        success_factors = entry.get("success_factors") or {}
        score = post.get("research_candidate_score") or {}

        row = [
            now,
            post.get("category", ""),
            post.get("url", ""),
            post.get("username", ""),
            score.get("total", ""),
            score.get("tier", ""),
        ]
        for key in SUCCESS_FACTOR_FIELDS:
            row.append(success_factors.get(key, ""))
        rows.append(row)

    worksheet.append_rows(rows, value_input_option="USER_ENTERED")


def get_recent_pick_categories(days: int = 7) -> set:
    """
    【2026-07-02新設(item4)】直近days日分のdaily_content_picksシートから
    「投稿カテゴリ」列(idea["投稿カテゴリ"]、悩み提示型・ビフォーアフター型など)
    を集める。main._select_daily_content_picksが「似た内容ではなく毎回違う
    切り口になるように」という要望に対応するための重複回避判定に使う。

    シートが空・読み込み失敗時は空集合を返す(失敗しても選定処理自体は
    止めない。「毎日使えること」を優先する方針)。
    """
    try:
        worksheet = _get_or_create_worksheet(SHEET_DAILY_CONTENT_PICKS, DAILY_CONTENT_PICKS_HEADERS)
        all_values = worksheet.get_all_values()
    except Exception:
        return set()

    if len(all_values) <= 1:
        return set()

    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    categories = set()
    for row in all_values[1:]:
        if len(row) < 3:
            continue
        timestamp_str, _post_type, category = row[0], row[1], row[2]
        try:
            ts = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if ts >= cutoff and category:
            categories.add(category)
    return categories


def save_daily_content_picks(picks: list) -> None:
    """
    【2026-07-02新設(item4)】その日実際に使う「30秒リール1本・60秒リール1本・
    Threads投稿1本」(main._select_daily_content_picksが選定した結果)を
    daily_content_picksシートに保存する。

    picks: [{"post_type": "30秒リール"|"60秒リール"|"Threads投稿",
             "category": 投稿カテゴリ, "post": 投稿dict,
             "title": str, "body": str, "caption": str, "cta": str}, ...]
    """
    if not picks:
        return

    worksheet = _get_or_create_worksheet(SHEET_DAILY_CONTENT_PICKS, DAILY_CONTENT_PICKS_HEADERS)
    now = _now()

    rows = []
    for pick in picks:
        post = pick.get("post") or {}
        score = post.get("research_candidate_score") or {}
        rows.append([
            now,
            pick.get("post_type", ""),
            pick.get("category", ""),
            post.get("url", ""),
            post.get("username", ""),
            score.get("total", ""),
            pick.get("title", ""),
            pick.get("body", ""),
            pick.get("caption", ""),
            pick.get("cta", ""),
        ])

    worksheet.append_rows(rows, value_input_option="USER_ENTERED")


def save_post_analyses(entries: list) -> None:
    """
    Research Candidate Score上位research_candidate_score.TOP_N_FOR_ANALYSIS件
    (既定5件。2026-07-02に一時「常に上位N件固定」としたが、2026-07-05に
    ANALYSIS_MIN_SCORE以上という条件を復活させた。research_candidate_score.
    select_for_analysis参照)の
    投稿について、②analyze_post_structureの分析結果(POST_ANALYSIS_FIELDS:
    prompts.POST_ANALYSIS_TEXT_KEYSの13項目)をpost_analysisシートに1行ずつ
    保存する。投稿案そのものはsave_core_hari_ideas()でcore_hari_ideasシートに
    保存する(2026-06-29(6回目): ②analyze_post_structureと③+④generate_core_
    hari_ideaが別々のAI呼び出しになったため、entriesの"analysis"キーは②の
    結果のみを指す)。

    entries: [{"post": 投稿dict, "analysis": analyze_post_structureの戻り値dict,
               "idea": generate_core_hari_ideaの戻り値dict}, ...]
             postは"research_candidate_score"キー
             (research_candidate_score.compute_research_candidate_scoreの戻り値)を
             持っていること。
    """
    if not entries:
        return

    worksheet = _get_or_create_worksheet(SHEET_POST_ANALYSIS, POST_ANALYSIS_HEADERS)
    now = _now()

    rows = []
    for entry in entries:
        post = entry.get("post") or {}
        analysis = entry.get("analysis") or {}
        score = post.get("research_candidate_score") or {}

        row = [
            now,
            post.get("url", ""),
            post.get("username", ""),
            post.get("views", 0),
            _blank_if_none(post.get("view_multiplier")),
            _blank_if_none(post.get("growth_rate")),
            score.get("total", ""),
            score.get("tier", ""),
        ]
        for key in POST_ANALYSIS_FIELDS:
            row.append(analysis.get(key, ""))
        rows.append(row)

    worksheet.append_rows(rows, value_input_option="USER_ENTERED")


def save_core_hari_ideas(entries: list) -> None:
    """
    save_post_analyses()と同じ対象投稿について、③+④generate_core_hari_ideaの
    投稿案(CORE_HARI_IDEAS_TEXT_FIELDS: prompts.CORE_HARI_IDEA_TEXT_KEYSの
    7項目。タイトル・30秒版リール・60秒版リール・Threads投稿・キャプション・
    CTA・投稿カテゴリ)をcore_hari_ideasシートに1行ずつ保存する
    (2026-06-29(5回目)追加、(6回目)で項目を3段階パイプライン用に更新)。

    entries: save_post_analyses()と同じ形式。"idea"キー
             (generate_core_hari_ideaの戻り値dict)を読む。
    """
    if not entries:
        return

    worksheet = _get_or_create_worksheet(SHEET_CORE_HARI_IDEAS, CORE_HARI_IDEAS_HEADERS)
    now = _now()

    rows = []
    for entry in entries:
        post = entry.get("post") or {}
        idea = entry.get("idea") or {}
        score = post.get("research_candidate_score") or {}

        row = [
            now,
            post.get("url", ""),
            post.get("username", ""),
            score.get("total", ""),
            score.get("tier", ""),
        ]
        for key in CORE_HARI_IDEAS_TEXT_FIELDS:
            row.append(idea.get(key, ""))
        rows.append(row)

    worksheet.append_rows(rows, value_input_option="USER_ENTERED")


def save_success_factors(entries: list) -> None:
    """
    save_post_analyses()/save_core_hari_ideas()と同じ対象投稿について、
    openai_analyzer.analyze_success_factorsの出力(SUCCESS_FACTOR_FIELDS。
    2026-07-01(2回目)追加時は6項目だったが、2026-07-02にitem3+item6対応で
    13項目に拡張した。詳細はprompts.SUCCESS_FACTOR_TEXT_KEYS直前のコメント
    参照)をsuccess_factorsシートに1行ずつ保存する。

    Research Candidate Score(数値配点、research_candidate_score.py)とは別の、
    AIによる質的な「成功要因分析」。既存のpost_analysis(analyze_post_structureの13項目)
    とは独立したシート・独立したAI呼び出し結果である(ユーザーの選択により、
    既存を置き換えず新しい分析として追加した)。

    entries: save_post_analyses()と同じ形式([{"post":..., "analysis":...,
             "idea":..., "success_factors":...}, ...])。"success_factors"
             キー(analyze_success_factorsの戻り値dict)を読む。
    """
    if not entries:
        return

    worksheet = _get_or_create_worksheet(SHEET_SUCCESS_FACTORS, SUCCESS_FACTOR_HEADERS)
    now = _now()

    rows = []
    for entry in entries:
        post = entry.get("post") or {}
        success_factors = entry.get("success_factors") or {}
        score = post.get("research_candidate_score") or {}

        row = [
            now,
            post.get("url", ""),
            post.get("username", ""),
            score.get("total", ""),
            score.get("tier", ""),
        ]
        for key in SUCCESS_FACTOR_FIELDS:
            row.append(success_factors.get(key, ""))
        rows.append(row)

    worksheet.append_rows(rows, value_input_option="USER_ENTERED")


# --- SNS Pattern Lab投稿素材(content_carousel/content_reels/content_threads/
# content_caption): 2026-07-01(3回目)追加 ---
#
# openai_analyzer.generate_pattern_lab_contentは21項目を1回のOpenAI呼び出しで
# まとめて生成するが、保存先は出力タイプごとに4シートへ分ける(1シートに21列
# まとめると見づらいため)。4関数はすべて同じentries(pattern_labキーを読む)を
# 受け取り、それぞれ自分が担当するフィールド群だけを抜き出して保存する。


def _save_pattern_lab_sheet(entries: list, sheet_name: str, headers: list, fields: list) -> None:
    if not entries:
        return

    worksheet = _get_or_create_worksheet(sheet_name, headers)
    now = _now()

    rows = []
    for entry in entries:
        post = entry.get("post") or {}
        pattern_lab = entry.get("pattern_lab") or {}
        score = post.get("research_candidate_score") or {}

        row = [
            now,
            post.get("url", ""),
            post.get("username", ""),
            score.get("total", ""),
            score.get("tier", ""),
        ]
        for key in fields:
            row.append(pattern_lab.get(key, ""))
        rows.append(row)

    worksheet.append_rows(rows, value_input_option="USER_ENTERED")


def save_content_carousel(entries: list) -> None:
    """
    success_factors()と同じ対象投稿について、SNS Pattern Lab向けInstagram
    カルーセル投稿案(10枚分、CONTENT_CAROUSEL_FIELDS)をcontent_carouselシートに
    1行ずつ保存する(2026-07-01(3回目)追加)。

    entries: [{"post":..., "analysis":..., "idea":..., "success_factors":...,
               "pattern_lab": generate_pattern_lab_contentの戻り値dict}, ...]
    """
    _save_pattern_lab_sheet(
        entries, SHEET_CONTENT_CAROUSEL, CONTENT_CAROUSEL_HEADERS, CONTENT_CAROUSEL_FIELDS
    )


def save_content_reels(entries: list) -> None:
    """
    同じ対象投稿について、SNS Pattern Lab向けリール台本(冒頭3秒・本文・
    テロップ・ナレーション・CTA、CONTENT_REELS_FIELDS)をcontent_reelsシートに
    1行ずつ保存する(2026-07-01(3回目)追加)。entries形式はsave_content_carousel
    と同じ。
    """
    _save_pattern_lab_sheet(
        entries, SHEET_CONTENT_REELS, CONTENT_REELS_HEADERS, CONTENT_REELS_FIELDS
    )


def save_content_threads(entries: list) -> None:
    """
    同じ対象投稿について、SNS Pattern Lab向けThreads投稿案(短文3本+やや詳しい
    解説1本、CONTENT_THREADS_FIELDS)をcontent_threadsシートに1行ずつ保存する
    (2026-07-01(3回目)追加)。entries形式はsave_content_carouselと同じ。
    """
    _save_pattern_lab_sheet(
        entries, SHEET_CONTENT_THREADS, CONTENT_THREADS_HEADERS, CONTENT_THREADS_FIELDS
    )


def save_content_caption(entries: list) -> None:
    """
    同じ対象投稿について、SNS Pattern Lab向けキャプション(Instagram用・サブスク
    誘導用、CONTENT_CAPTION_FIELDS)をcontent_captionシートに1行ずつ保存する
    (2026-07-01(3回目)追加)。entries形式はsave_content_carouselと同じ。
    """
    _save_pattern_lab_sheet(
        entries, SHEET_CONTENT_CAPTION, CONTENT_CAPTION_HEADERS, CONTENT_CAPTION_FIELDS
    )


# --- auto_added_accounts: 自動追加されたアカウントの履歴ログ(人の操作は不要) ---


def save_auto_added_accounts(entries: list) -> None:
    """
    accounts_writer.add_accounts() によって実際にANTENNA_ACCOUNTSへ追加された
    アカウントを、履歴ログとしてauto_added_accountsシートに記録する。
    これは記録のみが目的で、ユーザーの操作は不要(承認/除外列などは持たない)。

    entries: classify_candidates()のto_promoteのうち、実際に追加されたものの
             候補dictのリスト({"username", "source_accounts", "sample_hashtags",
             "sample_caption", ...})
    """
    if not entries:
        return

    worksheet = _get_or_create_worksheet(
        SHEET_AUTO_ADDED_ACCOUNTS, AUTO_ADDED_ACCOUNTS_HEADERS
    )
    now = _now()

    rows = []
    for entry in entries:
        source_accounts = entry.get("source_accounts") or []
        rows.append(
            [
                now,
                entry.get("username", ""),
                len(source_accounts),
                "、".join(source_accounts),
                "、".join(entry.get("sample_hashtags") or []),
                entry.get("sample_caption", ""),
            ]
        )

    worksheet.append_rows(rows, value_input_option="USER_ENTERED")


# --- account_mention_tracker: しきい値未満の候補の累積カウント用ワーキングシート ---


def get_mention_tracker() -> dict:
    """
    account_mention_trackerシートを読み込み、累積言及データを辞書化する。

    戻り値: {
        username: {
            "row": 行番号(1始まり。既存行の更新に使う),
            "first_seen": str,
            "source_accounts": set(これまでの累積言及元アカウント),
        },
        ...
    }
    """
    worksheet = _get_or_create_worksheet(
        SHEET_ACCOUNT_MENTION_TRACKER, ACCOUNT_MENTION_TRACKER_HEADERS
    )
    all_values = worksheet.get_all_values()

    tracker = {}
    for row_index, row in enumerate(all_values[1:], start=2):  # 1行目はヘッダー
        username = (row[0] if len(row) > 0 else "").strip().lower()
        if not username:
            continue
        first_seen = row[1] if len(row) > 1 else ""
        source_accounts_raw = row[4] if len(row) > 4 else ""
        source_accounts = {
            s.strip() for s in source_accounts_raw.split("、") if s.strip()
        }
        tracker[username] = {
            "row": row_index,
            "first_seen": first_seen,
            "source_accounts": source_accounts,
        }

    return tracker


def upsert_mention_tracker(entries: list) -> None:
    """
    しきい値未満の候補(classify_candidates()のto_track)を、
    account_mention_trackerシートに保存する。既にシートにある候補は該当行を
    更新し、無ければ新規行を追記する。

    entries: candidate dictのリスト。source_accountsには累積後の集合
             (classify_candidatesが返したもの)が入っていること。
    """
    if not entries:
        return

    worksheet = _get_or_create_worksheet(
        SHEET_ACCOUNT_MENTION_TRACKER, ACCOUNT_MENTION_TRACKER_HEADERS
    )
    tracker = get_mention_tracker()
    now = _now()

    # 2026-07-01: 既存行の更新(worksheet.update)と新規行の追記(append_row)を
    # entryごとに個別のAPIリクエストにしていたのを、更新はbatch_updateで1回、
    # 新規追記はappend_rowsで1回にまとめた(Sheets APIの書き込みリクエスト数削減)。
    update_data = []
    new_rows = []

    for entry in entries:
        username = (entry.get("username") or "").strip().lower()
        if not username:
            continue

        source_accounts = entry.get("source_accounts") or []
        existing = tracker.get(username)
        first_seen = existing["first_seen"] if existing else now

        row_values = [
            username,
            first_seen,
            now,
            len(source_accounts),
            "、".join(source_accounts),
            entry.get("sample_caption", ""),
            "、".join(entry.get("sample_hashtags") or []),
        ]

        if existing:
            row_number = existing["row"]
            update_data.append({"range": f"A{row_number}:G{row_number}", "values": [row_values]})
        else:
            new_rows.append(row_values)

    if update_data:
        worksheet.batch_update(update_data, value_input_option="USER_ENTERED")
    if new_rows:
        worksheet.append_rows(new_rows, value_input_option="USER_ENTERED")


def remove_from_mention_tracker(usernames: list) -> None:
    """
    しきい値に到達して自動追加された候補を、account_mention_trackerシートから
    削除する(以後は累積カウントの対象から外れる)。

    行削除によるインデックスのずれを避けるため、行番号の降順で削除する。
    """
    if not usernames:
        return

    worksheet = _get_or_create_worksheet(
        SHEET_ACCOUNT_MENTION_TRACKER, ACCOUNT_MENTION_TRACKER_HEADERS
    )
    tracker = get_mention_tracker()

    target_usernames = {u.strip().lower() for u in usernames if u and u.strip()}
    rows_to_delete = sorted(
        (tracker[u]["row"] for u in target_usernames if u in tracker),
        reverse=True,
    )

    for row_number in rows_to_delete:
        worksheet.delete_rows(row_number)


# --- north_star_daily: Creator Intelligence Sprint 1 Task A(2026-07-03追加) ---


def save_north_star_daily(entries: list, result: dict) -> None:
    """
    openai_analyzer.generate_north_star_dailyの結果を、north_star_dailyシートに
    1行保存する。

    他の保存関数(save_post_analyses等)はentriesの件数だけ複数行をappend_rows
    するが、North Star Dailyは「投稿1件ごと」ではなく「実行(=1日)ごとに1件」
    という設計(AskUserQuestionで確認した方針)のため、save_category_trend_
    summaryと同じく単一行のappend_rowを使う(複数行のappend_rowsではない。
    バッチ書き込みの対象外で正しい)。

    entries: その日analyzeされた投稿のリスト(「対象投稿数」列にlen(entries)を
             記録するためだけに使う。中身は読まない)。
    result: generate_north_star_dailyの戻り値dict(NORTH_STAR_DAILY_TEXT_KEYS
            の各キーを持つ)。
    """
    worksheet = _get_or_create_worksheet(SHEET_NORTH_STAR_DAILY, NORTH_STAR_DAILY_HEADERS)

    result = result or {}
    row = [_now(), len(entries or [])]
    for key in NORTH_STAR_DAILY_TEXT_KEYS:
        row.append(result.get(key, ""))

    worksheet.append_row(row, value_input_option="USER_ENTERED")


# --- knowledge_library/success_patterns/psychology_patterns/hook_library/
#     cta_library/research_sources: Creator Intelligence Sprint 1 Task B
#     (2026-07-03追加) ---


def get_knowledge_library_rows() -> list:
    """
    knowledge_libraryシートの既存データ行を読み込む(2026-07-04(4回目)新設)。
    knowledge_registry.pyが「このパターンは既に登録済みか」を判定するために使う。

    戻り値: [{"row": 行番号(1始まり。update_knowledge_library_rowに渡す),
              "values": {列名: 値, ...}}, ...]
            (データ行が無い場合は空リスト)。
    """
    worksheet = _get_or_create_worksheet(SHEET_KNOWLEDGE_LIBRARY, KNOWLEDGE_LIBRARY_HEADERS)
    all_values = worksheet.get_all_values()

    rows = []
    for row_index, row in enumerate(all_values[1:], start=2):  # 1行目はヘッダー
        values = {
            header: (row[col] if col < len(row) else "")
            for col, header in enumerate(KNOWLEDGE_LIBRARY_HEADERS)
        }
        rows.append({"row": row_index, "values": values})
    return rows


def append_knowledge_library_row(values: dict) -> None:
    """新しい成功パターンをknowledge_libraryシートに1行追記する(初めて見るパターンのみ)。"""
    worksheet = _get_or_create_worksheet(SHEET_KNOWLEDGE_LIBRARY, KNOWLEDGE_LIBRARY_HEADERS)
    row = [values.get(header, "") for header in KNOWLEDGE_LIBRARY_HEADERS]
    worksheet.append_row(row, value_input_option="USER_ENTERED")


def update_knowledge_library_row(row_number: int, values: dict) -> None:
    """
    既存の成功パターン行(使用回数・最後に確認した日・信頼度・実績など)を更新する。
    row_numberはget_knowledge_library_rowsが返した"row"の値をそのまま渡すこと。
    """
    worksheet = _get_or_create_worksheet(SHEET_KNOWLEDGE_LIBRARY, KNOWLEDGE_LIBRARY_HEADERS)
    row = [values.get(header, "") for header in KNOWLEDGE_LIBRARY_HEADERS]
    end_col_letter = chr(ord("A") + len(KNOWLEDGE_LIBRARY_HEADERS) - 1)
    worksheet.update(
        f"A{row_number}:{end_col_letter}{row_number}",
        [row],
        value_input_option="USER_ENTERED",
    )


def save_research_sources(entries: list) -> None:
    """
    research_engine.gather_evidence_for_postの結果をresearch_sourcesシートに
    保存する(2026-07-04(4回目)追加。Creator Intelligence Sprint 2 Task1の
    根拠データをシート化する部分)。

    2026-07-04時点ではResearchProviderの各search()がスタブのため、実際に
    保存されるのは各投稿の「一次情報(投稿実測値)」1件のみ(外部検索は
    まだ行われない。research_engine.pyのdocstring参照)。将来、検索APIが
    実装されればここで保存される行数が自動的に増える(本関数自体の変更は不要)。

    entries: [{"post":..., "idea":..., "success_factors":...}, ...]
             (North Star Dailyの入力と同じ形式。"タグ"列にはidea["投稿カテゴリ"]
             を入れ、後からどの投稿案に基づく根拠かを追跡できるようにする)。
    """
    if not entries:
        return

    worksheet = _get_or_create_worksheet(SHEET_RESEARCH_SOURCES, RESEARCH_SOURCES_HEADERS)
    now = _now()

    rows = []
    for entry in entries:
        post = entry.get("post") or {}
        idea = entry.get("idea") or {}
        tag = idea.get("投稿カテゴリ", "")
        for evidence in gather_evidence_for_post(post):
            rows.append([
                now,
                evidence.get("出典名", ""),
                evidence.get("URL", ""),
                evidence.get("概要", ""),
                evidence.get("取得日", ""),
                tag,
            ])

    if rows:
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")


# --- core_hari_kb: CORE HARI専門知識DB (2026-07-01追加) ---

def get_core_hari_kb() -> list:
    """
    core_hari_kbシートの全行を読み込む。
    戻り値: [{"row": 行番号, "values": {列名: 値, ...}}, ...]
    空行・topic空の行はスキップする。
    """
    ws = _get_or_create_worksheet(SHEET_CORE_HARI_KB, CORE_HARI_KB_HEADERS)
    all_values = ws.get_all_values()
    rows = []
    for row_index, row in enumerate(all_values[1:], start=2):
        values = {
            header: (row[col].strip() if col < len(row) else "")
            for col, header in enumerate(CORE_HARI_KB_HEADERS)
        }
        if values.get("topic") and values.get("fact"):
            rows.append({"row": row_index, "values": values})
    return rows


def append_core_hari_kb_entries(entries: list) -> None:
    """
    core_hari_kbシートにエントリを一括追記する。
    entries: [{CORE_HARI_KB_HEADERSの各列名: 値, ...}, ...]
    """
    ws = _get_or_create_worksheet(SHEET_CORE_HARI_KB, CORE_HARI_KB_HEADERS)
    rows = [[e.get(h, "") for h in CORE_HARI_KB_HEADERS] for e in entries]
    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")


def save_core_hari_kb_samples(entries: list) -> None:
    """
    core_hari_kb_samplesシートに入力例を書き込む（ヘッダー＋データを上書き）。
    seed実行時に1度だけ呼ぶ。既存データは消去してから書き直す。
    entries: [{CORE_HARI_KB_HEADERSの各列名: 値, ...}, ...]
    """
    ws = _get_or_create_worksheet("core_hari_kb_samples", CORE_HARI_KB_HEADERS)
    ws.clear()
    all_rows = [CORE_HARI_KB_HEADERS]
    for e in entries:
        all_rows.append([e.get(h, "") for h in CORE_HARI_KB_HEADERS])
    ws.update(all_rows, value_input_option="USER_ENTERED")
    # ヘッダー行を太字・背景色で装飾（視認性向上）
    try:
        ws.format("A1:J1", {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.85, "green": 0.92, "blue": 0.98},
        })
        # fact / example_sentence 列（D・E列）を黄色背景で「ここを入力」と分かるように
        ws.format("D2:E100", {
            "backgroundColor": {"red": 1.0, "green": 0.99, "blue": 0.82},
        })
    except Exception:
        pass  # 装飾失敗は無視


def ensure_creator_intelligence_library_sheets() -> None:
    """
    Creator Intelligence Sprint 1のライブラリ系6シート(knowledge_library/
    success_patterns/psychology_patterns/hook_library/cta_library/
    research_sources)の雛形(タブ+ヘッダー行)を、無ければ作成する。

    AskUserQuestionで確認した方針により、Sprint 1ではこの6シートへの
    自動データ投入ロジックは実装しない(雛形のみ)。main.main()の冒頭付近で
    毎回呼び出され、_get_or_create_worksheetの冪等性(既にあれば何もしない)
    によって、何度実行してもデータ行を書き込まずタブとヘッダーだけを保証する。

    posts/entriesに依存しないため、取得・分析の結果に関わらず常に呼んで良い。
    1シートの作成に失敗しても他のシートの作成は継続する(既存の他の保存処理を
    壊さないため、1シートずつtry/exceptで囲む)。
    """
    for sheet_name, headers in _CREATOR_INTELLIGENCE_LIBRARY_SHEETS:
        try:
            _get_or_create_worksheet(sheet_name, headers)
        except Exception as e:
            print(f"  ⚠️ {sheet_name}シートの作成に失敗しました(スキップ): {e}")
    # core_hari_kb は別定義なので個別に作成
    try:
        _get_or_create_worksheet(SHEET_CORE_HARI_KB, CORE_HARI_KB_HEADERS)
    except Exception as e:
        print(f"  ⚠️ core_hari_kbシートの作成に失敗しました(スキップ): {e}")


# ────────────────────────────────────────────────────────────────────────────
# manual_post_results シート (2026-07-01: フィードバックループ)
# ────────────────────────────────────────────────────────────────────────────

def ensure_manual_post_results_sheet() -> None:
    """
    manual_post_resultsシートのタブ+ヘッダー行を、無ければ作成する。
    main()の冒頭で呼ぶ。ユーザーが手入力するシートなので、データ行は書き込まない。
    """
    try:
        _get_or_create_worksheet(SHEET_MANUAL_POST_RESULTS, MANUAL_POST_RESULTS_HEADERS)
    except Exception as e:
        print(f"  ⚠️ manual_post_resultsシートの作成に失敗しました: {e}")


def get_manual_post_results() -> list:
    """
    manual_post_resultsシートの全行を読み込む。
    戻り値: [{"row": 行番号(1始まり), "values": dict}, ...]
    """
    worksheet = _get_or_create_worksheet(SHEET_MANUAL_POST_RESULTS, MANUAL_POST_RESULTS_HEADERS)
    all_values = worksheet.get_all_values()
    if len(all_values) < 2:
        return []
    header = all_values[0]
    result = []
    for i, row in enumerate(all_values[1:], start=2):
        values = {
            header[col]: (row[col] if col < len(row) else "")
            for col in range(len(header))
        }
        result.append({"row": i, "values": values})
    return result


def mark_manual_post_result_checked(row_number: int, checked_at: str) -> None:
    """
    feedback_collectorが処理済みにする際に checked_at 列だけを書き込む。
    row_numberはget_manual_post_resultsが返した"row"の値をそのまま渡すこと。
    """
    worksheet = _get_or_create_worksheet(SHEET_MANUAL_POST_RESULTS, MANUAL_POST_RESULTS_HEADERS)
    col_index = MANUAL_POST_RESULTS_HEADERS.index("checked_at") + 1  # 1始まり
    col_letter = chr(ord("A") + col_index - 1)
    worksheet.update(f"{col_letter}{row_number}", [[checked_at]])


# ────────────────────────────────────────────────────────────────────────────
# knowledge_units シート (2026-07-01: Learning Engine)
# ────────────────────────────────────────────────────────────────────────────

def get_knowledge_units() -> list:
    """
    knowledge_unitsシートの全行を読み込む。
    戻り値: [{"row": 行番号(1始まり), "values": dict}, ...]
    "row"はupdate_knowledge_unitにそのまま渡す。
    """
    worksheet = _get_or_create_worksheet(SHEET_KNOWLEDGE_UNITS, KNOWLEDGE_UNITS_HEADERS)
    all_values = worksheet.get_all_values()
    if len(all_values) < 2:
        return []
    header = all_values[0]
    result = []
    for i, row in enumerate(all_values[1:], start=2):
        values = {
            header[col]: row[col] if col < len(row) else ""
            for col in range(len(header))
        }
        result.append({"row": i, "values": values})
    return result


def append_knowledge_unit(values: dict) -> None:
    """knowledge_unitsシートに新規KnowledgeUnitを1行追加する(初回発見時)。"""
    worksheet = _get_or_create_worksheet(SHEET_KNOWLEDGE_UNITS, KNOWLEDGE_UNITS_HEADERS)
    row = [str(values.get(h, "")) for h in KNOWLEDGE_UNITS_HEADERS]
    worksheet.append_rows([row], value_input_option="USER_ENTERED")


def update_knowledge_unit(row_number: int, values: dict) -> None:
    """
    knowledge_unitsシートの既存行をまるごと上書きする(再発見時)。
    row_numberはget_knowledge_unitsが返した"row"の値をそのまま渡すこと。
    """
    worksheet = _get_or_create_worksheet(SHEET_KNOWLEDGE_UNITS, KNOWLEDGE_UNITS_HEADERS)
    row = [str(values.get(h, "")) for h in KNOWLEDGE_UNITS_HEADERS]
    end_col = chr(ord("A") + len(KNOWLEDGE_UNITS_HEADERS) - 1)
    worksheet.update(f"A{row_number}:{end_col}{row_number}", [row], value_input_option="USER_ENTERED")


# ────────────────────────────────────────────────────────────────────────────
# Evidence Layer (2026-07-01 Sprint3)
# ────────────────────────────────────────────────────────────────────────────

def ensure_evidence_sheets() -> None:
    """evidence_registry / evidence_links シートをなければ作成する。"""
    for sheet_name, headers in [
        (SHEET_EVIDENCE_REGISTRY, EVIDENCE_REGISTRY_HEADERS),
        (SHEET_EVIDENCE_LINKS, EVIDENCE_LINKS_HEADERS),
    ]:
        try:
            _get_or_create_worksheet(sheet_name, headers)
            print(f"  ✓ {sheet_name} シート確認済")
        except Exception as e:
            print(f"  ⚠️ {sheet_name} シート作成失敗: {e}")


def get_evidence_registry() -> list:
    """evidence_registryシートの全行を返す。[{"row": int, "values": dict}, ...]"""
    worksheet = _get_or_create_worksheet(SHEET_EVIDENCE_REGISTRY, EVIDENCE_REGISTRY_HEADERS)
    all_values = worksheet.get_all_values()
    if len(all_values) < 2:
        return []
    header = all_values[0]
    result = []
    for i, row in enumerate(all_values[1:], start=2):
        values = {header[col]: (row[col] if col < len(row) else "") for col in range(len(header))}
        result.append({"row": i, "values": values})
    return result


def append_evidence_entries(rows: list) -> None:
    """evidence_registryシートに複数行を一括追加する(バッチ書き込み)。"""
    if not rows:
        return
    worksheet = _get_or_create_worksheet(SHEET_EVIDENCE_REGISTRY, EVIDENCE_REGISTRY_HEADERS)
    data = [[str(r.get(h, "")) for h in EVIDENCE_REGISTRY_HEADERS] for r in rows]
    worksheet.append_rows(data, value_input_option="USER_ENTERED")


def get_evidence_links() -> list:
    """evidence_linksシートの全行を返す。[{"row": int, "values": dict}, ...]"""
    worksheet = _get_or_create_worksheet(SHEET_EVIDENCE_LINKS, EVIDENCE_LINKS_HEADERS)
    all_values = worksheet.get_all_values()
    if len(all_values) < 2:
        return []
    header = all_values[0]
    result = []
    for i, row in enumerate(all_values[1:], start=2):
        values = {header[col]: (row[col] if col < len(row) else "") for col in range(len(header))}
        result.append({"row": i, "values": values})
    return result


def append_evidence_links(rows: list) -> None:
    """evidence_linksシートに複数行を一括追加する(バッチ書き込み)。"""
    if not rows:
        return
    worksheet = _get_or_create_worksheet(SHEET_EVIDENCE_LINKS, EVIDENCE_LINKS_HEADERS)
    data = [[str(r.get(h, "")) for h in EVIDENCE_LINKS_HEADERS] for r in rows]
    worksheet.append_rows(data, value_input_option="USER_ENTERED")


# ────────────────────────────────────────────────────────────────────────────
# Creator Studio (2026-07-01 MVP)
# ────────────────────────────────────────────────────────────────────────────

def get_today_daily_content_picks(today: str) -> list:
    """
    daily_content_picksシートから今日(today=YYYY-MM-DD)の行を返す。
    戻り値: [{"実行日時":..., "投稿タイプ":..., ...}, ...]  ヘッダーをkeyにしたdict list
    """
    try:
        worksheet = _get_or_create_worksheet(SHEET_DAILY_CONTENT_PICKS, DAILY_CONTENT_PICKS_HEADERS)
        all_values = worksheet.get_all_values()
    except Exception as e:
        print(f"  ⚠️ daily_content_picks読み込み失敗: {e}")
        return []
    if len(all_values) < 2:
        return []
    header = all_values[0]
    result = []
    for row in all_values[1:]:
        if not row:
            continue
        ts = row[0] if row else ""
        if ts.startswith(today):
            values = {header[i]: (row[i] if i < len(row) else "") for i in range(len(header))}
            result.append(values)
    return result


def get_top_research_candidate(today: str) -> dict:
    """
    research_candidatesシートから今日の行のうち Research Candidate Score合計が
    最大の1件を返す。なければ空dictを返す。
    """
    try:
        worksheet = _get_or_create_worksheet(SHEET_RESEARCH_CANDIDATES, RESEARCH_CANDIDATES_HEADERS)
        all_values = worksheet.get_all_values()
    except Exception as e:
        print(f"  ⚠️ research_candidates読み込み失敗: {e}")
        return {}
    if len(all_values) < 2:
        return {}
    header = all_values[0]
    score_col = "Research Candidate Score合計"
    url_col = "投稿URL"
    best = {}
    best_score = -1
    for row in all_values[1:]:
        if not row or not row[0].startswith(today):
            continue
        values = {header[i]: (row[i] if i < len(row) else "") for i in range(len(header))}
        try:
            sc = float(values.get(score_col) or 0)
        except (ValueError, TypeError):
            sc = 0
        if sc > best_score:
            best_score = sc
            best = values
    return best


def save_creator_studio_daily(record: dict) -> None:
    """creator_studio_dailyシートに1行追加する。"""
    worksheet = _get_or_create_worksheet(SHEET_CREATOR_STUDIO_DAILY, CREATOR_STUDIO_DAILY_HEADERS)
    row = [str(record.get(h, "")) for h in CREATOR_STUDIO_DAILY_HEADERS]
    worksheet.append_rows([row], value_input_option="USER_ENTERED")


def get_recent_creator_studio_records(days: int = 30) -> list:
    """
    creator_studio_dailyシートから過去days日以内の行を返す。
    brand_score降順でソート済み。
    戻り値: [{ヘッダーをkeyにしたdict}, ...]
    """
    try:
        worksheet = _get_or_create_worksheet(SHEET_CREATOR_STUDIO_DAILY, CREATOR_STUDIO_DAILY_HEADERS)
        all_values = worksheet.get_all_values()
    except Exception as e:
        print(f"  ⚠️ creator_studio_daily読み込み失敗: {e}")
        return []
    if len(all_values) < 2:
        return []
    header = all_values[0]
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    result = []
    for row in all_values[1:]:
        if not row:
            continue
        date_str = row[0] if row else ""
        try:
            row_date = datetime.date.fromisoformat(date_str)
        except (ValueError, TypeError):
            continue
        if row_date < cutoff:
            continue
        values = {header[i]: (row[i] if i < len(row) else "") for i in range(len(header))}
        result.append(values)
    result.sort(key=lambda x: float(x.get("brand_score") or 0), reverse=True)
    return result


# ────────────────────────────────────────────────────────────────────────────
# Thought Library (2026-07-02(10回目))
# 考え方・話し方・例え話のデータベース。
# Creator Studio はここから台本を組み立てる。
# ────────────────────────────────────────────────────────────────────────────

def ensure_thought_library_sheet() -> None:
    """thought_library シートのタブ+ヘッダー行を、なければ作成する。"""
    try:
        _get_or_create_worksheet(SHEET_THOUGHT_LIBRARY, THOUGHT_LIBRARY_HEADERS)
        print("  ✓ thought_library シート確認済")
    except Exception as e:
        print(f"  ⚠️ thought_library シート作成失敗: {e}")


def get_thought_library() -> list:
    """
    thought_library シートの全行を読み込む。
    verified="TRUE" の行のみを返す（FALSE は候補段階で使わない）。
    戻り値: [dict, ...] — THOUGHT_LIBRARY_HEADERS のキーを持つ辞書のリスト
    """
    print("[API START] Google Sheets thought_library 読み込み")
    try:
        worksheet = _get_or_create_worksheet(SHEET_THOUGHT_LIBRARY, THOUGHT_LIBRARY_HEADERS)
        all_values = worksheet.get_all_values()
        print("[API END] Google Sheets thought_library 読み込み")
    except Exception as e:
        print(f"[API TIMEOUT] thought_library 読み込みスキップ: {e}")
        return []

    if len(all_values) < 2:
        return []
    header = all_values[0]
    result = []
    for row in all_values[1:]:
        if not row or not any(row):
            continue
        values = {header[i]: (row[i] if i < len(row) else "") for i in range(len(header))}
        # verified="TRUE" のみ使用
        if str(values.get("verified", "")).strip().upper() == "TRUE":
            result.append(values)
    return result


def seed_thought_library(entries: list) -> None:
    """
    thought_library シートが空のときだけシードデータを投入する（冪等）。
    entries: THOUGHT_LIBRARY_HEADERS に対応するキーを持つ辞書のリスト。
    既に1件でもデータ行があれば何もしない（手動編集を保護するため）。
    """
    print("[API START] Google Sheets thought_library シード確認")
    try:
        worksheet = _get_or_create_worksheet(SHEET_THOUGHT_LIBRARY, THOUGHT_LIBRARY_HEADERS)
        existing = worksheet.get_all_values()
        print("[API END] Google Sheets thought_library シード確認")
    except Exception as e:
        print(f"[API TIMEOUT] thought_library シード確認スキップ: {e}")
        return

    if len(existing) >= 2:  # ヘッダー + 1行以上あれば投入しない
        print(f"  thought_library: 既に{len(existing)-1}件あるためシードをスキップ")
        return

    if not entries:
        return

    rows = []
    for e in entries:
        row = [str(e.get(h, "")) for h in THOUGHT_LIBRARY_HEADERS]
        rows.append(row)

    print(f"[API START] Google Sheets thought_library シード投入 ({len(rows)}件)")
    try:
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"[API END] Google Sheets thought_library シード投入完了")
    except Exception as e:
        print(f"[API TIMEOUT] thought_library シード投入失敗: {e}")
