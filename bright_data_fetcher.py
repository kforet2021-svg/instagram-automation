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
ACCOUNTS_PER_BATCH = 5  # 1回のBright Dataジョブで取得するアカウント数の上限(3〜5件)
DEFAULT_RESULTS_PER_ACCOUNT = 8  # 1アカウントあたり取得する最新投稿数(5〜10件)

# --- ポーリング設定 ---
# 2026-06-29(3回目): 実際に運用したところ、ACCOUNTS_PER_BATCH=5・
# 1アカウント8件という小さなバッチでもPOLL_TIMEOUT_SEC=120秒では
# 毎回タイムアウトし、採用件数が0件になる事象が発生した。
# (Discover by URLは非同期スクレイピングのため、バッチが小さくても
#  数分かかることがある)。バッチを縮小したのは元々「1ジョブに大量の
# アカウント・投稿数を詰め込むと600秒でもタイムアウトする」問題への
# 対処だったため、120秒は不要に短すぎた。バッチサイズはそのままに
# 待ち時間だけ300秒に伸ばす。
POLL_INTERVAL_SEC = 15  # 2026-07-18: 5→15秒に変更。600秒タイムアウト時のAPI呼び出し過剰防止。
POLL_TIMEOUT_SEC = 600  # 2026-07-18: 150→600秒に変更。Discover by URLは数分かかることが多い。
# タイムアウト時はsnapshot_idをPENDING_SNAPSHOTS_PATHに保存し、次回実行時に再確認する。
# 【2026-07-02(10回目): 全バッチを合計した最大取得時間。これを超えたら残りのバッチは
#   スキップして後続のOpenAI分析・Creator Studioへ進む(10分以内完了要件対応)】
FETCH_TOTAL_BUDGET_SEC = 300  # Bright Data全体に許可する最大秒数(5分)

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
# 大量取得でのタイムアウトを避けるため、安定動作を確認できるまでは
# 1回の実行で最大TEST_MODE_MAX_TOTAL_ACCOUNTS件までしか取得しないようにする。
# 安定して動くことを確認できたら TEST_MODE = False に変更すれば、
# accounts.py の ANTENNA_ACCOUNTS 全件を取得対象にできる。
TEST_MODE = True
TEST_MODE_MAX_TOTAL_ACCOUNTS = 5

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


def _apply_test_mode_limit(usernames: list, category: str) -> list:
    """
    TEST_MODE中は、1回の実行でTEST_MODE_MAX_TOTAL_ACCOUNTS件までしか
    アカウントを取得対象にしない。
    """
    if not TEST_MODE:
        return usernames

    limited = usernames[:TEST_MODE_MAX_TOTAL_ACCOUNTS]
    if len(limited) < len(usernames):
        print(
            f"{category}: テストモード(最大{TEST_MODE_MAX_TOTAL_ACCOUNTS}アカウントまで)のため、"
            f"{len(usernames)}件中{len(limited)}件のみ取得します"
        )
    return limited


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


def _check_snapshot_status(snapshot_id: str) -> str:
    """
    既存のsnapshot_idの現在のstatus("ready"/"running"/"failed"/エラー時"error")を返す。
    """
    try:
        progress_resp = _request_with_retry(
            "GET", f"{API_BASE}/datasets/v3/progress/{snapshot_id}", timeout=30
        )
        return progress_resp.json().get("status", "unknown")
    except Exception as e:
        print(f"snapshot_id={snapshot_id}の状態確認中にエラーが発生しました: {e}")
        return "error"


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

    usernames = [_to_username(a) for a in accounts if a and a.strip()]
    if not usernames:
        print(f"{category}: 取得対象アカウントが0件です(競合発見の結果0件、または該当カテゴリで競合候補が見つかりませんでした)")
        return {"posts": posts, "snapshot_meta": snapshot_meta}

    usernames = _apply_test_mode_limit(usernames, category)
    if not usernames:
        return {"posts": posts, "snapshot_meta": snapshot_meta}

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

    print(
        f"取得中: {category} / {len(usernames)}アカウントを{len(batches)}バッチに分割"
        f"(1バッチ最大{ACCOUNTS_PER_BATCH}アカウント, 1アカウント最大{results_limit}件)"
    )

    # 2026-07-18: 前回タイムアウトした未完了ジョブのsnapshot_idを読み込む。
    # 同じバッチキーで重複ジョブを作らないための排他制御にも使う。
    pending = _load_pending_snapshots()
    updated_pending = dict(pending)  # 書き戻し用コピー

    failed_accounts = []
    fetch_start = time.monotonic()

    for batch_index, batch_usernames in enumerate(batches, start=1):
        elapsed = time.monotonic() - fetch_start
        if elapsed >= FETCH_TOTAL_BUDGET_SEC:
            remaining = len(batches) - batch_index + 1
            print(
                f"[API TIMEOUT] Bright Data 全体予算{FETCH_TOTAL_BUDGET_SEC}秒を超過({elapsed:.0f}秒経過)。"
                f"残り{remaining}バッチをスキップして次の処理へ進みます。"
            )
            failed_accounts.extend(
                u for b in batches[batch_index - 1:] for u in b
            )
            break

        # バッチキー: アカウント名ソート済み文字列で一意に識別
        batch_key = "|".join(sorted(batch_usernames))

        # 2026-07-18: 前回未完了のsnapshot_idがある場合は先に状態確認する
        if batch_key in pending:
            pending_info = pending[batch_key]
            pending_sid = pending_info.get("snapshot_id")
            print(
                f"  [{category}] バッチ{batch_index}: 前回未完了snapshot_id={pending_sid}を確認中..."
            )
            status = _check_snapshot_status(pending_sid)
            if status == "ready":
                print(f"  [{category}] バッチ{batch_index}: snapshot準備完了(status=ready)。結果を取得します")
                recovered_count = 0
                try:
                    snapshot_resp = _request_with_retry(
                        "GET",
                        f"{API_BASE}/datasets/v3/snapshot/{pending_sid}",
                        params={"format": "json"},
                        timeout=60,
                    )
                    payload = snapshot_resp.json()
                    _save_debug_snapshot(payload)
                    raw_items, structure = _extract_snapshot_items(payload)
                    items = [item for item in raw_items if isinstance(item, dict)]
                    recovered_count = len(items)
                    print(f"  [{category}] バッチ{batch_index}: 未完了ジョブから{recovered_count}件取得しました")
                    for item in raw_items:
                        owner_username = _get_first(item, ["user_posted"], "") or ""
                        posts.append(
                            _normalize_post(item, source_account=owner_username, category=category)
                        )
                    del updated_pending[batch_key]
                    snapshot_meta.append({
                        "batch_key": batch_key,
                        "snapshot_id": pending_sid,
                        "bd_status": "recovered",
                        "error_msg": "",
                        "accounts": batch_usernames,
                        "recovered": True,
                        "recovered_count": recovered_count,
                    })
                except Exception as e:
                    err = f"未完了ジョブの取得中にエラー: {e}"
                    print(f"  [{category}] バッチ{batch_index}: {err}")
                    snapshot_meta.append({
                        "batch_key": batch_key,
                        "snapshot_id": pending_sid,
                        "bd_status": "error",
                        "error_msg": err,
                        "accounts": batch_usernames,
                        "recovered": False,
                    })
                continue
            elif status == "running":
                msg = f"Bright Dataジョブはstatus=runningのまま待機時間を超過。結果未回収(snapshot_id={pending_sid})"
                print(
                    f"  [{category}] バッチ{batch_index}: まだ処理中(status=running)です。"
                    f"このバッチはスキップして次回確認します(snapshot_id={pending_sid})"
                )
                failed_accounts.extend(batch_usernames)
                snapshot_meta.append({
                    "batch_key": batch_key,
                    "snapshot_id": pending_sid,
                    "bd_status": "running",
                    "error_msg": msg,
                    "accounts": batch_usernames,
                    "recovered": False,
                })
                continue
            elif status == "failed":
                print(
                    f"  [{category}] バッチ{batch_index}: Bright Data APIエラー（status=failed）。"
                    f"snapshot_id={pending_sid}"
                )
                snapshot_meta.append({
                    "batch_key": batch_key,
                    "snapshot_id": pending_sid,
                    "bd_status": "failed",
                    "error_msg": "Bright Data APIエラー（status=failed）",
                    "accounts": batch_usernames,
                    "recovered": False,
                })
                del updated_pending[batch_key]
                # fallthrough: 新規ジョブを作成する
            else:
                print(f"  [{category}] バッチ{batch_index}: 状態不明(status={status})。新規ジョブを作成します")
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
            f"  [{category}] バッチ{batch_index}/{len(batches)}: "
            f"{', '.join(batch_usernames)}"
        )

        # 2026-07-18: trigger直後にsnapshot_idを即時永続化するコールバック。
        # ポーリング中にプロセスがクラッシュしても snapshot_id を失わない。
        def _on_snapshot_id(sid, _key=batch_key, _accts=batch_usernames):
            updated_pending[_key] = {
                "snapshot_id": sid,
                "accounts": _accts,
                "triggered_at": now.isoformat(),
                "bd_status": "running",
            }
            _save_pending_snapshots(updated_pending)
            print(f"  [{category}] snapshot_id={sid} を即時保存しました(pending_snapshots.json)")

        try:
            ok, raw_items, returned_sid, bd_status = _trigger_and_collect(
                REELS_DATASET_ID, REELS_DISCOVER_QUERY, input_list,
                on_snapshot_id=_on_snapshot_id,
            )
        except Exception as e:
            # _trigger_and_collect内で例外は処理済みのはずだが、念のため
            # ここでも捕まえて、このバッチだけ失敗とし、全体は止めない。
            err = f"予期しないエラー: {e}"
            print(f"  [{category}] バッチ{batch_index}で{err}")
            failed_accounts.extend(batch_usernames)
            snapshot_meta.append({
                "batch_key": batch_key,
                "snapshot_id": None,
                "bd_status": "error",
                "error_msg": err,
                "accounts": batch_usernames,
                "recovered": False,
            })
            continue

        if not ok:
            # bd_statusに応じてエラーメッセージを分ける
            if bd_status == "running":
                error_msg = "Bright Dataジョブはstatus=runningのまま待機時間を超過。結果未回収"
            elif bd_status == "failed":
                error_msg = "Bright Data APIエラー（status=failed）"
            else:
                error_msg = f"Bright Data取得失敗（bd_status={bd_status}）"

            # pending情報はon_snapshot_id経由で既に保存済み。
            # on_snapshot_idが呼ばれなかった場合(trigger_failed)は returned_sid=None。
            if returned_sid:
                # pending に bd_status を更新
                if batch_key in updated_pending:
                    updated_pending[batch_key]["bd_status"] = bd_status
                    updated_pending[batch_key]["error_msg"] = error_msg
                print(
                    f"  [{category}] バッチ{batch_index}: {error_msg}"
                    f"(snapshot_id={returned_sid})"
                )
            else:
                print(
                    f"  [{category}] バッチ{batch_index}は失敗しました(snapshot_id取得不可): "
                    f"{', '.join(batch_usernames)}"
                )
            snapshot_meta.append({
                "batch_key": batch_key,
                "snapshot_id": returned_sid,
                "bd_status": bd_status,
                "error_msg": error_msg,
                "accounts": batch_usernames,
                "recovered": False,
            })
            failed_accounts.extend(batch_usernames)
            continue

        # 成功時: pendingから削除
        if batch_key in updated_pending:
            del updated_pending[batch_key]

        snapshot_meta.append({
            "batch_key": batch_key,
            "snapshot_id": returned_sid,
            "bd_status": "ready",
            "error_msg": "",
            "accounts": batch_usernames,
            "recovered": False,
        })

        if not raw_items:
            print(
                f"  [{category}] バッチ{batch_index}は0件でした"
                f"(対象期間内に取得対象データが無い可能性があります): {', '.join(batch_usernames)}"
            )
            continue

        error_items = [item for item in raw_items if _is_error_item(item)]
        if error_items:
            print(
                f"  [{category}] バッチ{batch_index}: "
                f"{len(error_items)}/{len(raw_items)}件が取得失敗または空データです"
            )
            seen_targets = set()
            for item in error_items:
                desc = _describe_error_item(item)
                target = desc.split(":", 1)[0]
                if target in seen_targets:
                    continue
                seen_targets.add(target)
                print(f"    - {desc}")

        for item in raw_items:
            owner_username = _get_first(item, ["user_posted"], "") or ""
            posts.append(
                _normalize_post(item, source_account=owner_username, category=category)
            )

    if failed_accounts:
        print(
            f"{category}: 取得失敗(ジョブ失敗/タイムアウト)したアカウント"
            f"({len(failed_accounts)}件): {', '.join(failed_accounts)}"
        )

    # 2026-07-18: 未完了ジョブ情報を書き戻す(変更があった場合のみ)
    if updated_pending != pending:
        _save_pending_snapshots(updated_pending)
        if updated_pending:
            print(
                f"未完了ジョブ {len(updated_pending)}件をpending_snapshots.jsonに保存しました。"
                f"次回実行時に自動再確認します"
            )

    return {"posts": posts, "snapshot_meta": snapshot_meta}


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
