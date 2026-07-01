# Instagram リール分析自動化（CORE HARI FACE向け）

このツールの目的は「Instagramの投稿を取得すること」ではなく、
**「Instagram全体で伸びている投稿を毎日分析し、CORE HARI FACEの集客につながる投稿案を自動生成すること」**です。

CORE HARI FACE（札幌のフェイシャルエステサロン。顔トレ・小顔フェイシャル・表情筋トレーニング・たるみ改善が専門）のSNS運用のために、Instagramで実際に伸びているリールをジャンル不問で収集・分析し、CORE HARI FACE向けの投稿案に変換します。

## アンテナアカウントは完全自動で増える（2026-06-29: 設計変更・2回目）

Instagram自体が「全体トレンド」を取得できる公開APIを提供していないため、Bright Data・Apifyいずれを使っても、ハッシュタグやキーワードだけを起点に未知の投稿をInstagram全体から無条件に発見することはできません（調査の詳細は後述）。そのため、何らかの起点アカウントは依然として必要ですが、目的は「Instagram全体で伸びている投稿を毎日分析すること」であり、**日々の人の判断作業はできる限り無くしたい**ため、以下の完全自動フローでアンテナアカウントを増やす構成にしています（人による「採用/除外」の手入力は不要です）。

1. `accounts.py` の `ANTENNA_ACCOUNTS`（ジャンル不問の起点アカウント）からBright Dataでリールを取得する
2. 取得した投稿のキャプションから `@メンション` を抽出する（`candidate_discovery.py`）
3. ある候補アカウントが、複数の異なるアンテナアカウントから言及されている場合（`accounts.AUTO_PROMOTE_MIN_SOURCE_ACCOUNTS` 件以上。**1回の実行内だけでなく、`account_mention_tracker` シートで複数回の実行をまたいで累積カウントする**）、人の承認なしに自動的に `accounts.py` の `ANTENNA_ACCOUNTS` に追記される（`accounts_writer.add_accounts`。`main.py` が実行ごとに自動で呼ぶ）
4. 自動追加されたアカウントは `auto_added_accounts` シートに履歴として記録される（ログ目的。ユーザーの操作は不要）
5. しきい値未満の候補は `account_mention_tracker` シートに記録され、次回以降の実行で言及元アカウントが積み上がればしきい値到達時に自動追加される

この自動拡張フローは `main.py` の日次実行に完全に含まれています（手動で別スクリプトを実行する必要はありません。旧 `sync_adopted_accounts.py` は廃止しました）。

自動追加されたアカウントが明らかに無関係だった場合のみ、ユーザーが `accounts.py` の `BLOCKED_ACCOUNTS` にユーザー名を**まれに**追加し、`ANTENNA_ACCOUNTS` から該当行を削除してください。これは日次の判断作業ではなく、気づいたときに行う程度の低頻度メンテナンスです。`BLOCKED_ACCOUNTS` に入れておくと、今後同じアカウントが候補に挙がっても自動追加されなくなります。

`ANTENNA_ACCOUNTS` はジャンルを問いません（美容・エンタメ・お笑い・ライフスタイル・グルメ・バズ系など）。ジャンルを横断して観測すること自体が目的のため、美容ジャンルだけに絞らないようにしてください。初期値は、以前の美容競合アカウント・Instagram全体トレンド観測用アカウントを1つのリストに統合したものです。

## Bright Dataだけで「Instagram全体のトレンド取得」は可能か（調査結果）

2026-06-29に公式ドキュメント（docs.brightdata.com）を調査した結果は以下の通りです。

- Bright Data Instagram Scraper API（ライブAPI）は Profiles / Posts / Reels / Comments の4種類のみで、**いずれも既知のInstagram URL（プロフィールまたは投稿）を入力として必要とします。** ハッシュタグやキーワードから未知のアカウント・投稿を新規発見する機能はありません。
- Bright Dataには「Instagram Hashtag Datasets」というマーケットプレイス型の事前収集データセットもありますが、こちらは**最低注文10万件・$250〜**のバルク購入製品であり、「今まさに伸びている投稿」をオンデマンドかつ低コストで取得する用途には適していません。
- Apify（旧構成）のハッシュタグスクレイパーも、実際には「ハッシュタグ」という起点が必要であり、本当の意味で無条件にInstagram全体を発見していたわけではありませんでした。

結論として、**外部サービスを問わず「起点ゼロでInstagram全体を発見する」ことはプラットフォーム的に不可能**です。そのため、「起点アカウントからの自動拡張（人の承認なしの自動採用）」を、目的を変えずに追加コストを抑えて毎日安定動作する代替構成として採用しています。

## プール条件とResearch Candidate Scoreによるランキング（2026-06-30: 採用/不採用の二値フィルタを廃止）

以前は再生数100,000回以上・再生倍率1.0以上などの条件を満たさない投稿を「不採用」として丸ごと捨てていましたが、実際の運用ログで取得27件中採用0件という問題が発生したため、この二値フィルタ自体を廃止しました。現在は「構造的に使えないデータ」だけを除外し、それ以外は全件をResearch Candidate Scoreでスコアリングして高得点順に並べる方式です（`bright_data_fetcher.build_post_pool`）。

`accounts.py` に記載されたアカウントの直近リールを取得したうえで、以下のいずれかに該当する投稿のみを除外します（構造的に分析に使えないデータのみ）。

| # | 除外条件 |
|---|---|
| 1 | Bright Dataが取得失敗・空データを返した |
| 2 | リールではない |
| 3 | 投稿日が直近20日（`RECENT_DAYS`）より前 |

再生数・再生倍率・フォロワー数の有無は、もはや除外条件ではありません。これらはResearch Candidate Scoreの点数（0〜100点、7要素）に反映され、点数が低い投稿は自然に分析対象から外れる仕組みに統一されています。フォロワー数が取得できない投稿も除外せず、再生倍率の項目を0点扱いにするだけで残します。

除外された投稿を含む取得データ全件（URL・投稿日・再生数・いいね数・フォロワー数・再生倍率・除外理由）は、`raw_fetch_log` シートに毎回保存されます。フィルター前の生データを確認したい場合はこのシートを見てください。

AI分析（個別分析・集約分析）に進める投稿は、Research Candidate Scoreが`ANALYSIS_MIN_SCORE`（80点）以上の投稿の中から、スコア上位`TOP_N_FOR_ANALYSIS`（5件）に絞られます（`research_candidate_score.select_for_analysis`）。2026-07-05に、ユーザー要望「研究対象として価値がある投稿だけをAI分析対象にしてほしい」に対応してこのしきい値ゲートを復活させました（しきい値以上の投稿が無い日は、その日の個別AI分析は0件になります。これはエラーではなく想定内の挙動です）。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `main.py` | 実行のエントリーポイント。全体の処理フローを管理する |
| `accounts.py` | **【現行】** 取得対象アカウント（`ANTENNA_ACCOUNTS`、ジャンル不問）と、自動追加のしきい値（`AUTO_PROMOTE_MIN_SOURCE_ACCOUNTS`）・除外リスト（`BLOCKED_ACCOUNTS`）を管理するファイル |
| `bright_data_fetcher.py` | **【現行】** Bright Dataで各アカウントのリールを取得し、リール判定と構造的な除外判定（取得失敗/リール以外/投稿日）のみを行う（`build_post_pool`）。再生数・再生倍率による採用/不採用判定は廃止 |
| `candidate_discovery.py` | **【現行】** 取得済み投稿のキャプションから新しいアンテナアカウント候補を抽出し、自動追加するか・累積トラッカーに記録するかを判定する（`classify_candidates`） |
| `accounts_writer.py` | **【現行】** 自動追加が決まった候補を、実際に `accounts.py` の `ANTENNA_ACCOUNTS` に追記するファイル書き込みユーティリティ。`main.py` が実行ごとに自動で呼ぶ |
| `openai_analyzer.py` | OpenAIで集約分析（`analyze_category_trend`）と投稿単位の個別分析（`analyze_post_structure` → `generate_core_hari_idea` → `analyze_success_factors` → `generate_pattern_lab_content`）を行う |
| `prompts.py` | OpenAIに渡すプロンプトを組み立てる |
| `sheets_writer.py` | Googleスプレッドシートへの保存処理（シート自動作成・ヘッダー管理） |
| `config.py` | `.env` から設定値を読み込み・検証する |
| `requirements.txt` | 必要なPythonパッケージ一覧 |
| `.env.example` | `.env` のテンプレート |
| `competitor_discovery.py` | 【バックアップ】以前Instagram全体から競合・参考アカウントを自動発見していたモジュール（Apifyのハッシュタグ検索を使用）。`main.py`からは呼ばれていない |
| `apify_fetcher.py` | 【バックアップ】以前リール取得に使っていたApify版。`main.py`からは呼ばれていないが、削除せず残している |
| `competitors.xlsx` | 過去にApifyのハッシュタグ検索で自動発見していた競合候補リスト（参考資料・現在は更新されない） |

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. `.env` の作成

`.env.example` をコピーして `.env` を作成し、実際の値を入力します。

```bash
cp .env.example .env
```

| 変数名 | 内容 |
|---|---|
| `OPENAI_API_KEY` | OpenAIのAPIキー |
| `BRIGHT_DATA_API_KEY` | Bright DataのAPIキー（リール取得・`bright_data_fetcher.py`が使用） |
| `GOOGLE_SHEET_ID` | 出力先のGoogleスプレッドシートID |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | サービスアカウントJSONファイルのパス（例: `service_account.json`） |

`APIFY_API_TOKEN` は不要です（`config.py`では読み込みません）。取得対象アカウントを変更したい場合は `.env` ではなく `accounts.py` の `ANTENNA_ACCOUNTS` を直接編集してください（通常は前述の自動拡張フローで増えていくため、手動編集は初期セットアップ時や `BLOCKED_ACCOUNTS` のメンテナンス時のみで構いません）。

### 3. Googleスプレッドシートの共有設定

サービスアカウントのメールアドレス（`service_account.json` 内の `client_email`）を、出力先のスプレッドシートに「編集者」として共有しておいてください。

## 実行方法

### 日次の分析実行

```bash
python3 main.py
```

実行すると、以下の流れで処理が進みます。

1. `accounts.py` の `ANTENNA_ACCOUNTS` を読み込む
2. 各アカウントの直近リールをBright Data（Reels - Discover by URL）で取得し、構造的に使えない投稿（取得失敗/リール以外/投稿日が古い）だけを除外してプールを作る（`build_post_pool`。再生数・再生倍率による採用/不採用判定は廃止）
3. フィルター前の取得投稿全件（除外理由付き）を `raw_fetch_log` シートに保存する
4. 取得した投稿（プールで絞る前の全件）のキャプションから新しいアンテナアカウント候補を抽出し、複数のアンテナアカウントから累積で言及されたものは人の承認なしに自動で `accounts.py` の `ANTENNA_ACCOUNTS` に追記する（`auto_added_accounts` シートにログを記録）。しきい値未満の候補は `account_mention_tracker` シートに記録し、次回以降の実行に持ち越す
5. プール対象の投稿（構造的に使える全件）をResearch Candidate Score（0〜100点）でスコアリングし、点数順に並べてスプレッドシートに保存（`research_candidates`。2026-07-05に`trend_posts`からリネーム）。各投稿の配点内訳（生値+得点）も `research_candidate_score_debug` に保存する（2026-07-01追加。2026-07-05に`trend_score_debug`からリネーム。下記「research_candidate_score_debug シート」参照）
6. ランキングシートを作成（`Instagram全体トレンドTOP20` / `再生倍率TOP20` / `保存率TOP20`）
7. Research Candidate Scoreが`ANALYSIS_MIN_SCORE`（80点）以上の投稿の中から、スコア上位`TOP_N_FOR_ANALYSIS`（5件）について、投稿ごとに個別にAI分析・投稿案・成功要因分析・SNS Pattern Lab投稿素材を生成し、`post_analysis` / `core_hari_ideas` / `success_factors` / `content_carousel` / `content_reels` / `content_threads` / `content_caption` に保存する（2026-07-01(2回目): `success_factors` 追加。2026-07-01(3回目): SNS Pattern Lab投稿素材生成を追加。1投稿あたりのOpenAI呼び出しは2回→3回→4回に増加。2026-07-05: しきい値ゲートを復活させ、対象が0件の日は個別分析をスキップ）
8. プール対象のリール群をOpenAIに集約分析させ、`trend_analysis` に保存
9. 取得件数・除外件数・プール件数のログを表示

このフローはすべて `main.py` 1回の実行内で完結し、人の追加操作（候補の採用/除外入力や別スクリプトの実行）は不要です。

## 保存される分析項目（投稿ごと）

プール対象になった投稿（構造的に使える全件）について、以下を `research_candidates` シート（2026-07-05に`trend_posts`からリネーム）および各ランキングシートに保存します。

投稿URL / 投稿日 / 再生数 / いいね数 / コメント数 / 保存数（取得できる場合） / シェア数（取得できる場合） / フォロワー数 / 再生倍率（再生数÷フォロワー数） / 動画尺 / キャプション全文 / 使用ハッシュタグ / 投稿ジャンル

## research_candidate_score_debug シート（配点内訳の確認用、2026-07-01追加。2026-07-05に`trend_score_debug`からリネーム）

`research_candidates` シートにはResearch Candidate Scoreの合計と項目別の「得点」しか出ないため、「再生数が何回だったから何点になったのか」を確認できませんでした。`research_candidate_score_debug` シートには、プール対象の投稿全件について、各評価項目の**生値**と**得点**をセットで保存します。

実行日時 / 投稿URL / 投稿者 / Research Candidate Score合計 / 判定 / 再生数 / 再生数の得点 / フォロワー数 / 再生倍率 / 再生倍率の得点 / いいね数 / いいね率 / いいね率の得点 / コメント数 / コメント率 / コメント率の得点 / 投稿日 / 投稿からの日数の得点 / 動画尺(秒) / 動画時間の得点 / 投稿頻度（取得窓内の同アカウント投稿数） / 投稿頻度の得点

「`ANALYSIS_MIN_SCORE`（80点）以上が0件だった」場合は、このシートで各項目の生値と得点を確認し、`research_candidate_score.py` の `_score_views` / `_score_view_multiplier` / `_score_like_rate` / `_score_comment_rate` / `_score_recency` / `_score_duration` / `_score_post_frequency` の各しきい値を調整してください。

## AI分析項目（集約分析）

`trend_analysis` シートには、1回の実行につき1行、以下の項目がOpenAIによって生成されます。投稿1件ごとの分析ではなく、プール対象のリール群全体をまとめた分析です。

最初3秒のフック / 伸びた理由 / 構成 / 編集・テロップの特徴 / テーマ・切り口 / CTA / 使われている心理テクニック / 共通点 / CORE HARI FACEへ応用できるポイント / 30秒版投稿案 / 60秒版投稿案 / Threads投稿案 / タイトル案10個 / 冒頭フック10個

## AI分析項目（投稿単位の個別分析、2026-06-29 追加）

Research Candidate Scoreが`ANALYSIS_MIN_SCORE`（80点）以上かつスコア上位`TOP_N_FOR_ANALYSIS`（5件）の投稿については、`post_analysis` シートに投稿ごとに1行、以下の項目が個別に生成されます。複数投稿をまとめる前提の「共通点」は個別分析では意味が無いため除いています。

最初3秒のフック / 伸びた理由 / 構成 / 編集・テロップの特徴 / テーマ・切り口 / CTA / 使われている心理テクニック / CORE HARI FACEへ応用できるポイント / 30秒版投稿案 / 60秒版投稿案 / Threads投稿案 / タイトル案5個 / 冒頭フック5個

1回の実行でOpenAI呼び出しは「集約分析1回＋個別分析（構造分析＋投稿案生成＋成功要因分析＋SNS Pattern Lab素材生成の4回）×最大`TOP_N_FOR_ANALYSIS`（5件、`research_candidate_score.py`）」の合計最大21回になります（2026-07-01(2回目): 成功要因分析の追加により個別分析が1件あたり2回→3回に増加。2026-07-01(3回目): SNS Pattern Lab投稿素材生成の追加により3回→4回に増加。2026-07-05: 旧`MAX_ANALYZED_POSTS_PER_RUN`(10件)は廃止され、`ANALYSIS_MIN_SCORE`(80点)以上の投稿の中から固定で上位5件を選ぶ方式に統一されました。しきい値以上が0件の日は個別分析・集約分析以外のOpenAI呼び出しは発生しません）。

## AI分析項目（成功要因分析、2026-07-01(2回目) 追加）

Research Candidate Scoreが`ANALYSIS_MIN_SCORE`（80点）以上かつスコア上位`TOP_N_FOR_ANALYSIS`（5件）の投稿については、`post_analysis` / `core_hari_ideas` とは別に、`success_factors` シートにも投稿ごとに1行、以下の項目が個別に生成されます。Research Candidate Score（数値配点）とは別の切り口でAIに分析させる、独立した3つ目のOpenAI呼び出しです（`post_analysis` の内容と一部重複しますが、ユーザーの選択により既存の分析は置き換えず、新規の分析として追加しました）。

なぜ伸びたか / 冒頭3秒のフック / 構成 / CTA / 心理トリガー（社会的証明・限定性/緊急性・権威・ザイガニク効果・FOMO・損失回避・共感・ビフォーアフター対比など具体的なテクニック名で記述） / CORE HARI FACEへの応用方法

## SNS Pattern Lab投稿素材（2026-07-01(3回目) 追加）

`success_factors` と同じ対象投稿（Research Candidate Scoreが`ANALYSIS_MIN_SCORE`(80点)以上かつスコア上位`TOP_N_FOR_ANALYSIS`(5件)）について、その成功要因分析結果のみを入力に、顔出し不要の匿名ブランド**「SNS Pattern Lab」**として発信できる投稿素材一式をAIが生成します。元投稿の文章はそのまま使わず、型として言語化したものです（`post_analysis` / `core_hari_ideas` の結果は入力に使いません）。

コストを抑えるため、21項目すべてを1回のOpenAI呼び出しでまとめて生成し（`openai_analyzer.generate_pattern_lab_content`）、保存先のみ出力タイプごとに4シートへ分けています。

### content_carousel シート（Instagramカルーセル投稿案、10枚分）

実行日時 / 投稿URL / 投稿者 / Research Candidate Score / 判定 / カルーセル1_タイトル / カルーセル2_投稿概要 / カルーセル3_伸びた理由 / カルーセル4_冒頭フック / カルーセル5_心理トリガー / カルーセル6_他ジャンルへの応用 / カルーセル7_美容サロンへの応用 / カルーセル8_今日使える投稿例 / カルーセル9_まとめ / カルーセル10_CTA

7枚目（美容サロンへの応用）のみCORE HARI FACE/美容ジャンルに触れる内容で、他の9枚はジャンルを問わず使える一般化した内容にしています。

### content_reels シート（リール台本）

実行日時 / 投稿URL / 投稿者 / Research Candidate Score / 判定 / リール台本_冒頭3秒 / リール台本_本文 / リール台本_テロップ / リール台本_ナレーション / リール台本_CTA

### content_threads シート（Threads投稿案）

実行日時 / 投稿URL / 投稿者 / Research Candidate Score / 判定 / Threads短文1 / Threads短文2 / Threads短文3 / Threads解説

短文3本＋やや詳しい解説1本の構成です。

### content_caption シート（キャプション）

実行日時 / 投稿URL / 投稿者 / Research Candidate Score / 判定 / キャプション_Instagram用 / キャプション_サブスク誘導用

## ランキングシート

- `Instagram全体トレンドTOP20`：プール対象のリールを再生数順に最大20件
- `再生倍率TOP20`：プール対象のリールを再生倍率順に最大20件
- `保存率TOP20`：保存数が取得できたプール対象リールのみを保存率順に最大20件（保存数が1件も取得できなかった場合はシート自体を作成しません）

## auto_added_accounts シート（自動追加の履歴ログ）

| 列 | 内容 |
|---|---|
| 追加日時 | このアカウントが `ANTENNA_ACCOUNTS` に自動追加された日時 |
| ユーザー名 | 追加されたアカウントのユーザー名 |
| 累積言及元アカウント数 | 追加時点で何件の異なるアンテナアカウントから言及されていたか |
| 言及元アカウント(累積) | 言及していたアンテナアカウントの一覧 |
| 参考ハッシュタグ | 言及元投稿で使われていたハッシュタグの例 |
| サンプルキャプション | 言及元投稿のキャプション抜粋 |

記録のみが目的のログであり、ユーザーの操作は不要です。

## account_mention_tracker シート（しきい値未満の候補を累積カウントするワーキングシート）

| 列 | 内容 |
|---|---|
| ユーザー名 | 候補アカウントのユーザー名 |
| 初回検出日時 | この候補が最初に検出された日時 |
| 最終検出日時 | 直近で言及が確認された日時 |
| 累積言及元アカウント数 | これまでに言及していた異なるアンテナアカウントの累積数 |
| 言及元アカウント(累積) | 言及していたアンテナアカウントの一覧(累積) |
| 直近サンプルキャプション | 直近の言及元投稿のキャプション抜粋 |
| 直近参考ハッシュタグ | 直近の言及元投稿で使われていたハッシュタグの例 |

`accounts.AUTO_PROMOTE_MIN_SOURCE_ACCOUNTS`（既定2件）に達すると、このシートから削除され、`ANTENNA_ACCOUNTS` に自動追加されます。ユーザーがこのシートを直接編集する必要はありません。

プロフィール文（bio）は取得していません（追加コストを抑えるため）。キャプション本文の `@メンション` のみを手がかりにしています。

## 実行ログ

実行の最後に、以下を表示します。

取得件数 / 取得失敗件数（Instagramにブロックされた可能性） / リール以外で除外件数 / 投稿日で除外件数 / フォロワー数未取得件数（除外はせず再生倍率0点扱い） / Research Candidate Scoreの対象プール件数

「取得失敗件数」は、Bright Dataが投稿データそのものを返せず、エラー/警告情報だけを返してきた件数です（非公開アカウント・削除済み投稿などで発生）。「リール以外で除外件数」（実際に投稿は取得できたがリールではなかった件数）とは別に集計しています。

バッチ（アカウント）ごとのsnapshot取得時には、上記とは別に `取得件数 / 解析件数 / 解析失敗件数 / レスポンス構造` をログに表示します（2026-07-01追加）。「レスポンス構造」は `list`（レスポンス自体がリスト） / `dict.data`・`dict.items`・`dict.results`・`dict.snapshot` など（dictの中の既知キーにリストがあった） / `dict.single_item`（投稿1件分のdictがそのまま返ってきた） / `dict.error`（エラーレスポンス） / `unknown`（解釈不能）のいずれかです。`unknown` になった場合や想定外の事象が起きた場合は、Bright Data snapshot APIの生レスポンスがプロジェクト直下の `debug_snapshot.json` に毎回上書き保存されているので、そこで実際の構造を確認できます。

## エラーが出たときの確認ポイント

- `設定エラー: .envに以下の項目が設定されていません: ...`
  → `.env` に該当の項目が入力されていません。`.env.example` を参考に入力してください。
- `Instagram全体トレンド: accounts.pyにアカウントが0件のため、この実行ではリール取得をスキップします`
  → `accounts.py` の `ANTENNA_ACCOUNTS` が空になっています。取得したいアカウントのユーザー名を追加してください。
- 投稿の取得中にエラー
  → `BRIGHT_DATA_API_KEY` が正しいか、Bright Dataの利用上限・契約状態を確認してください。また `bright_data_fetcher.py` 内の `REELS_DATASET_ID`（`gd_lyclm20il4r5helnj`）が、契約しているデータセットとして使えるIDになっているかも確認してください。
- 「取得失敗件数」が0件より多い、または「全件が取得失敗でした」と表示される
  → 非公開アカウント・削除済み投稿・Bright Data側の収集失敗などで発生します。コード側の不具合ではない場合がほとんどです。Bright Dataの管理画面でsnapshot/jobのログを確認してください。
- `main.py` を実行すると `EnvironmentError: BRIGHT_DATA_API_KEYが設定されていません` のようなエラーが出る
  → `.env` に `BRIGHT_DATA_API_KEY` を追加してください（`.env.example` 参照）。
- 集約分析の作成中にエラー
  → `OPENAI_API_KEY` が正しいか、OpenAIの利用上限に達していないかを確認してください。
- スプレッドシート保存中にエラー
  → サービスアカウントがスプレッドシートに「編集者」として共有されているか、`GOOGLE_SHEET_ID` が正しいかを確認してください。
- `main.py` 実行中に「accounts.py内に自動追加用のマーカーコメントが見つかりませんでした」と表示される
  → `accounts.py` 内のコメント行（`# --- ここから下: ... ---`）が削除・変更されています。コメント行を復元するか、表示されたユーザー名を手動で `ANTENNA_ACCOUNTS` に追記してください。

## 過去の変更履歴

### 2026-07-05: Trend Score → Research Candidate Scoreへのリネーム + AI分析しきい値ゲートの復活

ユーザー要望「Trend Scoreを廃止してResearch Candidate Scoreを追加してほしい。研究対象として価値がある投稿だけをAI分析対象にしてほしい」に対応しました。

- `trend_score.py` → `research_candidate_score.py`、`trend_posts`シート → `research_candidates`シート、`trend_score_debug`シート → `research_candidate_score_debug`シートにリネームしました。採点項目・配点（再生数10点・再生倍率30点・いいね率15点・コメント率15点・投稿からの日数10点・動画時間10点・投稿頻度10点=100点）自体は変更していません。
- AI個別分析に進める投稿の選定を、`ANALYSIS_MIN_SCORE`（80点）以上の投稿の中からスコア上位`TOP_N_FOR_ANALYSIS`（5件）を選ぶ方式に変更しました。以前（2026-07-02、当時は本READMEに未反映）は「フィルタなしで常に上位5件」という方式でしたが、低スコアの投稿しか無い日にもAI分析が走ってしまうため、しきい値ゲートを復活させました。しきい値以上の投稿が無い日は、その日の個別AI分析は0件になります（エラーではなく想定内の挙動です）。
- 旧`trend_posts`/`trend_score_debug`タブは過去の実行データとしてシートは残りますが、これ以降の実行では新しいシート名（`research_candidates`/`research_candidate_score_debug`）に書き込まれます。

### 2026-07-01(4回目): SNS Pattern Lab投稿素材生成を追加

ユーザーから「分析結果から、顔出し不要の匿名ブランド『SNS Pattern Lab』として発信できる投稿素材を自動生成したい」との要望があり、個別AI分析の4つ目のOpenAI呼び出しとして `generate_pattern_lab_content` を追加しました。設計上の論点が3つあったため、ユーザーに確認した上で以下の方針に決定しています。

- **呼び出し構成**：コストを抑えるため、21項目（カルーセル10枚＋リール台本5項目＋Threads4項目＋キャプション2項目）すべてを1回のOpenAI呼び出しでまとめて生成する方式にしました（分割呼び出しではない）。
- **入力データ**：成功要因分析（`success_factors`）の結果のみを入力にしました（`post_analysis` / `core_hari_ideas` の結果は使いません）。
- **対象範囲**：既存の個別分析対象と同じ投稿全件（Trend Score80点以上、最大`MAX_ANALYZED_POSTS_PER_RUN`件）に対して行います。

生成結果は出力タイプごとに `content_carousel` / `content_reels` / `content_threads` / `content_caption` の4シートに分けて保存します（詳細は上記「SNS Pattern Lab投稿素材」参照）。1投稿あたりのOpenAI呼び出しは3回→4回に増加しました。

### 2026-07-01(3回目): Trend Scoreの再生数・再生倍率を段階評価に変更（小規模アカウント対応）

`trend_score_debug` シートで実データを確認した結果、「再生数10万未満は一律0点」「再生倍率1.0未満は一律0点」という設計だと、絶対的な再生数は少なくてもフォロワー数に対する伸び（再生倍率）が高い小規模アカウントの成功事例が正当に評価されない問題がありました。対応として以下を変更しました。

- `_score_views`：10万再生未満を一律0点にしていた閾値を撤廃し、1,000再生以上から段階的に加点する設計に変更（満点20点→10点）。
- `_score_view_multiplier`：倍率1.0未満を一律0点にしていた閾値を撤廃し、倍率0より大きければ段階的に加点する設計に変更（満点20点→30点）。
- 「再生倍率を重視してほしい」という要望に対応し、配点の合計100点は変えずに再生数から10点を再生倍率に移しました。フォロワー規模に対する伸びを、絶対的な再生数より重い指標として扱います。
- AI分析実行のしきい値（Trend Score 80点以上、`ANALYSIS_MIN_SCORE`）自体は今回変更していません。配点変更後も生値と得点の関係は `trend_score_debug` シートで確認できます。

### 2026-07-01(2回目): Sheets書き込みの一括化（429エラー対策）+ trend_score_debug追加

実運用でGoogle Sheets APIの書き込みリクエスト数上限を超え、429エラーが発生しました。原因は、`sheets_writer.py` の各保存関数が「投稿1件ごとに1回書き込みリクエスト（`append_row`）」をループしていたことです。対応として、すべての保存関数を「全件まとめて1回のリクエスト（`append_rows`）」に変更しました。`account_mention_tracker` の既存行更新のみ、複数range更新を1リクエストにまとめる `batch_update` に変更しています。

また、「25件取得したのにTrend Score80点以上が0件だった」という報告を受け、各投稿の評価項目の生値（再生数・フォロワー数・再生倍率・いいね率・コメント率・投稿日など）と得点をセットで確認できる `trend_score_debug` シートを追加しました（詳細は上記「trend_score_debug シート」参照）。

### 2026-07-01: Bright Data snapshotのレスポンス解析を堅牢化

実運用で「Bright Data snapshotのレスポンス形式が想定外でした（リストではない）」というログが出て取得0件になる問題が発生しました。原因は、snapshot APIのレスポンスが常に「投稿のdictがそのまま並んだリスト」である前提でコードを書いていたことです。実際の構造を確認する手段が無かったため、対応として以下を実装しました。

- snapshot APIの生レスポンスを毎回 `debug_snapshot.json`（プロジェクト直下）に上書き保存するようにしました。同種の事象が起きた際は、このファイルで実際の構造を確認できます。
- レスポンスが `data` / `items` / `results` / `snapshot` / `result` / `rows` のいずれかのキーでdictにラップされていても対応できるようにしました。未知のキー名の場合は、dict内で最初に見つかったリストを使うフォールバックも追加しています。
- リストが見つからない場合は、`error`/`warning` キーの有無でエラーレスポンスか「投稿1件分のdict」かを判別し、後者であれば1件として扱うようにしました。
- バッチごとに `取得件数 / 解析件数 / 解析失敗件数 / レスポンス構造` をログへ出力するようにしました（詳細は「実行ログ」セクション参照）。

### 2026-06-30: 採用/不採用の二値フィルタを廃止し、Trend Score順位方式に統一

実運用で取得27件中、再生数条件で25件・投稿日で1件が除外され、採用0件になる問題が発生しました。原因は `MIN_VIEWS`（再生数10万回以上）・再生倍率1.0以上・フォロワー数必須という条件が厳しすぎたことでした。閾値を緩めるだけの対応ではなく、二値フィルタの設計自体を以下のように変更しました。

- `filter_and_adopt` を廃止し、`build_post_pool` に置き換えました。除外するのは「取得失敗」「リール以外」「投稿日が古い」という構造的に使えないデータのみです。再生数・再生倍率・フォロワー数の有無はもう除外条件にせず、Trend Scoreの点数（既存の7要素のうち再生数20点・再生倍率20点）にそのまま反映させ、低スコアの投稿は自然にランキング下位になる方式にしました。
- フィルター前の取得投稿全件（除外理由付き）を `raw_fetch_log` シートに常時保存するようにしました。URL・投稿日・再生数・いいね数・フォロワー数・再生倍率・除外理由を確認できます。
- AI分析対象の選定（Trend Score 80点以上・上限件数以内）は既に点数順だったため変更していません。今回の変更は、その手前の「プール作成」段階にあった二値フィルタを除去したものです。

### 2026-06-29: 候補アカウントの人による採用判断を廃止し、投稿単位の個別AI分析を追加（設計変更・2回目）

目的は「Instagram全体で伸びている投稿を毎日分析し、CORE HARI FACEの投稿案を自動生成すること」であり、日々の人の判断作業はできる限り無くしたいというフィードバックを受けて、以下のように変更しました。

- `candidate_accounts` シート＋人による「採用/除外」手入力＋`sync_adopted_accounts.py`（手動実行）という半自動フローを廃止しました。
- 代わりに、複数の異なるアンテナアカウントから累積で言及された候補（`accounts.AUTO_PROMOTE_MIN_SOURCE_ACCOUNTS` 件以上）を、人の承認なしに自動で `ANTENNA_ACCOUNTS` に追加する方式にしました（`candidate_discovery.classify_candidates` → `accounts_writer.add_accounts`）。1回の実行内だけでなく、複数回の実行をまたいで累積カウントするため、新たに `account_mention_tracker` シート（累積カウント用）と `auto_added_accounts` シート（追加履歴ログ）を追加しました。
- 自動追加されたアカウントが明らかに無関係だった場合のみ、`accounts.py` の `BLOCKED_ACCOUNTS` にユーザーがまれに追記する運用とし、日次の判断作業とは明確に分離しました。
- 採用された上位5件（再生数順）について、投稿ごとに個別のAI分析・投稿案生成（`openai_analyzer.analyze_single_post`）を追加し、`post_analysis` シートに保存するようにしました。既存の集約分析（カテゴリ全体をまとめた `trend_analysis`）はそのまま維持しています。
- `sync_adopted_accounts.py` は削除しました（ファイル追記のロジックは `accounts_writer.py` に引き継いでいます）。

### 2026-06-29: 美容競合分析ツールから「Instagram全体トレンド分析ツール」への設計変更

目的が「美容競合の分析」ではなく「Instagram全体で伸びている投稿を毎日分析すること」であるため、以下のように変更しました。

- 美容ジャンル／Instagram全体トレンドの2カテゴリ運用を単一カテゴリ（`Instagram全体トレンド`）に統合しました。
- `accounts.py` の `BEAUTY_ACCOUNTS` / `GENERAL_ACCOUNTS` を、ジャンル不問の `ANTENNA_ACCOUNTS` 1本に統合しました。
- 競合アカウントの手動管理に依存しすぎないよう、`candidate_discovery.py` / `sync_adopted_accounts.py` による半自動のアカウント候補発見フローを追加しました（前述）。
- AI分析項目に「編集・テロップの特徴」「テーマ・切り口」を追加しました。
- 旧シート（`beauty_reels` / `general_reels` / `美容ジャンルTOP20`）は過去の実行データとして残りますが、これ以降の実行では作成されません。新しいシートは `reels` / `Instagram全体トレンドTOP20` です。

### 2026-06-29: リール取得をApifyからBright Dataに切り替え

リール/プロフィール取得（フォロワー数・再生数・投稿日などの取得）を、Apify(`apify_fetcher.py`)からBright Data(`bright_data_fetcher.py`)に切り替えました。

- **リール取得には Bright Data の「Reels - Discover by URL」を使用します。**（dataset_id: `gd_lyclm20il4r5helnj`、`type=discover_new&discover_by=url`）。このAPIのレスポンスにはフォロワー数（`followers`）がリールごとに含まれているため、Apify版で必要だった「プロフィール取得→リール取得」の2段階呼び出しが不要になりました。
- `apify_fetcher.py` は削除せず、バックアップとして残しています。

### 2026-06-29: Apifyを完全停止し、Bright Dataのみで動作する構成に変更

ハッシュタグ検索による競合アカウント自動発見（`competitor_discovery.py`、Apify使用）を完全に停止しました。

- `main.py` から `competitor_discovery.py` の呼び出しを削除しました。
- `config.py` から `APIFY_API_TOKEN` の読み込みと、`validate_config()` の必須項目チェックを削除しました。
- `apify_fetcher.py` / `competitor_discovery.py` はファイルとしては削除せず残していますが、`main.py` を含むどの実行経路からもimportされていません。Apifyへの通信は発生しません。

### 2026-06-29: 大量取得によるタイムアウト対策（バッチ分割・テストモード）

1回のBright Dataジョブに全アカウント・全投稿を詰め込んでいたため、ジョブが600秒でタイムアウトする問題が発生しました。**目的は大量取得ではなく「毎日安定して集客に使える投稿案を作ること」**のため、以下のように安定性優先の構成に変更しました。

- **1ジョブあたり最大 `ACCOUNTS_PER_BATCH`（5）アカウントまで** に分割して取得します。
- **1アカウントあたりの取得件数は `DEFAULT_RESULTS_PER_ACCOUNT`（8件）** に縮小しました（5〜10件の範囲）。
- **1バッチの待ち時間（`POLL_TIMEOUT_SEC`）は120秒** に短縮しました。120秒を超えたら、そのバッチだけスキップして次のバッチに進みます（プログラム全体は止まりません）。
- どのバッチ（アカウント）が失敗・タイムアウトしたかをログに出力します（`取得失敗(ジョブ失敗/タイムアウト)したアカウント: ...`）。
- **`TEST_MODE = True`（初期設定）の間は、1回の実行で `TEST_MODE_MAX_TOTAL_ACCOUNTS`（5）アカウントまでしか取得しません。** 安定して動くことを確認できたら、`bright_data_fetcher.py` の `TEST_MODE` を `False` に変更すれば、`accounts.py` に記載した全アカウントを取得対象にできます。

## 今後の改善余地・要確認事項

- **Bright Dataの「取得失敗アイテム」の正確な形（フィールド名）は実データでまだ検証できていません。** `bright_data_fetcher._is_error_item` は、公式ドキュメントに明記された失敗時のレスポンス例が見つからなかったため、`error`/`warning` キーの有無、または `url`/`user_posted`/`post_id` などの中核フィールドが欠落しているかどうかで保守的に判定する実装にしています（コード内コメントに明記）。実際の `BRIGHT_DATA_API_KEY` で実行し、非公開アカウントなどの失敗ケースのレスポンスを確認したら、このロジックを実データに合わせて調整してください。
- **アカウント候補の抽出は、現時点ではキャプション内の `@メンション` のみを手がかりにしています。** プロフィール文（bio）からの抽出が必要になった場合は、`candidate_discovery.py` の `extract_mentions()` を拡張点として、Bright DataのProfiles - Collect by URLを別途呼び出す処理を追加してください（追加コストが発生します）。
- **リール判定（`_is_reel`）は `product_type` / `video_url` / `video_play_count` の有無で判定しています。** Bright DataのReels APIはリールのみを返す想定ですが、念のためこの判定を残しており、リールと判定できない投稿は `build_post_pool` で除外します（`リール以外で除外件数` としてログに表示）。
- `bright_data_fetcher.py` の `DEFAULT_RESULTS_PER_ACCOUNT`（取得件数）・`ACCOUNTS_PER_BATCH`（バッチサイズ）・`TEST_MODE`（テストモード）で取得件数・範囲を調整できます。テストモードを解除する（`TEST_MODE = False`）と取得対象アカウント数が増えるため、まずはテストモードのまま安定動作を確認してから解除することを推奨します。
- 定期実行（スケジュール化）にも対応できる構成ですが、まずは手動実行で安定動作を確認してから自動化することを推奨します。
