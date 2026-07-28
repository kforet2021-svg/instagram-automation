"""
instagram_fetcher.py

【2026-07-24: 新規作成】
INSTAGRAM_FETCH_PROVIDER 環境変数で Instagram 取得プロバイダを切り替える。

  brightdata (デフォルト):
      bright_data_fetcher.fetch_trend_posts() にそのまま委譲する。
      BRIGHT_DATA_API_KEY が必要。

  apify:
      Apify の instagram-reel-scraper Actor を使って取得する。
      APIFY_API_TOKEN が必要。
      最大 APIFY_MAX_CONCURRENT=3 並列 Actor run、
      pending_actor_runs.json に未完了 run を保存して次回実行時に回収、
      失敗時は APIFY_MAX_RETRIES=2 回まで自動リトライ。

戻り値は両プロバイダとも {"posts": list[dict], "snapshot_meta": list[dict]}。
posts の各 dict は bright_data_fetcher._normalize_post() と同一スキーマ。
"""

import datetime as dt
import json
import os
import re
import time

from dotenv import load_dotenv

load_dotenv()

# ── プロバイダ設定 ─────────────────────────────────────────────────────────────
INSTAGRAM_FETCH_PROVIDER: str = os.getenv("INSTAGRAM_FETCH_PROVIDER", "brightdata")

# ── Apify 定数 ────────────────────────────────────────────────────────────────
APIFY_ACTOR_ID = "apify/instagram-reel-scraper"
APIFY_PROFILE_ACTOR_ID = "apify/instagram-profile-scraper"
APIFY_ACCOUNTS_PER_BATCH: int = int(os.getenv("APIFY_ACCOUNTS_PER_BATCH", "15"))
APIFY_MAX_CONCURRENT = 3
APIFY_WAIT_SECS: int = int(os.getenv("APIFY_WAIT_SECS", "1800"))  # 30分
APIFY_POLL_INTERVAL = 30  # seconds
APIFY_MAX_RETRIES = 2
APIFY_RECENT_DAYS = 20  # bright_data_fetcher.RECENT_DAYS と同じ値

# bright_data_fetcher.CATEGORY_ALL と同じ値
_CATEGORY_ALL = "Instagram全体トレンド"

PENDING_RUNS_FILE: str = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "pending_actor_runs.json"
)
DEFAULT_RESULTS_PER_ACCOUNT = 8  # bright_data_fetcher と同じデフォルト値


# ─────────────────────────────────────────────────────────────────────────────
# 公開 API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_trend_posts(
    accounts: list, results_limit: int = DEFAULT_RESULTS_PER_ACCOUNT
) -> dict:
    """
    INSTAGRAM_FETCH_PROVIDER に応じて BrightData または Apify で取得する。
    戻り値: {"posts": list[dict], "snapshot_meta": list[dict]}
    """
    if INSTAGRAM_FETCH_PROVIDER == "apify":
        return _apify_fetch_trend_posts(accounts, results_limit)
    from bright_data_fetcher import fetch_trend_posts as _bd
    return _bd(accounts, results_limit)


# ─────────────────────────────────────────────────────────────────────────────
# pending_actor_runs.json 管理
# ─────────────────────────────────────────────────────────────────────────────

def _load_pending_runs() -> list:
    try:
        with open(PENDING_RUNS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_pending_runs(runs: list) -> None:
    with open(PENDING_RUNS_FILE, "w", encoding="utf-8") as f:
        json.dump(runs, f, ensure_ascii=False, indent=2, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# 数値ユーティリティ
# ─────────────────────────────────────────────────────────────────────────────

def _parse_numeric(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("_", "")
    if not text:
        return None
    upper = text.upper()
    for suf, mul in (("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
        if upper.endswith(suf) and len(text) > 1:
            try:
                return float(text[:-1]) * mul
            except ValueError:
                return None
    if text.endswith("万") and len(text) > 1:
        try:
            return float(text[:-1]) * 10_000
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value, default: int = 0) -> int:
    parsed = _parse_numeric(value)
    try:
        return int(parsed) if parsed is not None else default
    except (ValueError, TypeError, OverflowError):
        return default


def _to_int_or_none(value):
    parsed = _parse_numeric(value)
    try:
        return int(parsed) if parsed is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def _get_value(obj, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default) if obj is not None else default


def _get_first(item, keys: list, default=None):
    for key in keys:
        val = _get_value(item, key)
        if val not in (None, ""):
            return val
    return default


# ─────────────────────────────────────────────────────────────────────────────
# Apify レスポンス正規化ヘルパー
# ─────────────────────────────────────────────────────────────────────────────

_VIEW_KEYS = [
    "videoPlayCount", "videoViewCount", "videoViews", "videoPlays",
    "playCount", "plays", "viewCount", "viewsCount", "views",
]


def _extract_views(item: dict):
    """None=未取得, int=取得済み(0含む)"""
    for key in _VIEW_KEYS:
        raw = item.get(key)
        if raw is None:
            continue
        parsed = _to_int_or_none(raw)
        if parsed is not None:
            return parsed
    return None


def _extract_followers(item: dict):
    direct = _get_first(
        item,
        ["followersCount", "ownerFollowersCount", "followerCount", "ownerFollowerCount"],
        None,
    )
    if direct is not None:
        return _to_int_or_none(direct)
    owner = _get_value(item, "owner")
    if owner:
        nested = _get_first(owner, ["followersCount", "followerCount"], None)
        if nested is not None:
            return _to_int_or_none(nested)
    return None


def _parse_posted_at(raw):
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
    if text.isdigit():
        try:
            return dt.datetime.fromtimestamp(int(text), tz=dt.timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _compute_growth_metrics(views: int, followers, posted_at_dt):
    if posted_at_dt is None or not followers:
        return None, None
    now = dt.datetime.now(dt.timezone.utc)
    days_elapsed = max((now - posted_at_dt).total_seconds() / 86400, 1.0)
    gv = round(views / days_elapsed, 1)
    return gv, round(gv / followers, 4)


def _is_reel(item: dict) -> bool:
    product_type = str(_get_value(item, "productType") or "").lower()
    if product_type in ("clips", "reel", "reels"):
        return True
    url = str(_get_value(item, "url") or "")
    if "/reel/" in url:
        return True
    item_type = str(_get_value(item, "type") or "").lower()
    if item_type in ("video", "reel", "clip", "graphvideo") or "video" in item_type:
        return True
    if _get_value(item, "isVideo") is True or _get_value(item, "isReel") is True:
        return True
    if _get_first(item, ["videoUrl", "videoPlayUrl", "videoPlayCount", "videoViewCount"]):
        return True
    return False


def _get_post_type(item: dict) -> str:
    url = str(_get_first(item, ["url"], "") or "")
    product_type = str(_get_value(item, "productType") or "").lower()
    if "/reel/" in url or product_type in ("clips", "reel", "reels"):
        return "Reel"
    if _get_value(item, "isVideo") is True or _get_value(item, "isReel") is True:
        return "Reel"
    if _get_first(item, ["videoUrl", "videoPlayUrl", "videoPlayCount", "videoViewCount"]):
        return "Reel"
    if product_type == "carousel_container":
        return "Carousel"
    return "Feed"


def _extract_hashtags(item: dict, caption: str) -> list:
    hashtags = _get_value(item, "hashtags")
    if isinstance(hashtags, list) and hashtags:
        return [str(h).lstrip("#") for h in hashtags]
    if caption:
        return re.findall(r"#(\w+)", caption)
    return []


def _is_error_item(item: dict) -> bool:
    return bool(_get_value(item, "error")) or bool(_get_value(item, "errorDescription"))


def _to_username(account: str) -> str:
    return str(account or "").strip().lstrip("@").strip()


def _normalize_apify_post(item: dict, source_account: str, category: str) -> dict:
    """
    Apify instagram-reel-scraper の出力アイテムを
    bright_data_fetcher._normalize_post() と同一スキーマに変換する。
    """
    username = _get_first(
        item,
        ["ownerUsername", "username", "userName", "ownerFullName", "ownerId"],
        "",
    ) or ""

    caption = _get_first(item, ["caption", "text", "description"], "") or ""

    views_fetched = _extract_views(item)
    views = views_fetched if views_fetched is not None else 0

    likes_raw = _get_first(item, ["likesCount", "likes", "like_count"], 0)
    comments_raw = _get_first(item, ["commentsCount", "comments", "comment_count"], 0)
    saves_raw = _get_first(item, ["saveCount", "savesCount", "saves"], None)
    shares_raw = _get_first(item, ["shareCount", "sharesCount", "shares"], None)
    duration_raw = _get_first(item, ["videoDuration", "duration"], None)

    url = _get_first(item, ["url", "postUrl", "shortCode"], "") or ""
    if url and not str(url).startswith("http"):
        url = f"https://www.instagram.com/p/{url}/"

    media_url = _get_first(
        item,
        ["videoUrl", "displayUrl", "thumbnailUrl", "imageUrl", "videoPlayUrl"],
        "",
    ) or ""

    posted_at_raw = _get_first(item, ["timestamp", "takenAt", "taken_at_timestamp"], "") or ""
    posted_at_dt = _parse_posted_at(posted_at_raw)

    followers = _extract_followers(item)
    view_multiplier = round(views / followers, 2) if followers and views else None
    growth_velocity, growth_rate = _compute_growth_metrics(views, followers, posted_at_dt)

    saves = _to_int_or_none(saves_raw)
    save_rate = round(saves / views, 4) if (saves is not None and views > 0) else None

    return {
        "username": username,
        "caption": caption,
        "likes": _to_int(likes_raw),
        "comments": _to_int(comments_raw),
        "views": views,
        "saves": saves,
        "shares": _to_int_or_none(shares_raw),
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
        "hashtags": _extract_hashtags(item, caption),
        "is_reel": _is_reel(item),
        "post_type": _get_post_type(item),
        "fetch_error": _is_error_item(item),
        "source_account": source_account,
        "category": category,
        "raw_data": item,
        "platform": "instagram",
    }


def _attach_account_post_counts(posts: list) -> None:
    """account_post_count_window を全投稿に付与 (in-place)。"""
    counts: dict = {}
    for post in posts:
        if post.get("fetch_error"):
            continue
        key = post.get("source_account") or post.get("username") or ""
        if key:
            counts[key] = counts.get(key, 0) + 1
    for post in posts:
        key = post.get("source_account") or post.get("username") or ""
        post["account_post_count_window"] = counts.get(key, 0)


# ─────────────────────────────────────────────────────────────────────────────
# Apify 取得コア
# ─────────────────────────────────────────────────────────────────────────────

def _run_attr(run_obj, attr: str, default=""):
    """apify_client v3 の Run オブジェクト (Pydantic モデル) から属性を安全に取得する。"""
    if run_obj is None:
        return default
    return getattr(run_obj, attr, default) or default


def _collect_dataset_items(client, dataset_id: str) -> list:
    try:
        return list(client.dataset(dataset_id).iterate_items())
    except Exception as e:
        print(f"[Apify] Dataset取得エラー (dataset_id={dataset_id}): {e}")
        return []


def _normalize_items(items: list, category: str) -> list:
    posts = []
    for item in items:
        source = _get_first(item, ["ownerUsername", "username", "userName"], "") or ""
        posts.append(_normalize_apify_post(item, source_account=source, category=category))
    return posts


def _fetch_follower_counts(client, usernames: list) -> dict:
    """
    apify/instagram-profile-scraper を使いフォロワー数を一括取得する (2nd pass)。
    戻り値: {username_lower: followers_int}
    失敗時は空 dict を返し、呼び出し元は followers=None のままパイプラインを継続する。
    """
    if not usernames:
        return {}
    print(f"[Apify] プロフィール 2nd pass: {len(usernames)}アカウント")
    try:
        run_info = client.actor(APIFY_PROFILE_ACTOR_ID).call(
            run_input={"usernames": usernames}
        )
        dataset_id = _run_attr(run_info, "default_dataset_id")
        items = _collect_dataset_items(client, dataset_id) if dataset_id else []
        print(f"[Apify] プロフィール取得完了: {len(items)} 件")
    except Exception as e:
        print(f"[Apify] プロフィール取得失敗 (followers=None で継続): {e}")
        return {}

    result = {}
    for item in items:
        uname = str(
            _get_first(item, ["username", "ownerUsername", "userName"], "") or ""
        ).lower().lstrip("@").strip()
        followers = _to_int_or_none(
            _get_first(item, ["followersCount", "followerCount", "followers"], None)
        )
        if uname and followers is not None:
            result[uname] = followers
    return result


def _merge_followers(posts: list, follower_map: dict) -> None:
    """
    follower_map ({username_lower: count}) から各投稿の followers を補完する (in-place)。
    補完した投稿は view_multiplier / growth_velocity / growth_rate も再計算する。
    """
    for post in posts:
        if post.get("followers") is not None:
            continue
        uname = (post.get("username") or "").lower().lstrip("@").strip()
        followers = follower_map.get(uname)
        if followers is None:
            continue
        post["followers"] = followers
        views = post.get("views") or 0
        post["view_multiplier"] = round(views / followers, 2) if followers else None
        gv, gr = _compute_growth_metrics(views, followers, post.get("posted_at_dt"))
        post["growth_velocity"] = gv
        post["growth_rate"] = gr


def _apify_fetch_trend_posts(accounts: list, results_limit: int) -> dict:
    """
    Apify instagram-reel-scraper Actor を使って投稿を取得する。
    最大 APIFY_MAX_CONCURRENT 並列 run、pending_actor_runs.json に状態保存、
    失敗時は APIFY_MAX_RETRIES 回まで自動リトライ。
    """
    from apify_client import ApifyClient

    token = os.getenv("APIFY_API_TOKEN", "")
    if not token:
        raise EnvironmentError("APIFY_API_TOKEN が設定されていません")

    client = ApifyClient(token)

    usernames = [_to_username(a) for a in accounts if a and a.strip()]
    if not usernames:
        return {"posts": [], "snapshot_meta": []}

    now = dt.datetime.now(dt.timezone.utc)
    cutoff_date = (now - dt.timedelta(days=APIFY_RECENT_DAYS)).strftime("%Y-%m-%d")

    batches = [
        usernames[i:i + APIFY_ACCOUNTS_PER_BATCH]
        for i in range(0, len(usernames), APIFY_ACCOUNTS_PER_BATCH)
    ]
    batch_keys = [f"batch_{i}" for i in range(len(batches))]

    print(
        f"[Apify] {len(usernames)}アカウント / {len(batches)}バッチ"
        f" / actor={APIFY_ACTOR_ID}"
        f" / cutoff={cutoff_date}"
    )

    # ── 1. pending runs の回収・リトライ判定 ──────────────────────────────────
    pending = _load_pending_runs()
    still_pending_runs: list = []   # まだ実行中 → pending file に戻す
    retry_queue: dict = {}          # batch_key → retry_count
    recovered_posts: list = []
    snapshot_meta: list = []

    for run in pending:
        bk = run["batch_key"]
        run_id = run["run_id"]
        retry_count = run.get("retry_count", 0)
        accounts_in_run = run.get("accounts", [])

        try:
            run_info = client.run(run_id).get()
            status = str(_run_attr(run_info, "status", "UNKNOWN"))
        except Exception as e:
            print(f"[Apify] {bk}: pending run確認エラー (run_id={run_id}): {e}")
            still_pending_runs.append(run)
            continue

        if status == "SUCCEEDED":
            dataset_id = _run_attr(run_info, "default_dataset_id") or run.get("dataset_id", "")
            items = _collect_dataset_items(client, dataset_id) if dataset_id else []
            recovered_posts.extend(_normalize_items(items, _CATEGORY_ALL))
            snapshot_meta.append({
                "batch_key": bk,
                "snapshot_id": run_id,
                "bd_status": "ready",
                "error_msg": "",
                "accounts": accounts_in_run,
                "recovered": True,
            })
            print(f"[Apify] {bk}: 前回 pending → 回収完了 ({len(items)}件)")
        elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
            print(
                f"[Apify] {bk}: 失敗"
                f" (status={status}, retry={retry_count}/{APIFY_MAX_RETRIES})"
            )
            if retry_count < APIFY_MAX_RETRIES:
                retry_queue[bk] = retry_count + 1
        else:
            # RUNNING / READY など → 保持
            still_pending_runs.append(run)
            print(f"[Apify] {bk}: まだ実行中 (status={status})")

    # ── 2. 新規 / リトライ対象バッチを特定して起動 ───────────────────────────
    covered_keys = (
        {m["batch_key"] for m in snapshot_meta if m.get("recovered")}
        | {r["batch_key"] for r in still_pending_runs}
    )
    available_slots = max(0, APIFY_MAX_CONCURRENT - len(still_pending_runs))
    active_runs: list = []  # 今回新たに開始した runs

    for bk, batch in zip(batch_keys, batches):
        if bk in covered_keys and bk not in retry_queue:
            continue

        if len(active_runs) >= available_slots:
            # 並列上限 → 次回実行へ延期
            print(f"[Apify] {bk}: 並列上限 ({APIFY_MAX_CONCURRENT}) のため次回実行へ延期")
            snapshot_meta.append({
                "batch_key": bk,
                "snapshot_id": "",
                "bd_status": "queued",
                "error_msg": "並列上限のため延期",
                "accounts": batch,
                "recovered": False,
            })
            continue

        retry_count = retry_queue.get(bk, 0)
        run_input = {
            "username": batch,
            "resultsLimit": results_limit,
            "onlyPostsNewerThan": cutoff_date,
        }
        print(f"[Apify] {bk}: Actor開始 ({len(batch)}アカウント, retry={retry_count})")
        try:
            run_info = client.actor(APIFY_ACTOR_ID).start(run_input=run_input)
            run_id = _run_attr(run_info, "id")
            dataset_id = _run_attr(run_info, "default_dataset_id")
            active_runs.append({
                "batch_key": bk,
                "run_id": run_id,
                "dataset_id": dataset_id,
                "accounts": batch,
                "started_at": now.isoformat(),
                "status": "RUNNING",
                "retry_count": retry_count,
            })
        except Exception as e:
            print(f"[Apify] {bk}: Actor開始失敗: {e}")
            snapshot_meta.append({
                "batch_key": bk,
                "snapshot_id": "",
                "bd_status": "trigger_failed",
                "error_msg": str(e),
                "accounts": batch,
                "recovered": False,
            })

    # ── 3. active runs をポーリング (タイムアウト付き) ───────────────────────
    new_posts: list = []
    deadline = time.monotonic() + APIFY_WAIT_SECS
    waiting = list(active_runs)

    while waiting and time.monotonic() < deadline:
        time.sleep(APIFY_POLL_INTERVAL)
        next_waiting = []
        for run in waiting:
            run_id = run["run_id"]
            bk = run["batch_key"]
            try:
                run_info = client.run(run_id).get()
                status = str(_run_attr(run_info, "status", "UNKNOWN"))
            except Exception as e:
                print(f"[Apify] {bk}: ポーリングエラー: {e}")
                next_waiting.append(run)
                continue

            if status == "SUCCEEDED":
                dataset_id = (
                    _run_attr(run_info, "default_dataset_id") or run.get("dataset_id", "")
                )
                items = _collect_dataset_items(client, dataset_id) if dataset_id else []
                new_posts.extend(_normalize_items(items, _CATEGORY_ALL))
                snapshot_meta.append({
                    "batch_key": bk,
                    "snapshot_id": run_id,
                    "bd_status": "ready",
                    "error_msg": "",
                    "accounts": run["accounts"],
                    "recovered": False,
                })
                print(f"[Apify] {bk}: 完了 ({len(items)}件)")
            elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                snapshot_meta.append({
                    "batch_key": bk,
                    "snapshot_id": run_id,
                    "bd_status": "failed",
                    "error_msg": f"status={status}",
                    "accounts": run["accounts"],
                    "recovered": False,
                })
                print(f"[Apify] {bk}: 失敗 (status={status})")
            else:
                next_waiting.append(run)

        waiting = next_waiting

    # タイムアウトした run を pending file に保存
    for run in waiting:
        bk = run["batch_key"]
        still_pending_runs.append(run)
        snapshot_meta.append({
            "batch_key": bk,
            "snapshot_id": run["run_id"],
            "bd_status": "running",
            "error_msg": f"タイムアウト ({APIFY_WAIT_SECS}秒): 次回実行時に回収",
            "accounts": run["accounts"],
            "recovered": False,
        })
        print(f"[Apify] {bk}: タイムアウト → pending に保存 (run_id={run['run_id']})")

    # ── 4. pending file 更新 ────────────────────────────────────────────────
    _save_pending_runs(still_pending_runs)

    # ── 5. 全投稿を統合 ──────────────────────────────────────────────────────
    all_posts = recovered_posts + new_posts

    # ── 5b. フォロワー数 2nd pass (apify/instagram-profile-scraper) ──────────
    # instagram-reel-scraper はフォロワー数を返さないため、
    # 取得できた投稿のユニークアカウント名でプロフィール取得を追加実行する。
    usernames_need_followers = list({
        p["username"].lower().lstrip("@").strip()
        for p in all_posts
        if p.get("username") and not p.get("fetch_error") and p.get("followers") is None
    })
    if usernames_need_followers:
        follower_map = _fetch_follower_counts(client, usernames_need_followers)
        if follower_map:
            _merge_followers(all_posts, follower_map)
            merged = sum(1 for p in all_posts if p.get("followers") is not None)
            print(f"[Apify] followers補完: {merged}/{len(all_posts)} 件")

    _attach_account_post_counts(all_posts)

    print(f"[Apify] 合計 {len(all_posts)} 件取得")
    return {"posts": all_posts, "snapshot_meta": snapshot_meta}
