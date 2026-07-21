"""
bright_data_fetcher.py
Bright Data Instagram Scraper APIを使ってInstagramのリール投稿を取得し、
「Instagram全体で伸びている投稿からCORE HARI FACEの集客につながる
投稿案を作る」ためのプール作成(構造的に使えない投稿の除外)・Trend Score
ランキング用のデータを準備するモジュール(詳細は下記【プール条件】参照)。

apify_fetcher.py の置き換え版。外部公開している関数名・戻り値の形
(dictのキー名)はapify_fetcher.pyとほぼ同じにしている
(旧filter_and_adoptはbuild_post_poolに置き換えた。下記参照)。

【プール条件(2026-06-30: 採用/不採用の二値フィルタを廃止。下記参照)】
build_post_poolが除外するのは、データとして分析に使えない投稿のみ:
1. 取得失敗(fetch_error)
2. リール以外
3. 投稿日が直近RECENT_DAYS日より古い

再生数・再生倍率・フォロワー数の有無による除外は行わない。これらは
trend_score.pyのTrend Score(連続スコア)で評価し、スコアが高い投稿から
優先的にAI個別分析の対象にする方式に統一した(詳細は本ファイル末尾の
【2026-06-30】セクション、およびtrend_score.pyのdocstring参照)。

【2026-06-29: 美容ジャンル/Instagram全体トレンドの2カテゴリを統合】
このシステムの目的は美容競合の分析ではなく「Instagram全体で伸びている
投稿を毎日分析すること」のため、ジャンルで分けず単一カテゴリ
(CATEGORY_ALL)として扱う。取得対象アカウント(accounts.py の
ANTENNA_ACCOUNTS)もジャンルを問わない「アンテナアカウント」として
一本化した。新規アカウントの発見は candidate_discovery.py が行う
(取得した投稿のキャプション/ハッシュタグから@メンションを抽出する)。

【ハッシュタグ検索・競合アカウント発見について(2026-06-29: Apify完全停止)】
Bright Data Instagram Scraper API(公式ドキュメント: docs.brightdata.com)には
Profiles / Posts / Reels / Comments の4種類のAPIしかなく、ハッシュタグや
キーワードから「未知のアカウント」を新規発見する機能は存在しない
(「Discover by URL」は、あくまで既知のプロフィールURLから投稿/リールを
取得する機能であり、ハッシュタグ起点の探索ではない)。
そのため、ハッシュタグ自動発見(Apify)は完全に停止し、取得対象アカウントは
accounts.py(ANTENNA_ACCOUNTS)で管理し、candidate_discovery.pyによる
半自動の候補抽出で広げていく方式に変更した。
competitor_discovery.py(Apify使用)はバックアップとして残しているが、
main.pyからは呼ばれておらず、Apifyへの通信は一切発生しない。

【取得方式: Reels - Discover by URL】
dataset_id=gd_lyclm20il4r5helnj に対して
type=discover_new&discover_by=url を指定して呼び出す。
入力はプロフィールURL単位で、num_of_posts/start_date/end_dateで
取得件数・期間を指定できる。レスポンスにはreel自体の情報に加えて
"followers"(投稿者のフォロワー数)が直接含まれているため、
Apify版のように別途プロフィール取得Actorを呼ぶ必要がない。
(参考: https://docs.brightdata.com/api-reference/scrapers/social-media-apis/instagram-reels-discover-by-url)

Discover系はBright Data公式ドキュメントで「async(/trigger)専用」と
明記されているため、本モジュールは /trigger -> /progress -> /snapshot
の非同期フローのみを実装する(同期/scrapeは使わない)。

【2026-06-29: バッチ分割・タイムアウト短縮・テストモード】
1ジョブに大量のアカウント・投稿数を詰め込むと600秒でタイムアウトする
事象が発生したため、以下のように変更した。
- 1ジョブあたりACCOUNTS_PER_BATCH件(最大5)のアカウントのみ取得する
  (美容トレンド/Instagram全体トレンドは元々別々のジョブなので、
  さらにその中で小さなバッチに分割する)
- 1アカウントあたりの取得件数(DEFAULT_RESULTS_PER_ACCOUNT)を8件に縮小
- 1バッチの待ち時間(POLL_TIMEOUT_SEC)を120秒に短縮し、超えたら
  そのバッチだけスキップして次のバッチに進む(プログラム全体は止めない)
- どのバッチ(アカウント)が失敗したかをログに出力する
- TEST_MODE=Trueの間は、美容トレンド/Instagram全体トレンド合計で
  TEST_MODE_MAX_TOTAL_ACCOUNTS件(5件)までしか取得しない。
  安定動作を確認できたらTEST_MODE=Falseに変更する。
目的は大量取得ではなく「毎日安定して集客に使える投稿案を作ること」。

【2026-06-29(4回目): 伸び率(growth_rate)で採用順を決定するように変更】
ユーザーから「再生数・投稿日時・フォロワー数から伸び率を評価してほしい」との
要望があったため、filter_and_adoptの最終的な並び順を「再生数が多い順」から
「伸び率(growth_rate = 日次再生数 ÷ フォロワー数)が高い順」に変更した。
日次再生数(growth_velocity)は 累計再生数 ÷ 投稿からの経過日数 の近似値。
詳細は _compute_growth_metrics() のdocstringを参照。
（採用条件の「再生数10万以上」「再生数>=フォロワー数」自体は変更していない。
この変更は、採用済み投稿のうちどれを優先的にAI個別分析するか・どの順で
ランキングシートに出すかに影響する）

【2026-06-29(6回目): account_post_count_window(投稿頻度の実測代理指標)を追加】
ユーザーがtrend_score.pyのTrend Score評価項目に「投稿頻度」を追加する要望を
出したが、Bright DataのAPIは1回の取得で「アカウントの投稿頻度」(週何本など)を
直接は返さない。そのため、_attach_account_post_counts()で「今回の取得窓内
(直近RECENT_DAYS日以内・1アカウントあたり最大DEFAULT_RESULTS_PER_ACCOUNT件)で
同じsource_accountから実際に取得できた投稿数」を数え、全投稿に
post["account_post_count_window"]として付与するようにした
(fetch_trend_postsが返す直前、フィルタ前の全件に対して実行する)。
これはキーワード推定ではなく、実際に取得できた件数そのものなので
trend_score.pyの「測定可能な指標を使う」という方針に合致する。

【2026-06-30: 採用/不採用の二値フィルタ(filter_and_adopt)を廃止し、
build_post_poolによるTrend Score順位方式に全面変更】
実データで実行したところ、取得27件中25件が「再生数10万以上」条件で除外され、
採用0件という事態が発生した。ユーザーから明確な指示があり、以下のように
再設計した。
1. 再生数(MIN_VIEWS)・再生倍率(再生数>=フォロワー数)による二値除外を
   完全に廃止した。これらは既にtrend_score.pyのTrend Score項目
   (再生数20点・再生倍率20点、いずれも連続スコア)として評価されており、
   二値フィルタとして別途持つ必要がない。「条件を満たさないから捨てる」
   ではなく「点数が低いだけ」になり、後段のtrend_score.sort_by_scoreで
   自然に下位に並ぶ。
2. フォロワー数が取得できない投稿も除外しない(再生倍率の得点が0点に
   なるだけで、他の項目でのスコアリングは引き続き可能なため)。
3. 構造的に分析対象として成立しない投稿(取得失敗・リール以外・投稿日が
   直近RECENT_DAYS日より古い)のみを除外する。これは「良い投稿かどうか」
   ではなく「データとして使えるかどうか」の判断であるため、フィルタとして
   残す。
4. 旧TARGET_ADOPTED_COUNT(上位20件への絞り込み)も廃止した。プールに残った
   投稿は全件trend_score.score_posts/sort_by_scoreでスコアリング・ランキング
   され、Trend Scoreが高い投稿だけがAI個別分析の対象になる
   (trend_score.ANALYSIS_MIN_SCORE・MAX_ANALYZED_POSTS_PER_RUN参照)。
5. 関数名をfilter_and_adopt → build_post_poolに変更し、戻り値のキーも
   "adopted" → "pool"に変更した(「採用」という二値判断の語をコードからも
   無くすため)。各投稿にはpost["pool_exclusion_reason"](空文字列なら除外
   なし=プール入り)を付与する。main.pyはフィルター前の全件(この理由付き)を
   raw_fetch_logシートに常時保存するようにした(sheets_writer.save_raw_
   fetch_log参照)。これにより「何件中何件がどの理由で外れたか」を毎回の
   実行で確認できる。

【2026-07-01: snapshot APIのレスポンス構造解析を堅牢化】
実データで実行したところ「Bright Data snapshotのレスポンス形式が想定外でした
(リストではない)」というログで取得が0件になる事象が発生した。従来は
snapshot_resp.json()が常に「投稿アイテムのdictのリスト」そのものを返すことを
前提としており(isinstance(items, list)のみで判定)、dictでラップされた
レスポンスには対応していなかった。
対応として以下を実装した(詳細は_extract_snapshot_items/_save_debug_snapshot
直前のコメント参照)。
1. snapshot APIの生レスポンスを毎回debug_snapshot.json(本ファイルと同じ
   ディレクトリ)へそのまま保存するようにした。次回同種の事象が起きた際は、
   このファイルで実際の構造を確認できる。
2. レスポンスがdata/items/results/snapshot/result/rowsのいずれかのキーで
   ラップされている場合にも対応した。未知のキー名の場合はdict内で最初に
   見つかったリストを使うフォールバックも追加した。
3. リストが全く見つからない場合、dictに"error"/"warning"キーがあれば
   エラーレスポンスとして扱い、無ければ投稿1件分のdictがそのまま返ってきた
   ものとして[payload]を1件として扱う。
4. 取得件数(レスポンスから取り出せた要素数)・解析件数(dict形式で実際に
   使える件数)・解析失敗件数(dictでなかった要素数)・レスポンス構造
   (上記1〜3のどれに該当したか)を毎回ログに出力するようにした。
"""

import datetime as dt
import json
import os
import time

import requests

from config import BRIGHT_DATA_API_KEY

# --- Bright Data API設定 ---
API_BASE = "https://api.brightdata.com"

# 2026-07-01: snapshot APIの生レスポンスをそのまま保存するデバッグファイル。
# 「レスポンス形式が想定外でした」のような事象が起きた際に、実際に何が返って
# きたのかをコード変更なしで確認できるようにするためのもの(下記_save_debug_
# snapshot参照)。実行ごとに最新のレスポンスで上書きする(複数バッチ実行時は
# 最後に処理されたバッチの内容になる)。
DEBUG_SNAPSHOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_snapshot.json")

# 2026-07-18: タイムアウトした未完了ジョブのsnapshot_idを保存するファイル。
# タイムアウト時はsnapshot_idをここに書き込み、次回実行時に状態を再確認する。
# 同一バッチキーで重複ジョブを作らないための排他制御にも使う。
PENDING_SNAPSHOTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending_snapshots.json")
ACCOUNT_ROTATION_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "runtime_state", "account_rotation.json"
)

# Reels - Discover by URL 用のdataset_id。
# 公式ドキュメントで「Discover by URL用には必ずこの値を使うこと」と
# 明記されている固定値(推測ではない)。
REELS_DATASET_ID = "gd_lyclm20il4r5helnj"
REELS_DISCOVER_QUERY = {"type": "discover_new", "discover_by": "url"}

# --- バッチ分割設定 ---
# 2026-06-29: 1回のジョブに大量のアカウント・投稿数を詰め込むと
# POLL_TIMEOUT_SEC(旧600秒)以内にジョブが終わらずタイムアウトする事象が
# 発生したため、1ジョブあたりのアカウント数・投稿数を絞り、小さなジョブに
# 分割して実行する方式に変更した。
# 目的は大量取得ではなく「毎日安定して集客に使える投稿案を作ること」。
# 【2026-07-20: バッチサイズ調査結果】
# 5アカウント/バッチ → proxy error が発生すると Bright Data がリトライし続け300秒超過。
# 2アカウント/バッチ に下げると1ジョブの作業量が減り、proxy error も連鎖しにくくなる。
# main.py から --batch-size 2 オプションで上書き可能。
ACCOUNTS_PER_BATCH = 2  # 2026-07-20: 5→2に変更。proxy error によるrunning長期化対策。
DEFAULT_RESULTS_PER_ACCOUNT = 8  # 1アカウントあたり取得する最新投稿数(5〜10件)

# --- ポーリング設定 ---
# 2026-07-20: POLL_INTERVAL を15→30秒に変更。
# 理由: 全バッチを一括trigger（非同期化）後は巡回ポーリングのAPI呼び出しが
# バッチ数×ポーリング回数に比例して増える。30秒間隔にすることで
# progress API への呼び出し回数を半減させ、レート制限リスクを下げる。
# 43アカウント/2件バッチ=22バッチ構成では15秒だと1ラウンドで22回のAPI呼び出し、
# 300秒予算内で最大600回になる。30秒では最大330回に抑えられる。
POLL_INTERVAL_SEC = 30  # 2026-07-20: 15→30秒に変更。非同期化後の多バッチ対応。
POLL_TIMEOUT_SEC = 600  # 2026-07-18: 150→600秒に変更。Discover by URLは数分かかることが多い。
# タイムアウト時はsnapshot_idをPENDING_SNAPSHOTS_PATHに保存し、次回実行時に再確認する。
# 【2026-07-02(10回目): 全バッチを合計した最大取得時間。これを超えたら残りのバッチは
#   スキップして後続のOpenAI分析・Creator Studioへ進む(10分以内完了要件対応)】
FETCH_TOTAL_BUDGET_SEC = 300  # Bright Data全体に許可する最大秒数(5分)

# Bright Data Dashboard の snapshot 詳細ページURL（ログ表示・調査用）
BD_SNAPSHOT_DASHBOARD_URL = "https://brightdata.com/cp/datasets/snapshots/{snapshot_id}"

# ─── Stale / 障害検出しきい値 (2026-07-20) ───────────────────────────────────
# Bright Data 側の障害で全 snapshot が running のまま完了しない事象への対処。
#
# 状態区別:
#   completed    : status=ready でダウンロード済み
#   failed       : status=failed (Bright Data が明示的に失敗を返した)
#   running      : trigger 後 STALE_WARNING_MIN 分以内
#   stale        : STALE_WARNING_MIN 分超〜STALE_ABORT_MIN 分
#   not_triggered: trigger そのものを行っていない（trigger 禁止により）
#
STALE_WARNING_MIN  = 30   # これを超えると "stale" 警告
STALE_ABORT_MIN    = 120  # これを超えると異常扱い（新規 trigger しない）
MAX_RUNNING_TO_TRIGGER = 5  # running/stale がこの件数以上なら新規 trigger を禁止
                             # （Bright Data 障害中の無限 trigger 防止）

# --- 通信リトライ設定 ---
# Bright Data側、またはネットワーク経路で一時的に接続が切れる
# (例: "Connection reset by peer") ことがあるため、1回ごとの通信失敗で
# 即座に取得失敗とせず、何度かリトライする。
# 「設計よりも毎日安定して動くことを最優先にする」という方針のため。
MAX_REQUEST_RETRIES = 3
RETRY_BACKOFF_SEC = 5

CATEGORY_ALL = "Instagram全体トレンド"

# 2026-07-02追加: ①Instagram全体トレンド+②美容ジャンルトレンドの統合対応。
# Bright Dataへの取得を2回に増やすコストをかけず、1回の取得(CATEGORY_ALL)で
# 得た投稿のうち、accounts.ANTENNA_ACCOUNTS_BEAUTY由来のものだけを事後的に
# このカテゴリへ再分類する(apply_beauty_category参照)。
CATEGORY_BEAUTY = "美容ジャンルトレンド"

# --- プール条件のしきい値 ---
# 2026-06-30: 再生数(MIN_VIEWS)・採用目標件数(TARGET_ADOPTED_COUNT)による
# 二値フィルタ/上限カットは廃止した。直近何日以内を「分析対象として新しい」と
# 扱うかの基準(RECENT_DAYS)のみ、構造的な範囲指定として残す。
RECENT_DAYS = 20

# --- テストモード ---
# 2026-07-20: TEST_MODE を False（本番）に変更。
# 環境変数 BRIGHT_DATA_TEST_MODE=1 を設定することでテスト実行も可能。
# テストモード時は TEST_MODE_MAX_TOTAL_ACCOUNTS 件だけ取得する。
TEST_MODE = os.environ.get("BRIGHT_DATA_TEST_MODE", "").lower() in ("1", "true", "yes")
TEST_MODE_MAX_TOTAL_ACCOUNTS = 5

# --- ドライランモード ---
# main.py から DRY_RUN = True を設定すると、Bright Data API を呼ばずに
# 取得予定のアカウント一覧とバッチ計画だけを表示して終了する。
DRY_RUN = False

_session = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        if not BRIGHT_DATA_API_KEY:
            raise EnvironmentError("BRIGHT_DATA_API_KEY が設定されていません。")
        session = requests.Session()
        session.headers.update(
            {
                "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}",
                "Content-Type": "application/json",
            }
        )
        _session = session
    return _session


def _request_with_retry(method: str, url: str, **kwargs):
    """
    Bright DataへのHTTPリクエストを実行する。
    "Connection reset by peer" のような一時的な接続エラーに対しては、
    セッションを作り直してから最大MAX_REQUEST_RETRIES回まで再試行する。
    リトライしても失敗した場合は最後の例外をそのまま投げる
    (呼び出し側で requests.RequestException を捕まえて取得失敗として扱う)。
    """
    global _session

    last_exc = None
    for attempt in range(1, MAX_REQUEST_RETRIES + 1):
        try:
            session = _get_session()
            resp = session.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_exc = e
            print(
                f"Bright Data API呼び出しに失敗しました"
                f"(試行{attempt}/{MAX_REQUEST_RETRIES}, {method} {url}): {e}"
            )
            # 接続が切れた可能性があるため、セッションを作り直してから再試行する
            _session = None
            if attempt < MAX_REQUEST_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC)

    raise last_exc


def _to_username(account: str) -> str:
    """"@username" / "username" のどちらでも動くように正規化する。"""
    account = (account or "").strip()
    if account.startswith("@"):
        account = account[1:]
    return account.strip()


def _to_profile_url(account: str) -> str:
    username = _to_username(account)
    return f"https://www.instagram.com/{username}/"


def _load_rotation_state() -> dict:
    """runtime_state/account_rotation.json を読み込む。ファイルがなければ空dict。"""
    try:
        if os.path.exists(ACCOUNT_ROTATION_PATH):
            with open(ACCOUNT_ROTATION_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[ローテーション] 状態ファイル読み込み失敗（初期化します）: {e}")
    return {}


def _save_rotation_state(state: dict) -> None:
    """runtime_state/account_rotation.json に状態を保存する。"""
    try:
        os.makedirs(os.path.dirname(ACCOUNT_ROTATION_PATH), exist_ok=True)
        with open(ACCOUNT_ROTATION_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ローテーション] 状態ファイル保存失敗: {e}")


def _apply_test_mode_limit(usernames: list, category: str) -> list:
    """
    TEST_MODE中はアカウントを5件ずつローテーションして取得する。
    毎回先頭5件ではなく、前回の続きから5件を選ぶ。
    pending中のアカウントは選択対象から除外し、triggerの重複を防ぐ。
    本番モードでは全件対象（ローテーション制限なし）。
    """
    if not TEST_MODE:
        return usernames

    # 重複除外した一意リスト（順序保持）
    seen: set[str] = set()
    unique: list[str] = []
    for u in usernames:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    if not unique:
        return []

    # pending中のアカウントを除外
    try:
        pending = _load_pending_snapshots()
        pending_accounts: set[str] = set()
        for info in pending.values():
            for acc in info.get("accounts", []):
                pending_accounts.add(_to_username(acc))
        available = [u for u in unique if u not in pending_accounts]
        if pending_accounts:
            print(
                f"[ローテーション] pending中: {len(pending_accounts)}件を除外 "
                f"→ 対象候補: {len(available)}件"
            )
    except Exception:
        available = unique

    if not available:
        print("[ローテーション] pending除外後に対象アカウントが0件。pendingを待機中。")
        return []

    total = len(available)

    # ローテーション状態を読み込む
    state = _load_rotation_state()
    start_idx = state.get(category, {}).get("next_start", 0)
    # アカウント一覧の変更に対応: 範囲外なら先頭へ
    if start_idx >= total:
        start_idx = 0

    # 5件選択（末尾を超えたら先頭に折り返す）
    size = TEST_MODE_MAX_TOTAL_ACCOUNTS
    if total <= size:
        selected = available[:]
        next_start = 0
    else:
        end_idx = start_idx + size
        if end_idx <= total:
            selected = available[start_idx:end_idx]
        else:
            # 折り返し
            selected = available[start_idx:] + available[: end_idx - total]
        next_start = end_idx % total

    # 状態保存
    if category not in state:
        state[category] = {}
    state[category]["next_start"] = next_start
    state[category]["last_selected"] = selected
    _save_rotation_state(state)

    print(
        f"[テストモード・ローテーション] {category}: "
        f"登録{len(unique)}件中 {start_idx + 1}〜{start_idx + len(selected)}番 の{len(selected)}件を選択"
        f"（次回開始: {next_start + 1}番）"
    )
    print(f"  選択アカウント: {', '.join(selected)}")

    return selected


def _get_value(obj, key: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _get_first(item, keys: list, default=None):
    for key in keys:
        value = _get_value(item, key)
        if value not in (None, ""):
            return value
    return default


def _parse_numeric(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value, default=0) -> int:
    parsed = _parse_numeric(value)
    if parsed is None:
        return default
    try:
        return int(parsed)
    except (ValueError, TypeError, OverflowError):
        return default


def _to_int_or_none(value):
    parsed = _parse_numeric(value)
    if parsed is None:
        return None
    try:
        return int(parsed)
    except (ValueError, TypeError, OverflowError):
        return None


def _parse_posted_at(raw):
    """
    date_posted (例: "2026-02-26T03:23:20.000Z") をdatetime(UTC)に変換する。
    解釈できない場合はNoneを返す。
    """
    if raw is None or raw == "":
        return None

    if isinstance(raw, (int, float)):
        try:
            return dt.datetime.fromtimestamp(raw, tz=dt.timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None

    text = str(raw).strip()
    if not text:
        return None

    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_error_item(item) -> bool:
    """
    Bright Dataが返したアイテムが投稿データではなく、取得失敗(エラー)を
    表すアイテムかどうかを判定する。

    【注意】Bright DataのInstagram Reels APIで、個別URLの取得に失敗した
    場合の正確なレスポンス形式は、本プロジェクトでは実際のAPIキーでの
    実行確認がまだできていない(公式ドキュメントのレスポンス例には
    成功時の形しか載っていない)。
    そのため、ここでは以下のいずれかに当てはまる場合を「取得失敗」とみなす
    保守的な判定にしている。
    - "error" または "warning" キーに値が入っている
      (Bright Dataの他のデータセットで個別URL失敗時に使われる一般的な形)
    - 投稿データの中核フィールド(url/user_posted/post_id)が
      1つも無い(=投稿として扱えない空データ)
    実際の失敗レスポンスを確認できたら、この判定を実データに合わせて
    見直すこと。
    """
    if _get_value(item, "error") or _get_value(item, "warning"):
        return True

    has_core_fields = any(
        _get_value(item, key) not in (None, "")
        for key in ("url", "user_posted", "post_id")
    )
    return not has_core_fields


def _extract_error_item_url(item) -> str:
    """
    【2026-07-02追加: item1対応】
    実運用でBright Dataから "Cannot read properties of undefined
    (reading 'match')" という、Bright Data自身のバックエンドが返す
    per-item parse errorが発生した(debug_snapshot.jsonで実物を確認済み。
    Python側の例外ではなく、_is_error_item/fetch_errorにより既にクラッシュ
    せず・対象投稿だけスキップする実装になっている)。

    唯一の不備は、このエラーアイテムの "input" がdict
    (例: {"url": "https://www.instagram.com/p/xxx/", ...})の場合に、
    旧実装ではtargetにdictそのものを入れてしまい、ログが
    「{'url': '...', 'posts_count': 54, ...}: エラー文」のような読みにくい
    形になっていた点。ユーザー要望「ログにURLと原因だけ残す」に対応し、
    input/discovery_inputがdictならその中のurlキーだけを取り出すようにした。
    """
    direct_url = _get_value(item, "url")
    if isinstance(direct_url, str) and direct_url:
        return direct_url

    for key in ("input", "discovery_input"):
        nested = _get_value(item, key)
        if isinstance(nested, dict):
            nested_url = nested.get("url")
            if isinstance(nested_url, str) and nested_url:
                return nested_url
        elif isinstance(nested, str) and nested:
            return nested

    user_posted = _get_value(item, "user_posted")
    if isinstance(user_posted, str) and user_posted:
        return user_posted

    return "(不明なURL)"


def _describe_error_item(item) -> str:
    target = _extract_error_item_url(item)
    description = (
        _get_value(item, "error")
        or _get_value(item, "warning")
        or "投稿データが空でした(取得失敗、または該当アカウントに対象期間内のリールが無い可能性があります)"
    )
    return f"{target}: {description}"


def _is_reel(item) -> bool:
    """
    リール(動画)投稿かどうかを判定する。
    Reels - Discover by URL は本来リールのみを返すAPIだが、
    念のためproduct_type等で確認する(画像のみの投稿が混入していないか)。
    """
    product_type = str(_get_value(item, "product_type") or "").lower()
    if product_type in ("clips", "reel", "reels"):
        return True

    if _get_first(item, ["video_url", "video_play_count"]) is not None:
        return True

    return False


def _get_post_type(item) -> str:
    """
    【2026-07-18】URL・product_type・typenameから投稿種別を判定する。
    Returns: "Reel" / "Carousel" / "Feed"

    判定順:
    1. URL に /reel/ を含む → "Reel"
    2. product_type が clips/reel/reels → "Reel"
    3. video_url/video_play_count がある → "Reel"
    4. product_type が carousel_container、または typename が GraphSidecar → "Carousel"
    5. それ以外 → "Feed"
    """
    url = str(_get_first(item, ["url"], "") or "")
    product_type = str(_get_value(item, "product_type") or "").lower()
    typename = str(_get_value(item, "__typename") or "").lower()

    if "/reel/" in url or product_type in ("clips", "reel", "reels"):
        return "Reel"
    if _get_first(item, ["video_url", "video_play_count"]) is not None:
        return "Reel"
    if product_type == "carousel_container" or typename in ("graphsidecar", "xdtstextcarousel"):
        return "Carousel"
    return "Feed"


def _extract_followers(item):
    """
    フォロワー数を取得する。Reels - Discover by URLのレスポンスには
    "followers"が直接含まれている(投稿者プロフィールの情報)。
    取得できなければNoneを返す。
    """
    return _to_int_or_none(_get_value(item, "followers"))


def _compute_growth_metrics(views: int, followers, posted_at_dt) -> tuple:
    """
    【2026-06-29(4回目): 伸び率指標を追加】
    ユーザーの要望「再生数・投稿日時・フォロワー数から伸び率を評価する」に対応する。

    重要な制約: Bright Dataからは1回の取得につき投稿の「ある時点のスナップショット」
    (現在の累計再生数)しか得られず、同じ投稿を毎日再取得して再生数の変化を
    記録しているわけではない。そのため、ここでの「伸び率」は厳密な時系列の
    増加速度ではなく、「投稿日からこれまでの平均的な再生ペース」という近似値である
    (= 累計再生数 ÷ 経過日数)。これを明確にするため、内部的には
    "growth_velocity"(日次再生数の近似値)と呼ぶ。

    - growth_velocity = views ÷ 経過日数(1日未満は1日として扱い、投稿直後の
      極端な値を避ける)
    - growth_rate = growth_velocity ÷ フォロワー数
      (フォロワー数を考慮することで、単に「フォロワーが多いから再生数が多い」
      投稿と、「フォロワー規模に対して異常に速いペースで伸びている」投稿を
      区別できる。これが採用済み投稿の最終的な並び順に使う指標になる)

    posted_at_dtまたはfollowersが無い場合は (None, None) を返す。
    """
    if posted_at_dt is None or not followers:
        return None, None

    now = dt.datetime.now(dt.timezone.utc)
    days_elapsed = (now - posted_at_dt).total_seconds() / 86400
    days_elapsed = max(days_elapsed, 1.0)

    growth_velocity = round(views / days_elapsed, 1)
    growth_rate = round(growth_velocity / followers, 4)
    return growth_velocity, growth_rate


def _normalize_post(item: dict, source_account: str, category: str) -> dict:
    username = _get_first(item, ["user_posted"], "") or ""

    caption = _get_first(item, ["description"], "") or ""

    views_raw = _get_first(item, ["views", "video_play_count"], 0)
    # 【再生数取得できない原因調査ログ (2026-07-20)】
    # Bright Data Discover-by-URL では views/video_play_count が None になるケースが頻発。
    # 原因: Instagram がプロフィール未認証ユーザーに再生数を非公開にしている可能性。
    #       または Bright Data の内部データソースが Reels の plays を取得していない。
    # このログでフィールドの実態を確認する（1投稿目のみ）。
    if item is not None and not hasattr(_normalize_post, "_views_logged"):
        _normalize_post._views_logged = True
        raw_views = item.get("views")
        raw_vpc = item.get("video_play_count")
        if raw_views is None and raw_vpc is None:
            print(
                f"  [views調査] views=None, video_play_count=None "
                f"(投稿: {item.get('url', '')[:60]})"
            )
        else:
            print(f"  [views調査] views={raw_views}, video_play_count={raw_vpc}")
    likes_raw = _get_first(item, ["likes"], 0)
    comments_raw = _get_first(item, ["num_comments"], 0)
    duration_raw = _get_first(item, ["length"], None)

    url = _get_first(item, ["url"], "") or ""

    media_url = _get_first(item, ["video_url", "thumbnail"], "") or ""

    posted_at_raw = _get_first(item, ["date_posted"], "") or ""
    posted_at_dt = _parse_posted_at(posted_at_raw)

    views = _to_int(views_raw)
    followers = _extract_followers(item)
    view_multiplier = round(views / followers, 2) if followers else None
    growth_velocity, growth_rate = _compute_growth_metrics(views, followers, posted_at_dt)

    # Bright Data Instagram Reels APIには保存数・シェア数の項目が無いため、
    # 取得できない項目として常にNoneを返す(シート出力側は空欄として扱う)。
    saves = None
    save_rate = None
    shares = None

    hashtags_raw = _get_value(item, "hashtags")
    hashtags = [str(h).lstrip("#") for h in hashtags_raw] if isinstance(hashtags_raw, list) else []

    return {
        "username": username,
        "caption": caption,
        "likes": _to_int(likes_raw),
        "comments": _to_int(comments_raw),
        "views": views,
        "saves": saves,
        "shares": shares,
        "save_rate": save_rate,
        "followers": followers,
        "view_multiplier": view_multiplier,
        "growth_velocity": growth_velocity,
        "growth_rate": growth_rate,
        "duration_sec": _to_int_or_none(duration_raw),
        "url": url,
        "media_url": media_url,
        "posted_at": str(posted_at_raw),
        "posted_at_dt": posted_at_dt,
        "hashtags": hashtags,
        "is_reel": _is_reel(item),
        "post_type": _get_post_type(item),  # 2026-07-18: "Reel" / "Carousel" / "Feed"
        "fetch_error": _is_error_item(item),
        "source_account": source_account,
        "category": category,
        "raw_data": item,
        # 2026-07-04(6回目): Sprint2設計レビュー③(他プラットフォーム拡張)に対応。
        # 現状はBright Data Instagram Reels APIのみのため値は固定で"instagram"だが、
        # 将来TikTok/YouTube/Threads/X用のfetcherを追加した際、各fetcherがそれぞれの
        # platform名("tiktok"等)を返すようにすれば、analysis/prompts/Trend Score側の
        # コードは(post["platform"]を見て分岐したい箇所だけ追加すればよく)post辞書の
        # 構造自体は変更不要になる。
        "platform": "instagram",
    }


# 2026-07-01: snapshot APIのレスポンス構造解析を堅牢化(下記参照)。
# 【従来の想定】snapshot_resp.json()が常に「投稿アイテムのdictのリスト」その
# ものを返す、という前提だった(items = snapshot_resp.json(); isinstance(items,
# list)のみで判定)。実データで実行したところ「リストではない」というエラーで
# 取得が0件になる事象が発生したが、実際にどんな構造で返ってきたのかをコード上
# 確認する手段が無かった。
#
# 【対応】
# 1. snapshot_resp.json()の生レスポンスを毎回DEBUG_SNAPSHOT_PATH
#    (debug_snapshot.json)へそのまま保存するようにした(_save_debug_snapshot)。
#    実際の構造を確認してから、このリストへキー名を追加できる。
# 2. レスポンスがリストでなくdictだった場合に備えて、よく使われるラッパー
#    キー名(data/items/results/snapshot/result/rows)を順に探し、見つかった
#    リストを使うようにした。
# 3. 既知のキーに無い場合は、dict内で最初に見つかったリスト値を使う(未知の
#    キー名への保険)。
# 4. リストが1つも見つからない場合、dictに"error"/"warning"キーがあれば
#    明確なエラーレスポンスとして扱い、無ければ「投稿1件分のdictがそのまま
#    返ってきた」可能性を考慮して[payload]として扱う。
# 5. 上記すべてに当てはまらない場合のみ「構造を解釈できない」として失敗扱いに
#    する(無理にNoneやダミーで埋めることはしない)。
SNAPSHOT_LIST_KEYS = ["data", "items", "results", "snapshot", "result", "rows"]


def _load_pending_snapshots() -> dict:
    """
    pending_snapshots.jsonから未完了ジョブ情報を読み込む。
    形式: {batch_key: {"snapshot_id": str, "accounts": list, "triggered_at": str}}
    ファイルが無い・読み込めない場合は空dictを返す。
    """
    try:
        if os.path.exists(PENDING_SNAPSHOTS_PATH):
            with open(PENDING_SNAPSHOTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"pending_snapshots.jsonの読み込みに失敗しました(本処理には影響しません): {e}")
    return {}


def _snapshot_age_minutes(triggered_at_str: str) -> float:
    """triggered_at 文字列から経過分数を返す。パース失敗時は -1。"""
    try:
        tdt = dt.datetime.fromisoformat(triggered_at_str.replace("Z", "+00:00"))
        return (dt.datetime.now(dt.timezone.utc) - tdt).total_seconds() / 60
    except Exception:
        return -1.0


def _classify_snapshot_state(info: dict) -> str:
    """
    pending エントリ1件の状態を返す。
      completed    : bd_status == "ready" または "recovered"（正常完了）
      failed       : bd_status == "failed"
      running      : trigger 後 STALE_WARNING_MIN 分以内
      stale        : STALE_WARNING_MIN 分超〜STALE_ABORT_MIN 分
      stale_abort  : STALE_ABORT_MIN 分超（異常扱い）
      not_triggered: snapshot_id がない
    """
    sid = info.get("snapshot_id", "")
    bd_status = info.get("bd_status", "")

    if not sid:
        return "not_triggered"
    if bd_status in ("ready", "recovered"):
        return "completed"
    if bd_status == "failed":
        return "failed"

    age = _snapshot_age_minutes(info.get("triggered_at", ""))
    if age < 0:
        return "running"
    if age > STALE_ABORT_MIN:
        return "stale_abort"
    if age > STALE_WARNING_MIN:
        return "stale"
    return "running"


def _count_active_snapshots(pending: dict) -> dict:
    """
    pending の各エントリを状態別にカウントする。
    戻り値: {"running": N, "stale": N, "stale_abort": N, "completed": N, "failed": N}
    """
    counts: dict[str, int] = {"running": 0, "stale": 0, "stale_abort": 0, "completed": 0, "failed": 0}
    for info in pending.values():
        state = _classify_snapshot_state(info)
        if state in counts:
            counts[state] += 1
    return counts


def _check_trigger_allowed(pending: dict) -> tuple[bool, str]:
    """
    新規 trigger を許可するかどうかを判定する。
    戻り値: (allowed: bool, reason: str)
    """
    counts = _count_active_snapshots(pending)
    active = counts["running"] + counts["stale"] + counts["stale_abort"]

    if active >= MAX_RUNNING_TO_TRIGGER:
        reason = (
            f"⚠️  Bright Data 障害の疑い: {active}件の snapshot が running/stale のまま完了していません。\n"
            f"   (running={counts['running']} stale={counts['stale']} stale_abort={counts['stale_abort']})\n"
            f"   新規 trigger を停止し、Instagram取得なしモードで続行します。\n"
            f"   Dashboard で各 snapshot の状態を確認してください:\n"
            f"   https://brightdata.com/cp/datasets"
        )
        return False, reason
    return True, ""


def _print_pending_health(pending: dict) -> None:
    """pending_snapshots.json の健全性を表示する。"""
    if not pending:
        return
    counts = _count_active_snapshots(pending)
    total = len(pending)
    real = sum(1 for v in pending.values() if v.get("snapshot_id", "").startswith("sd_"))
    print(f"  pending_snapshots: 合計{total}件 (実 snapshot: {real}件)")
    for state, cnt in counts.items():
        if cnt:
            label = {
                "running":     "  running（正常）",
                "stale":       "⚠️  stale (30分超)",
                "stale_abort": "❌ stale_abort (2時間超・異常)",
                "completed":   "  completed",
                "failed":      "❌ failed",
            }.get(state, state)
            print(f"    {label}: {cnt}件")


def _save_pending_snapshots(snapshots: dict) -> None:
    """
    未完了ジョブ情報をpending_snapshots.jsonに保存する。
    空dictを渡すとファイルは残るがエントリが消える。
    """
    try:
        with open(PENDING_SNAPSHOTS_PATH, "w", encoding="utf-8") as f:
            json.dump(snapshots, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        print(f"pending_snapshots.jsonへの保存に失敗しました(本処理には影響しません): {e}")


def _check_snapshot_status(snapshot_id: str) -> tuple[str, dict]:
    """
    既存のsnapshot_idの現在のstatus を返す。
    戻り値: (status_str, detail_dict)
      status_str: "ready" / "running" / "failed" / "error" / "unknown"
      detail_dict: {"http_status": N, "body": "...", "error_message": "..."}
    """
    try:
        r = _request_with_retry(
            "GET", f"{API_BASE}/datasets/v3/progress/{snapshot_id}", timeout=30
        )
        http_status = r.status_code
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text[:500]}

        status = body.get("status", "unknown") if isinstance(body, dict) else "unknown"
        error_msg = ""
        if isinstance(body, dict):
            error_msg = body.get("error") or body.get("error_message") or body.get("message") or ""
        detail = {
            "http_status": http_status,
            "body": str(body)[:300],
            "error_message": error_msg,
        }
        return status, detail
    except Exception as e:
        detail = {"http_status": 0, "body": str(e)[:300], "error_message": str(e)}
        print(f"  snapshot_id={snapshot_id}の状態確認中にエラーが発生しました: {e}")
        return "error", detail


def _save_debug_snapshot(payload) -> None:
    """
    snapshot APIから返ってきたJSONをそのままDEBUG_SNAPSHOT_PATHへ保存する。
    デバッグ用の補助出力であり、失敗してもメインの取得フローを止めない
    (ファイル書き込み権限が無い環境などでも本処理に影響させないため)。
    """
    try:
        with open(DEBUG_SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        print(f"debug_snapshot.jsonへの保存に失敗しました(本処理には影響しません): {e}")


def _extract_snapshot_items(payload) -> tuple:
    """
    snapshot APIのレスポンス(payload, json.loads済み)から投稿アイテムの
    リストを取り出す。想定する構造と優先順位は本関数の直前のコメント参照。

    戻り値: (items: list, structure: str)
    structureはどの構造として解釈したかを表す文字列(ログ・デバッグ用)。
    - "list"                    : レスポンス自体がリストだった(従来の想定)
    - "dict.<key>"               : dict内の既知キーにリストがあった
    - "dict.<key>(fallback)"     : 既知キーには無かったが、別のキーにリストがあった
    - "dict.single_item"         : リストが見つからず、dict1件をそのまま1件として扱った
    - "dict.error"                : "error"/"warning"キーがあり、エラーレスポンスと判断した
    - "unknown"                  : リスト・dictのいずれでもない(解釈不能)
    """
    if isinstance(payload, list):
        return payload, "list"

    if isinstance(payload, dict):
        for key in SNAPSHOT_LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return value, f"dict.{key}"

        for key, value in payload.items():
            if isinstance(value, list):
                return value, f"dict.{key}(fallback)"

        if "error" in payload or "warning" in payload:
            return [], "dict.error"

        return [payload], "dict.single_item"

    return [], "unknown"


def _trigger_and_collect(
    dataset_id: str,
    query: dict,
    input_list: list,
    on_snapshot_id=None,
) -> tuple:
    """
    Bright Dataの非同期フロー(trigger -> progress -> snapshot)を実行し、
    (ok, items, snapshot_id, bd_status) の4要素タプルを返す。

    - ok=True : ジョブ成功(items=0件でも成功扱い=対象期間内データ無し)
    - ok=False: trigger失敗・タイムアウト・snapshot失敗などジョブが失敗した
    - snapshot_id: trigger成功時は必ず返す(ok=Falseでも)
    - bd_status: "ready" / "running" / "failed" / "trigger_failed" / "error"

    on_snapshot_id: trigger直後に呼ぶコールバック fn(snapshot_id: str) -> None。
      プロセスがポーリング中にクラッシュしても snapshot_id を失わないよう、
      呼び出し側がここで即時永続化する。

    ジョブ単位の失敗で例外を投げることはせず、呼び出し側(_fetch_posts_for_accounts)
    がこのバッチをスキップして次のバッチに進められるようにする。
    """
    params = {"dataset_id": dataset_id, "format": "json", "include_errors": "true"}
    params.update(query)

    print(f"[API START] Bright Data trigger ({len(input_list)}アカウント)")
    try:
        trigger_resp = _request_with_retry(
            "POST", f"{API_BASE}/datasets/v3/trigger", params=params, json=input_list, timeout=60
        )
        snapshot_id = trigger_resp.json().get("snapshot_id")
        print(f"[API END] Bright Data trigger → snapshot_id={snapshot_id}")
    except requests.RequestException as e:
        print(f"[API TIMEOUT] Bright Data trigger skipped: {e}")
        return False, [], None, "trigger_failed"

    if not snapshot_id:
        print("Bright Data trigger呼び出しに失敗しました: snapshot_idが返ってきませんでした")
        return False, [], None, "trigger_failed"

    print(f"Snapshot ID: {snapshot_id}")

    # 2026-07-18: trigger直後にsnapshot_idを即時永続化する。
    # ポーリング中にプロセスがクラッシュしても snapshot_id を失わないようにするため。
    if on_snapshot_id:
        on_snapshot_id(snapshot_id)

    deadline = time.monotonic() + POLL_TIMEOUT_SEC
    status = None
    while time.monotonic() < deadline:
        try:
            print(f"[API START] Bright Data progress ({snapshot_id})")
            progress_resp = _request_with_retry(
                "GET", f"{API_BASE}/datasets/v3/progress/{snapshot_id}", timeout=30
            )
            status = progress_resp.json().get("status")
            print(f"[API END] Bright Data progress → status={status}")
        except requests.RequestException as e:
            print(f"[API TIMEOUT] Bright Data progress skipped: {e}")
            return False, [], snapshot_id, "error"

        if status == "ready":
            break
        if status == "failed":
            print(f"Bright Data APIエラー（status=failed, snapshot_id={snapshot_id}）")
            return False, [], snapshot_id, "failed"

        time.sleep(POLL_INTERVAL_SEC)
    else:
        print(
            f"Bright Dataジョブはstatus=runningのまま待機時間を超過。結果未回収"
            f"(snapshot_id={snapshot_id}, {POLL_TIMEOUT_SEC}秒経過)"
        )
        return False, [], snapshot_id, "running"

    print(f"[API START] Bright Data snapshot download ({snapshot_id})")
    try:
        snapshot_resp = _request_with_retry(
            "GET",
            f"{API_BASE}/datasets/v3/snapshot/{snapshot_id}",
            params={"format": "json"},
            timeout=60,
        )
        payload = snapshot_resp.json()
        print(f"[API END] Bright Data snapshot download 完了")
    except requests.RequestException as e:
        print(f"[API TIMEOUT] Bright Data snapshot skipped: {e}")
        return False, [], snapshot_id, "error"

    _save_debug_snapshot(payload)

    raw_items, structure = _extract_snapshot_items(payload)

    if structure == "unknown":
        print(
            "Bright Data snapshotのレスポンス形式を解釈できませんでした"
            f"(型: {type(payload).__name__})。debug_snapshot.jsonを確認してください。"
        )
        return False, [], snapshot_id, "error"

    if structure == "dict.error":
        print(f"Bright Data snapshotがエラーレスポンスを返しました: {payload}")
        return False, [], snapshot_id, "error"

    fetched_count = len(raw_items)
    items = [item for item in raw_items if isinstance(item, dict)]
    parsed_count = len(items)
    failed_count = fetched_count - parsed_count

    print(
        f"取得件数: {fetched_count}件 / 解析件数: {parsed_count}件 / "
        f"解析失敗件数: {failed_count}件 / レスポンス構造: {structure}"
    )
    return True, items, snapshot_id, "ready"


def _trigger_batch(input_list: list) -> tuple[str | None, str, dict]:
    """
    Bright Data の trigger API を呼び出し (snapshot_id, bd_status, error_detail) を返す。
    成功: (snapshot_id, "running", {})
    失敗: (None, "trigger_failed", {"http_status": N, "body": "...", "error_code": "..."})
    """
    params = {"dataset_id": REELS_DATASET_ID, "format": "json", "include_errors": "true"}
    params.update(REELS_DISCOVER_QUERY)
    try:
        resp = _request_with_retry(
            "POST", f"{API_BASE}/datasets/v3/trigger",
            params=params, json=input_list, timeout=60,
        )
        http_status = resp.status_code
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:500]}

        snapshot_id = body.get("snapshot_id") if isinstance(body, dict) else None

        if http_status >= 400 or not snapshot_id:
            error_detail = {
                "http_status": http_status,
                "body": str(body)[:500],
                "error_code": body.get("error_code", "") if isinstance(body, dict) else "",
                "error_message": body.get("message", body.get("error", "")) if isinstance(body, dict) else str(body)[:200],
            }
            print(f"  [trigger失敗] HTTP {http_status}: {error_detail['error_message'] or body}")
            return None, "trigger_failed", error_detail

    except requests.RequestException as e:
        error_detail = {"http_status": 0, "body": str(e)[:500], "error_code": "network_error", "error_message": str(e)}
        print(f"  [trigger失敗] {e}")
        return None, "trigger_failed", error_detail

    return snapshot_id, "running", {}


def _download_snapshot(snapshot_id: str) -> tuple[bool, list, str]:
    """
    ready 状態の snapshot_id からデータをダウンロードする。
    戻り値: (ok, items, bd_status)
    """
    try:
        resp = _request_with_retry(
            "GET",
            f"{API_BASE}/datasets/v3/snapshot/{snapshot_id}",
            params={"format": "json"},
            timeout=60,
        )
        payload = resp.json()
    except requests.RequestException as e:
        print(f"  [download失敗] snapshot_id={snapshot_id}: {e}")
        return False, [], "error"

    _save_debug_snapshot(payload)
    raw_items, structure = _extract_snapshot_items(payload)

    if structure in ("unknown", "dict.error"):
        print(f"  [download失敗] snapshot_id={snapshot_id}: レスポンス構造={structure}")
        return False, [], "error"

    items = [item for item in raw_items if isinstance(item, dict)]
    print(
        f"  [download完了] snapshot_id={snapshot_id}: "
        f"{len(items)}件解析済み (全{len(raw_items)}件, 構造={structure})"
    )
    return True, items, "ready"


def print_instagram_fetch_quality_report(
    posts: list,
    target_accounts: list,
    category: str = "",
) -> dict:
    """
    Instagram取得結果の品質確認レポートを表示し、品質グレードを返す。

    戻り値:
      {
        "grade": "根拠あり" / "候補" / "不足",
        "grade_label": str,   # 表示用ラベル
        "total_posts": int,
        "recent_posts": int,
        "reels_count": int,
        "account_count": int,  # 1件以上取得できたアカウント数
        "has_views": int,
        "has_followers": int,
      }
    """
    import datetime as _dt

    valid = [p for p in posts if not p.get("fetch_error")]
    total = len(valid)

    # 直近10日以内の投稿
    now = _dt.datetime.now(_dt.timezone.utc)
    cutoff10 = now - _dt.timedelta(days=10)
    recent_count = 0
    for p in valid:
        ts = p.get("timestamp") or p.get("post_date") or ""
        if ts:
            try:
                t = _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                if t > cutoff10:
                    recent_count += 1
            except Exception:
                pass

    # リール数
    reels_count = sum(1 for p in valid if p.get("is_reel") or p.get("type") == "reel")

    # 再生数・フォロワー数取得率
    has_views = sum(1 for p in valid if p.get("play_count", 0) or p.get("video_view_count", 0))
    has_followers = sum(1 for p in valid if p.get("followers") or p.get("followers_count"))

    # アカウント別取得件数
    account_counts: dict[str, int] = {}
    for p in valid:
        acct = (p.get("source_account") or p.get("username") or "").strip().lower()
        if acct:
            account_counts[acct] = account_counts.get(acct, 0) + 1
    account_count = len(account_counts)

    # 分析可能なアカウント（2件以上取得）
    analyzable = sum(1 for cnt in account_counts.values() if cnt >= 2)

    # 品質グレード
    if total >= 50 and account_count >= 20:
        grade = "根拠あり"
        grade_label = "✅ Instagramトレンド根拠あり（50投稿以上 / 20アカウント以上）"
    elif total >= 20 and account_count >= 10:
        grade = "候補"
        grade_label = "⚠️  Instagramトレンド候補（20投稿以上 / 10アカウント以上）"
    else:
        grade = "不足"
        grade_label = "❌ Instagram参考データ不足（20投稿未満 または 10アカウント未満）"

    views_rate = f"{has_views}/{total} ({100*has_views//total if total else 0}%)"
    followers_rate = f"{has_followers}/{total} ({100*has_followers//total if total else 0}%)"

    print()
    print("=" * 60)
    print(f"【Instagram取得品質レポート】{f'({category})' if category else ''}")
    print()
    print(f"  登録アカウント総数     : {len(target_accounts)}件")
    print(f"  取得投稿合計           : {total}件")
    print(f"  直近10日以内の投稿     : {recent_count}件")
    print(f"  リール数               : {reels_count}件")
    print(f"  再生数取得率           : {views_rate}")
    print(f"  フォロワー数取得率     : {followers_rate}")
    print(f"  取得成功アカウント数   : {account_count}件")
    print(f"  分析可能アカウント数   : {analyzable}件（2件以上取得）")
    print()
    print(f"  品質判定: {grade_label}")
    if grade == "不足":
        print()
        print("  ※ Instagram根拠が不足しています。")
        print("    生成テーマは「Instagramトレンド」ではなく")
        print("    「季節・専門知識から作った投稿仮説」として扱います。")
    print("=" * 60)
    print()

    return {
        "grade": grade,
        "grade_label": grade_label,
        "total_posts": total,
        "recent_posts": recent_count,
        "reels_count": reels_count,
        "account_count": account_count,
        "has_views": has_views,
        "has_followers": has_followers,
    }


def _print_batch_fetch_summary(
    posts: list,
    snapshot_meta: list,
    batches: list,
    failed_accounts: list,
    category: str,
) -> None:
    """
    全バッチ完了後にアカウント別・バッチ別の取得結果サマリーを表示する。
    【2026-07-20追加】
    """
    # アカウント別取得件数
    account_counts: dict[str, int] = {}
    for p in posts:
        if p.get("fetch_error"):
            continue
        acct = (p.get("source_account") or p.get("username") or "").strip().lower()
        if acct:
            account_counts[acct] = account_counts.get(acct, 0) + 1

    # バッチ別取得件数
    batch_post_counts: dict[str, int] = {}
    for meta in snapshot_meta:
        batch_accounts = [a.lower() for a in meta.get("accounts", [])]
        count = sum(account_counts.get(a, 0) for a in batch_accounts)
        batch_post_counts[meta.get("batch_key", "")] = count

    failed_set = {a.lower() for a in failed_accounts}

    print()
    print("=" * 60)
    print("【取得結果サマリー】")
    print()

    # ① アカウント別
    all_batch_accounts = [u for batch in batches for u in batch]
    print("  アカウント別取得件数:")
    for acct in all_batch_accounts:
        cnt = account_counts.get(acct.lower(), 0)
        status = "失敗" if acct.lower() in failed_set else ("0件" if cnt == 0 else f"{cnt}件")
        print(f"    {acct}: {status}")

    print()

    # ② バッチ別
    print("  バッチ別結果:")
    for bi, (meta, batch) in enumerate(zip(snapshot_meta, batches), 1):
        bd_status = meta.get("bd_status", "")
        acct_names = ", ".join(batch)
        batch_key = "|".join(sorted(batch))
        cnt = batch_post_counts.get(batch_key, 0)
        status_label = "成功" if bd_status == "ready" else bd_status
        print(f"    バッチ{bi}/{len(batches)} [{status_label}] {acct_names} → {cnt}件")

    # スキップされたバッチ（snapshot_metaにない）
    if len(snapshot_meta) < len(batches):
        for bi in range(len(snapshot_meta) + 1, len(batches) + 1):
            print(f"    バッチ{bi}/{len(batches)} [スキップ] (全体タイムアウトにより未実行)")

    print()

    # ③ 集計
    completed = sum(1 for m in snapshot_meta if m.get("bd_status") == "ready")
    failed = sum(1 for m in snapshot_meta if m.get("bd_status") not in ("ready", "recovered"))
    skipped = len(batches) - len(snapshot_meta)
    succeeded_accounts = len(
        {a.lower() for a in all_batch_accounts if a.lower() not in failed_set and account_counts.get(a.lower(), 0) > 0}
    )
    print(f"  完了バッチ: {completed}/{len(batches)}件")
    if failed:
        print(f"  失敗バッチ: {failed}件")
    if skipped:
        print(f"  スキップ:   {skipped}件 (全体タイムアウト)")
    print(f"  取得成功アカウント: {succeeded_accounts}/{len(all_batch_accounts)}件")
    print(f"  取得投稿合計: {len([p for p in posts if not p.get('fetch_error')])}件")

    # ⑥ 取得できたアカウントが5未満の場合は警告
    if succeeded_accounts < 5 and len(all_batch_accounts) >= 5:
        print()
        print("  ⚠️  取得処理に異常がある可能性があります")
        print(f"     実際に取得できたアカウント: {succeeded_accounts}件 / 対象: {len(all_batch_accounts)}件")
        if TEST_MODE:
            print("     テストモードが有効です (BRIGHT_DATA_TEST_MODE=1)")
        else:
            print("     Bright Data API の状態・ネットワーク接続を確認してください")

    print("=" * 60)
    print()


def _fetch_posts_for_accounts(accounts: list, category: str, results_limit: int) -> dict:
    """
    2026-07-18: 戻り値を list から dict に変更。
      {
        "posts": list[dict],
        "snapshot_meta": list[dict],  # バッチごとのsnapshot追跡情報
      }
    snapshot_meta の各エントリ:
      {
        "batch_key": str,
        "snapshot_id": str | None,
        "bd_status": str,     # "ready"/"running"/"failed"/"trigger_failed"/"error"/"recovered"
        "error_msg": str,
        "accounts": list,
        "recovered": bool,    # 前回pending→今回ready になった場合 True
      }
    """
    posts = []
    snapshot_meta = []

    registered_count = len([a for a in accounts if a and a.strip()])
    usernames = [_to_username(a) for a in accounts if a and a.strip()]
    if not usernames:
        print(f"{category}: 取得対象アカウントが0件です(競合発見の結果0件、または該当カテゴリで競合候補が見つかりませんでした)")
        return {"posts": posts, "snapshot_meta": snapshot_meta}

    usernames = _apply_test_mode_limit(usernames, category)
    if not usernames:
        return {"posts": posts, "snapshot_meta": snapshot_meta}

    # 本番モードなのに対象が5件以下で登録アカウントが多い場合は設定ミスの可能性を警告
    if not TEST_MODE and len(usernames) <= 5 and registered_count > 5:
        print()
        print("=" * 60)
        print("⚠️  警告: 取得処理に異常がある可能性があります")
        print(f"   登録アカウント数: {registered_count}件")
        print(f"   今回の対象数: {len(usernames)}件")
        print("   テストモード設定またはアカウント上限が残っています")
        print("   BRIGHT_DATA_TEST_MODE 環境変数を確認してください")
        print("=" * 60)
        print()

    # 直近RECENT_DAYS日より古いリールは取得時点で除外し、無駄な取得コストを減らす
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=RECENT_DAYS)
    start_date = cutoff.strftime("%m-%d-%Y")
    end_date = now.strftime("%m-%d-%Y")

    # 1ジョブに大量のアカウントを詰め込むとタイムアウトするため、
    # ACCOUNTS_PER_BATCH件ずつの小さなジョブに分割して順番に取得する。
    batches = [
        usernames[i : i + ACCOUNTS_PER_BATCH]
        for i in range(0, len(usernames), ACCOUNTS_PER_BATCH)
    ]

    # ── 実行モード表示 ────────────────────────────────────────────────────────
    mode_label = "テスト" if TEST_MODE else "本番"
    print()
    print("=" * 60)
    print(f"実行モード          : {mode_label}")
    print(f"登録アカウント数    : {registered_count}件")
    print(f"今回の対象アカウント: {len(usernames)}件")
    print(f"バッチ数            : {len(batches)}バッチ (1バッチ最大{ACCOUNTS_PER_BATCH}件)")
    print()
    print("【対象アカウント一覧】")
    for i, u in enumerate(usernames, 1):
        print(f"  {i:2}. {u}")
    print()
    print("【バッチ計画】")
    for bi, batch in enumerate(batches, 1):
        print(f"  バッチ{bi}/{len(batches)}: {', '.join(batch)}")
    print("=" * 60)
    print()

    # ── ドライランモード: APIを呼ばずに終了 ──────────────────────────────────
    if DRY_RUN:
        print("[ドライラン] Bright Data API は呼び出しません。計画の確認が完了しました。")
        print("[ドライラン] 本番実行するには --dry-run オプションを外してください。")
        return {"posts": [], "snapshot_meta": [], "dry_run": True}

    print(
        f"取得中: {category} / {len(usernames)}アカウントを{len(batches)}バッチに分割"
        f"(1バッチ最大{ACCOUNTS_PER_BATCH}アカウント, 1アカウント最大{results_limit}件)"
    )

    # 前回タイムアウトした未完了ジョブのsnapshot_idを読み込む。
    pending = _load_pending_snapshots()
    updated_pending = dict(pending)

    # ── pending 健全性チェック ─────────────────────────────────────────────
    _print_pending_health(pending)
    trigger_allowed, trigger_block_reason = _check_trigger_allowed(pending)
    if not trigger_allowed:
        print()
        print("=" * 70)
        print(trigger_block_reason)
        print("=" * 70)
        print()
        return {
            "posts": [],
            "snapshot_meta": [],
            "bd_outage": True,
            "outage_reason": trigger_block_reason,
        }

    failed_accounts = []
    fetch_start = time.monotonic()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # フェーズ1: 全バッチを一括 trigger（非同期化の核心）
    # 各バッチごとに trigger → 即時 snapshot_id 取得。待たずに次へ進む。
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # running_jobs: {batch_key: {snapshot_id, accounts, batch_index}} — ポーリング対象
    running_jobs: dict[str, dict] = {}

    print()
    print(f"  ─ フェーズ1: 全{len(batches)}バッチを一括 trigger ─")
    for batch_index, batch_usernames in enumerate(batches, start=1):
        batch_key = "|".join(sorted(batch_usernames))

        # 前回未完了ジョブがある場合: 状態確認してrunningならそのまま流用、readyなら後でdownload
        if batch_key in pending:
            pending_sid = pending[batch_key].get("snapshot_id")
            # 【pending 再利用の正常性確認 (2026-07-20)】
            # Bright Data のスナップショットは作成後 24 時間程度で破棄される場合がある。
            # triggered_at から経過時間を確認し、古すぎる pending は新規 trigger する。
            triggered_at_str = pending[batch_key].get("triggered_at", "")
            pending_stale = False
            if triggered_at_str:
                try:
                    triggered_dt = dt.datetime.fromisoformat(triggered_at_str.replace("Z", "+00:00"))
                    age_hours = (now - triggered_dt).total_seconds() / 3600
                    if age_hours > 20:
                        print(
                            f"  バッチ{batch_index}: pending snapshot_id={pending_sid} は"
                            f" {age_hours:.1f}時間前のものです（20時間超 → 新規triggerに切り替え）"
                        )
                        pending_stale = True
                        del updated_pending[batch_key]
                except Exception:
                    pass
            if pending_stale:
                pass  # fallthrough to new trigger
            else:
                status, _status_detail = _check_snapshot_status(pending_sid)
                dashboard_url = BD_SNAPSHOT_DASHBOARD_URL.format(snapshot_id=pending_sid)
                state = _classify_snapshot_state({**pending[batch_key], "bd_status": status})
                print(
                    f"  バッチ{batch_index}/{len(batches)}: "
                    f"前回pending snapshot_id={pending_sid} → status={status} [{state}]"
                )
                print(f"    Dashboard: {dashboard_url}")
                if _status_detail.get("error_message"):
                    print(f"    ⚠️  error: {_status_detail['error_message']}")
                if status in ("ready", "running"):
                    running_jobs[batch_key] = {
                        "snapshot_id":    pending_sid,
                        "accounts":       batch_usernames,
                        "batch_index":    batch_index,
                        "recovered":      status == "ready",
                        "triggered_at_iso": pending[batch_key].get("triggered_at", ""),
                    }
                    continue
                elif status == "failed":
                    del updated_pending[batch_key]
                    # fallthrough: 新規trigger
                else:
                    del updated_pending[batch_key]

        input_list = [
            {
                "url": _to_profile_url(username),
                "num_of_posts": results_limit,
                "start_date": start_date,
                "end_date": end_date,
            }
            for username in batch_usernames
        ]
        print(
            f"  バッチ{batch_index}/{len(batches)}: trigger → "
            f"{', '.join(batch_usernames)}"
        )
        snapshot_id, bd_status, trigger_error = _trigger_batch(input_list)

        if snapshot_id is None:
            err_body = trigger_error.get("body", "")
            err_code = trigger_error.get("error_code", "")
            err_msg  = trigger_error.get("error_message", "")
            http_st  = trigger_error.get("http_status", 0)
            print(f"  バッチ{batch_index}: trigger 失敗 (HTTP {http_st}) → スキップ")
            if err_msg:
                print(f"    error: {err_msg}")
            failed_accounts.extend(batch_usernames)
            snapshot_meta.append({
                "batch_key":   batch_key,
                "snapshot_id": None,
                "bd_status":   "trigger_failed",
                "error_msg":   f"HTTP {http_st} / {err_msg or err_code or err_body[:100]}",
                "accounts":    batch_usernames,
                "recovered":   False,
            })
            continue

        # 重複保存チェック: 同じ snapshot_id が既に pending にある場合はスキップ
        existing_sids = {v.get("snapshot_id") for v in updated_pending.values()}
        if snapshot_id in existing_sids:
            print(f"  バッチ{batch_index}: snapshot_id={snapshot_id} は既に pending に存在 → 重複スキップ")
        else:
            dashboard_url = BD_SNAPSHOT_DASHBOARD_URL.format(snapshot_id=snapshot_id)
            print(f"  バッチ{batch_index}: snapshot_id={snapshot_id} 取得 → ポーリング待機へ")
            print(f"    Dashboard: {dashboard_url}")
            # trigger直後に即時永続化
            updated_pending[batch_key] = {
                "snapshot_id":    snapshot_id,
                "accounts":       batch_usernames,
                "triggered_at":   now.isoformat(),
                "bd_status":      "running",
            }
            _save_pending_snapshots(updated_pending)

        running_jobs[batch_key] = {
            "snapshot_id":    snapshot_id,
            "accounts":       batch_usernames,
            "batch_index":    batch_index,
            "recovered":      False,
            "triggered_at_iso": now.isoformat(),
        }

    print(f"  ─ フェーズ1完了: {len(running_jobs)}バッチのtrigger成功 ─")
    print()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # フェーズ2: 全スナップショットを巡回ポーリング → ready になり次第 download
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    remaining_jobs = dict(running_jobs)  # コピー: 完了したものは削除していく
    poll_deadline = fetch_start + FETCH_TOTAL_BUDGET_SEC

    print(f"  ─ フェーズ2: {len(remaining_jobs)}バッチのポーリング開始 ─")

    while remaining_jobs:
        elapsed = time.monotonic() - fetch_start
        if time.monotonic() >= poll_deadline:
            timed_out = list(remaining_jobs.keys())
            print(
                f"  [タイムアウト] 全体予算{FETCH_TOTAL_BUDGET_SEC}秒を超過({elapsed:.0f}秒)。"
                f"残り{len(timed_out)}バッチを未回収としてpending保存します。"
            )
            for bkey in timed_out:
                job = remaining_jobs[bkey]
                failed_accounts.extend(job["accounts"])
                snapshot_meta.append({
                    "batch_key": bkey,
                    "snapshot_id": job["snapshot_id"],
                    "bd_status": "running",
                    "error_msg": "全体タイムアウトにより未回収",
                    "accounts": job["accounts"],
                    "recovered": False,
                })
                if bkey in updated_pending:
                    updated_pending[bkey]["bd_status"] = "running"
            break

        completed_this_round = []
        for bkey, job in remaining_jobs.items():
            sid = job["snapshot_id"]
            bi = job["batch_index"]
            batch_usernames = job["accounts"]
            already_ready = job.get("recovered", False)

            if already_ready:
                status = "ready"
                _status_detail = {}
            else:
                status, _status_detail = _check_snapshot_status(sid)
                age_min = _snapshot_age_minutes(job.get("triggered_at_iso", ""))
                state_label = _classify_snapshot_state({"snapshot_id": sid, "bd_status": status, "triggered_at": job.get("triggered_at_iso", "")})
                age_str = f"{age_min:.0f}分経過" if age_min >= 0 else ""
                print(
                    f"  バッチ{bi}/{len(batches)} [{', '.join(batch_usernames[:2])}{'...' if len(batch_usernames)>2 else ''}]"
                    f" snapshot_id={sid} → status={status} [{state_label}] {age_str}"
                )
                if _status_detail.get("error_message"):
                    print(f"    ⚠️  error: {_status_detail['error_message']}")

            if status == "ready":
                ok, items, dl_status = _download_snapshot(sid)
                completed_this_round.append(bkey)

                if not ok:
                    failed_accounts.extend(batch_usernames)
                    snapshot_meta.append({
                        "batch_key": bkey,
                        "snapshot_id": sid,
                        "bd_status": "error",
                        "error_msg": "download失敗",
                        "accounts": batch_usernames,
                        "recovered": job.get("recovered", False),
                    })
                    if bkey in updated_pending:
                        del updated_pending[bkey]
                    continue

                # download 成功
                recovered_flag = job.get("recovered", False)
                if bkey in updated_pending:
                    del updated_pending[bkey]

                if not items:
                    print(
                        f"  バッチ{bi}: 0件でした"
                        f"(対象期間内に投稿なし): {', '.join(batch_usernames)}"
                    )

                # エラー投稿ログ
                error_items = [item for item in items if _is_error_item(item)]
                if error_items:
                    print(
                        f"  バッチ{bi}: {len(error_items)}/{len(items)}件が取得失敗または空データ"
                    )
                    seen_targets: set = set()
                    for item in error_items:
                        desc = _describe_error_item(item)
                        target = desc.split(":", 1)[0]
                        if target not in seen_targets:
                            seen_targets.add(target)
                            print(f"    - {desc}")

                for item in items:
                    owner_username = _get_first(item, ["user_posted"], "") or ""
                    posts.append(
                        _normalize_post(item, source_account=owner_username, category=category)
                    )

                snapshot_meta.append({
                    "batch_key": bkey,
                    "snapshot_id": sid,
                    "bd_status": "ready",
                    "error_msg": "",
                    "accounts": batch_usernames,
                    "recovered": recovered_flag,
                    **({"recovered_count": len(items)} if recovered_flag else {}),
                })

            elif status == "failed":
                completed_this_round.append(bkey)
                print(f"  バッチ{bi}: Bright Data APIエラー（status=failed, snapshot_id={sid}）")
                failed_accounts.extend(batch_usernames)
                snapshot_meta.append({
                    "batch_key": bkey,
                    "snapshot_id": sid,
                    "bd_status": "failed",
                    "error_msg": "Bright Data APIエラー（status=failed）",
                    "accounts": batch_usernames,
                    "recovered": False,
                })
                if bkey in updated_pending:
                    del updated_pending[bkey]

            elif status == "error":
                completed_this_round.append(bkey)
                failed_accounts.extend(batch_usernames)
                snapshot_meta.append({
                    "batch_key": bkey,
                    "snapshot_id": sid,
                    "bd_status": "error",
                    "error_msg": "progress API 呼び出し失敗",
                    "accounts": batch_usernames,
                    "recovered": False,
                })

            # running の場合は次のラウンドへ

        for bkey in completed_this_round:
            del remaining_jobs[bkey]

        if remaining_jobs:
            elapsed = time.monotonic() - fetch_start
            remaining_secs = poll_deadline - time.monotonic()
            print(
                f"  ─ {len(remaining_jobs)}バッチまだ処理中。"
                f"{POLL_INTERVAL_SEC}秒後に再確認 (残り{remaining_secs:.0f}秒) ─"
            )
            time.sleep(POLL_INTERVAL_SEC)

    print(f"  ─ フェーズ2完了 ─")
    print()

    if failed_accounts:
        print(
            f"{category}: 取得失敗(ジョブ失敗/タイムアウト)したアカウント"
            f"({len(failed_accounts)}件): {', '.join(failed_accounts)}"
        )

    # ── バッチ完了サマリー ────────────────────────────────────────────────────
    _print_batch_fetch_summary(posts, snapshot_meta, batches, failed_accounts, category)

    # ── Instagram取得品質レポート ────────────────────────────────────────────
    quality = print_instagram_fetch_quality_report(posts, usernames, category)
    # quality["grade"] は fetch_trend_posts の呼び出し元へ伝搬させるために保持
    # (現状はログ表示のみ; 将来 main.py で参照できるよう戻り値に含める)

    # 2026-07-18: 未完了ジョブ情報を書き戻す(変更があった場合のみ)
    if updated_pending != pending:
        _save_pending_snapshots(updated_pending)
        if updated_pending:
            print(
                f"未完了ジョブ {len(updated_pending)}件をpending_snapshots.jsonに保存しました。"
                f"次回実行時に自動再確認します"
            )

    return {"posts": posts, "snapshot_meta": snapshot_meta, "ig_quality": quality}


def _attach_account_post_counts(posts: list) -> None:
    """
    【2026-06-29(6回目)】trend_score.py の「投稿頻度」評価項目の入力として使う
    post["account_post_count_window"]を全件に付与する(in-place)。

    値は「今回の取得窓内(直近RECENT_DAYS日以内・1アカウントあたり最大
    DEFAULT_RESULTS_PER_ACCOUNT件)で、同じsource_accountから実際に取得できた
    投稿数」。取得失敗(fetch_error)のアイテムはカウントに含めない
    (実在する投稿の数のみを数える)。
    """
    counts = {}
    for post in posts:
        if post.get("fetch_error"):
            continue
        key = post.get("source_account") or post.get("username") or ""
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1

    for post in posts:
        key = post.get("source_account") or post.get("username") or ""
        post["account_post_count_window"] = counts.get(key, 0)


def fetch_trend_posts(
    accounts: list, results_limit: int = DEFAULT_RESULTS_PER_ACCOUNT
) -> dict:
    """
    accounts: accounts.py の ANTENNA_ACCOUNTS(ジャンル不問のアンテナアカウント)。

    2026-07-18: 戻り値を list から dict に変更。
      {"posts": list, "snapshot_meta": list}

    取得結果は全件category=CATEGORY_ALLになる。①Instagram全体トレンド+
    ②美容ジャンルトレンドの2カテゴリに分けたい場合は、戻り値["posts"]に対して
    apply_beauty_category()を呼ぶこと(main.py参照。2026-07-02)。
    """
    fetch_result = _fetch_posts_for_accounts(accounts, CATEGORY_ALL, results_limit)
    posts = fetch_result["posts"]
    _attach_account_post_counts(posts)
    return {"posts": posts, "snapshot_meta": fetch_result["snapshot_meta"]}


def apply_beauty_category(posts: list, beauty_usernames) -> list:
    """
    【2026-07-02追加: item5「Instagram全体トレンド+美容ジャンルトレンドの
    統合」対応】
    fetch_trend_posts()は1回の取得で済ませるため、全投稿が一旦
    category=CATEGORY_ALLとして返ってくる。本関数は、投稿の取得元アカウント
    (source_account、無ければusername)がbeauty_usernamesに含まれる場合だけ、
    その投稿のcategoryをCATEGORY_BEAUTYに事後的に上書きする(Bright Dataへの
    再取得は発生しない=取得コストは増えない)。

    posts自体をin-placeで変更し、同じリストを返す(他の保存・分析処理が同じ
    postオブジェクトを参照していても反映されるようにするため)。
    比較は大文字小文字を無視し、先頭の"@"を取り除いて行う。
    """
    normalized_beauty = {
        str(u).lstrip("@").strip().lower() for u in (beauty_usernames or [])
    }
    if not normalized_beauty:
        return posts

    for post in posts or []:
        account = (post.get("source_account") or post.get("username") or "")
        account = str(account).lstrip("@").strip().lower()
        if account in normalized_beauty:
            post["category"] = CATEGORY_BEAUTY

    return posts


def engagement_score(post: dict) -> int:
    return (
        post.get("views", 0)
        + post.get("likes", 0) * 3
        + post.get("comments", 0) * 5
    )


def dedupe_by_url(posts: list) -> list:
    """投稿URL(無ければユーザー名+キャプション)が同じ投稿の重複を取り除く。"""
    best_by_key = {}

    for post in posts:
        key = post.get("url") or f"{post.get('username')}|{post.get('caption')}"
        if not key:
            continue

        current_best = best_by_key.get(key)
        if current_best is None or engagement_score(post) > engagement_score(current_best):
            best_by_key[key] = post

    return list(best_by_key.values())


_PR_KEYWORDS = ("PR", "提供", "案件", "タイアップ", "広告", "ギフテッド", "gifted", "sponsored")


def _is_pr_post(post: dict) -> bool:
    """キャプションまたはハッシュタグにPR関連キーワードが含まれているか判定する。"""
    caption = (post.get("caption") or "").lower()
    # hashtags リストは "#" なしの文字列で格納されている
    hashtags_lower = {h.lower().lstrip("#") for h in (post.get("hashtags") or [])}

    # ハッシュタグリストに "pr" が含まれていれば即PR判定
    if "pr" in hashtags_lower or "広告" in hashtags_lower:
        return True

    # キャプション内の "#pr" / "【pr】" パターン
    if "#pr" in caption or "【pr】" in caption or "[pr]" in caption:
        return True
    if "#広告" in caption or "【広告】" in caption:
        return True

    # 「提供」「案件」「タイアップ」「ギフテッド」はキャプション・ハッシュタグに含まれていれば除外
    soft_keywords = ("提供", "案件", "タイアップ", "ギフテッド", "gifted", "sponsored")
    for kw in soft_keywords:
        kw_lower = kw.lower()
        if kw_lower in caption:
            return True
        if kw_lower in hashtags_lower:
            return True

    return False


def _classify_pool_exclusion(post: dict, cutoff) -> tuple:
    """
    投稿が「構造的に分析対象として成立するデータかどうか」だけを判定する。
    再生数・再生倍率・フォロワー数の有無による判断はここでは行わない
    (trend_score.pyの連続スコアに委ねる。本ファイル末尾の【2026-06-30】
    セクション参照)。

    【2026-07-20】PR投稿フィルタを追加。#PR・提供・案件・タイアップ・広告等の
    キーワードを含む投稿は除外する（除外理由: "PR投稿"）。

    戻り値: (stats_key, human_reason)。stats_keyが""なら除外なし(プール入り)。
    human_reasonはraw_fetch_logシートの「除外理由」列にそのまま使う文言。
    """
    if post.get("fetch_error"):
        return "excluded_fetch_error", "取得失敗(Bright Dataがエラー/空データを返した)"

    if not post.get("is_reel"):
        return "excluded_not_reel", "リール以外の投稿"

    posted_at_dt = post.get("posted_at_dt")
    if posted_at_dt is None:
        return "excluded_date", "投稿日が取得できない"

    if posted_at_dt < cutoff:
        days_old = int((dt.datetime.now(dt.timezone.utc) - posted_at_dt).total_seconds() // 86400)
        return "excluded_date", f"投稿日が古い(約{days_old}日前、直近{RECENT_DAYS}日より前)"

    if _is_pr_post(post):
        return "excluded_pr", "PR投稿"

    return "", ""


def build_post_pool(posts: list) -> dict:
    """
    取得した投稿のうち、構造的に分析対象として成立するもの全件を
    「プール」として返す(2026-06-30: 旧filter_and_adoptの再設計。
    本ファイル末尾の【2026-06-30】セクション参照)。

    旧版と異なり、以下は一切行わない:
    - 再生数・再生倍率・フォロワー数の有無による除外
    - 上位N件への絞り込み(旧TARGET_ADOPTED_COUNT)

    除外するのは「取得失敗」「リール以外」「投稿日が古い」の3種類のみ。
    各投稿には判定結果としてpost["pool_exclusion_reason"](空文字列なら
    除外なし)を付与する(除外された投稿を含む、posts全件に対して行う)。

    戻り値:
    {
        "pool": list[dict],   # 構造的に使える投稿全件(順序は取得順のまま)
        "stats": {
            "fetched": int,
            "excluded_fetch_error": int,
            "excluded_not_reel": int,
            "excluded_date": int,
            "no_followers_count": int,  # 除外ではなく情報用。再生倍率が0点になるだけ
            "pool_count": int,
        },
    }
    """
    stats = {
        "fetched": len(posts),
        "excluded_fetch_error": 0,
        "excluded_not_reel": 0,
        "excluded_date": 0,
        "excluded_pr": 0,
        "excluded_product_reviewer": 0,
        "no_followers_count": 0,
        "pool_count": 0,
    }

    fetch_error_count = sum(1 for p in posts if p.get("fetch_error"))
    real_posts = [p for p in posts if not p.get("fetch_error")]
    reel_count = sum(1 for p in real_posts if p.get("is_reel"))

    if posts and fetch_error_count == len(posts):
        print(
            "全件が取得失敗または空データでした"
            "(Bright Dataのジョブ状況/APIキー/対象アカウントを確認してください)"
        )
    elif real_posts and reel_count == 0:
        print("通常投稿しか取得できていません(リールが0件のため、再生数の評価ができません)")

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=RECENT_DAYS)
    pool = []

    for post in posts:
        stats_key, reason = _classify_pool_exclusion(post, cutoff)
        post["pool_exclusion_reason"] = reason

        if stats_key:
            stats[stats_key] += 1
            continue

        if post.get("followers") is None:
            stats["no_followers_count"] += 1

        pool.append(post)

    # 商品レビュー主体アカウントを除外
    # 同一アカウントがPR除外された投稿を2件以上持つ場合、そのアカウントのpool内投稿も除外
    pr_excluded_by_account: dict[str, int] = {}
    for post in posts:
        if post.get("pool_exclusion_reason") == "PR投稿":
            acct = (post.get("username") or post.get("source_account") or "").strip().lower()
            if acct:
                pr_excluded_by_account[acct] = pr_excluded_by_account.get(acct, 0) + 1

    product_reviewer_accounts = {acct for acct, cnt in pr_excluded_by_account.items() if cnt >= 2}

    if product_reviewer_accounts:
        filtered_pool = []
        for post in pool:
            acct = (post.get("username") or post.get("source_account") or "").strip().lower()
            if acct in product_reviewer_accounts:
                post["pool_exclusion_reason"] = "商品レビュー主体"
                stats["excluded_product_reviewer"] += 1
            else:
                filtered_pool.append(post)
        pool = filtered_pool

    pool = dedupe_by_url(pool)
    stats["pool_count"] = len(pool)

    return {"pool": pool, "stats": stats}
