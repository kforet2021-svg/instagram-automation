# CLAUDE.md — Creator Intelligence Platform

Claude Codeがこのプロジェクトで作業する際に必ず読む設定ファイルです。

> **最優先ルール**: 実装前に必ず [PROJECT_PRINCIPLES.md](PROJECT_PRINCIPLES.md) を参照すること。
> 設計で迷ったら「CORE HARI専用か、全業種で使える設計か」を問い直す。

---

## プロジェクトの目的

Instagramで伸びている投稿のパターンを自動収集・分析し、CORE HARI FACE（札幌の顔専門エステサロン：小顔矯正・顔筋トレーニング・たるみ改善）向けの投稿アイデアに変換するパイプライン。

**競合アカウント管理ではない。**ジャンル問わず伸びている投稿の構造・フック・CTAを抽出し、美容サロン向けに応用することが目的。

---

## ハードな制約（絶対に守る）

1. **`python3 main.py` 1コマンドで動くこと**。新しいエントリポイントを追加しない。
2. **OpenAI APIコストを最小化**する。新しいAI呼び出しを追加する前に必ずユーザーに確認。
3. **サンプル・ダミーデータをプロダクトコードに入れない**（検証スクリプトは別）。
4. **大規模リファクタリングは禁止**。1ステップずつ動作確認しながら進める。
5. **毎日の手動作業ゼロ**が設計目標。`accounts.BLOCKED_ACCOUNTS`だけが例外的な手動タッチポイント。

---

## 実装パターン（検証手順）

変更するたびに以下の順序で行う：

1. 該当モジュールを編集。モジュールdocstringに `【YYYY-MM-DD(N回目): 変更内容】` の節を追記。
2. `python3 -m py_compile <変更ファイル>.py` で構文確認。
3. スタブ使用のスモークテスト（`/tmp/` 以下に捨てスクリプト）。`openai`/`gspread`/`google-auth`/`dotenv`/`requests` はネットワーク不可の場合は `sys.modules` スタブで差し替え。`PYTHONPATH="$(pwd)"` を設定してから実行。
4. ユーザーへの簡潔な完了報告（中間ステップの詳細は不要）。

**スペック上の曖昧さは合理的に解釈して実装してよい**（ユーザーに許可済み）。AskUserQuestionは本当に判断不可能な矛盾・競合がある場合のみ使う。

---

## ファイル構成

```
main.py                        # エントリポイント（触る頻度高い）
accounts.py                    # ANTENNA_ACCOUNTS, BLOCKED_ACCOUNTS
bright_data_fetcher.py         # Bright Data 取得・プール構築・正規化
research_candidate_score.py    # Research Candidate Score（旧trend_score.py、2026-07-05リネーム）
openai_analyzer.py             # 全OpenAI呼び出し関数
prompts.py                     # 全プロンプト・定数
sheets_writer.py               # Google Sheets 書き込み（全て append_rows バッチ）
north_star_index.py            # North Star Index（0-100、OpenAIコストゼロ）
north_star_report.py           # North Star Daily Markdownファイル出力
knowledge_registry.py          # knowledge_library 重複排除ロジック
research_engine.py             # 互換シム（旧 → creator_intelligence/research/ への委譲）
candidate_discovery.py         # アンテナアカウント自動拡張
config.py                      # 環境変数・定数

creator_intelligence/
  research/
    base.py                    # ResearchProvider 抽象クラス
    engine.py                  # gather_evidence_for_post / build_evidence_summary_text
    providers/                 # 8つのスタブプロバイダ（現在は全て空リスト返却）
  knowledge/
    base.py                    # KnowledgeStore 抽象クラス（all/append/update）
    sheets_store.py            # SheetsKnowledgeStore（Sheets実装、DB移行時はここを差し替え）

reports/north_star_daily/      # YYYY-MM-DD.md（日次レポート）
```

---

## スコア・分析ゲートの現状（2026-07-05時点）

### Research Candidate Score（旧Trend Score）
- `research_candidate_score.py`（旧 `trend_score.py`）
- 7要素・100点満点：再生数10点、再生倍率30点、いいね率15点、コメント率15点、投稿からの日数10点、動画時間10点、投稿頻度10点
- **AI個別分析のゲート**：`ANALYSIS_MIN_SCORE = 80点`以上 かつ 上位`TOP_N_FOR_ANALYSIS = 5件`（`select_for_analysis`）
  - 80点以上が0件の日は個別分析が0件になる（エラーではない）
- Sheetsシート名：`research_candidates`（スコアランキング）、`research_candidate_score_debug`（配点内訳）

### North Star Index
- `north_star_index.py`（OpenAI呼び出しゼロ）
- 6要素：Discovery=15、Psychology=20、Trust=15、Education=15、Reproducibility=20、Momentum=15
- `post["research_candidate_score"]["breakdown"]` と `success_factors` テキストのみ使用
- 現状はコンソールログのみ（シート保存は未実装）

---

## 1実行あたりのOpenAI呼び出し数

- 個別分析（qualifying post 1件あたり4回）：`analyze_post_structure` + `generate_core_hari_idea` + `analyze_success_factors` + `generate_pattern_lab_content`
- 集約分析（カテゴリ別、1カテゴリあたり1回）：`analyze_category_trend`
- North Star Daily：1回/実行
- **合計最大21回**（集約2回 + 個別4回×5件）

---

## Sheetsシート一覧（現在）

| シート名 | 内容 |
|---|---|
| raw_fetch_log | 全取得投稿（除外理由含む）デバッグログ |
| reels | プール対象投稿 |
| research_candidates | Research Candidate Scoreランキング（旧trend_posts） |
| research_candidate_score_debug | 配点内訳（旧trend_score_debug） |
| post_analysis | 個別AI分析（構造分析） |
| core_hari_ideas | CORE HARI FACE投稿アイデア |
| success_factors | 成功要因分析（13フィールド） |
| content_carousel / content_reels / content_threads / content_caption | SNS Pattern Lab素材 |
| trend_analysis | 分析済み投稿ごとの行（上位5件/実行） |
| trend_analysis_summary | カテゴリ別集約分析（旧trend_analysis） |
| daily_content_picks | 今日の3投稿ピック |
| north_star_daily | North Star Dailyレポート（1行/実行） |
| knowledge_library | 成功パターンDB（重複排除済み） |
| success_patterns / psychology_patterns / hook_library / cta_library / research_sources | Creator Intelligence ライブラリ（ヘッダーのみ、未実装） |
| auto_added_accounts / account_mention_tracker | アンテナアカウント自動拡張 |

> **注意**：旧 `trend_posts` / `trend_score_debug` タブは過去データとして残るが、新規実行では書き込まれない（2026-07-05以降）。

---

## Google Sheets 書き込みルール

- **全サーバーは `append_rows` バッチ書き込み**（`append_row` 1件ずつのループは429エラーの原因、禁止）
- 例外：North Star Daily / カテゴリ集約など「1行/実行」のみのものは `append_row` 1回でよい
- 新しい save 関数を追加するときは必ずバッチパターンに従う

---

## アーキテクチャ上の重要な区別

- `post["category"]`（`CATEGORY_ALL` / `CATEGORY_BEAUTY`）：Bright Dataの取得元カテゴリ（Instagram全体 vs 美容ジャンル）
- `idea["投稿カテゴリ"]`（例：ビフォーアフター型/悩み提示型）：AIが付ける投稿コンテンツ角度
- この2つは全く別のフィールドで意味が違う。`daily_content_picks` の重複排除は後者を使う。

---

## Sprint2の残タスク（優先度：低、ユーザー指示待ち）

- Task6：North Star Daily HTML出力（`north_star_report.py`にスタブ追記済み、未実装）
- Task7：TikTok/YouTube/Threads/X向けフェッチャー抽象化（現在Instagramのみ）
- Task8：`creator_intelligence/` への全ファイル移行（現在は `research/` と `knowledge/` のみ移行済み）

**1ステップずつ動作確認しながら進める**（大規模リファクタリング禁止）。

---

## 過去の重要な意思決定（変更前に確認）

| 日付 | 決定内容 |
|---|---|
| 2026-06-30 | 採用/不採用の二値フィルタ廃止 → `build_post_pool`（構造的に使えるもの全件プール）に変更 |
| 2026-07-01 | Sheets書き込みをバッチ化（429エラー対策） |
| 2026-07-01(2回目) | 成功要因分析を独立した第3のAI呼び出しとして追加（②③④パイプラインには連鎖しない） |
| 2026-07-01(3回目) | SNS Pattern Lab素材生成を第4のAI呼び出しとして追加（`analyze_success_factors`の出力のみを入力） |
| 2026-07-02 | AI分析ゲートを「スコア80点以上」→「常に上位5件」に変更（`MAX_ANALYZED_POSTS_PER_RUN`廃止） |
| 2026-07-05 | `trend_score.py` → `research_candidate_score.py` 全体リネーム + AI分析しきい値ゲート（80点）復活 |
