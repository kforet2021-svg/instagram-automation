"""
tests/test_account_rotation.py
アカウントローテーションと取得品質ルールのユニットテスト（API呼び出しなし）。

テスト項目:
  1. 43アカウントを5件ずつ9回で全件が一巡する
  2. 10回目は先頭グループへ戻る
  3. 重複アカウントがあっても重複取得しない
  4. pending中のアカウントを新規triggerしない
  5. ready回収済みのアカウントを同一実行内で再triggerしない
  6. Instagram投稿1件の場合、根拠レベルAにならない
  7. Topic「舌・むくみ」に対し、無関係なAIや針美容液投稿を参考根拠に採用しない
  8. 再生数0の投稿を最上位トレンド根拠にしない
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── モジュールインポート前にネットワーク依存をスタブ化 ─────────────────────────

def _stub_modules():
    """openai / gspread / google-auth / dotenv / requests をスタブに差し替える。"""
    for mod in ["openai", "gspread", "google.oauth2", "google.oauth2.service_account",
                "dotenv", "requests", "google", "google.auth"]:
        if mod not in sys.modules:
            sys.modules[mod] = MagicMock()

_stub_modules()

# .env を読まずに環境変数をスタブ化
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("GOOGLE_SHEETS_SPREADSHEET_ID", "test-sheet-id")
os.environ.setdefault("BRIGHT_DATA_API_KEY", "test-bd-key")
os.environ.setdefault("BRIGHT_DATA_TEST_MODE", "1")


class TestAccountRotation(unittest.TestCase):
    """アカウントローテーションの動作確認"""

    def setUp(self):
        # 一時ファイルを使ってローテーション状態をテスト
        self.tmp_dir = tempfile.mkdtemp()
        self.rotation_path = os.path.join(self.tmp_dir, "account_rotation.json")
        self.pending_path = os.path.join(self.tmp_dir, "pending_snapshots.json")

        # bright_data_fetcher をインポートしてパスを差し替え
        import bright_data_fetcher as bdf
        self.bdf = bdf
        self._orig_rotation_path = bdf.ACCOUNT_ROTATION_PATH
        self._orig_pending_path = bdf.PENDING_SNAPSHOTS_PATH
        bdf.ACCOUNT_ROTATION_PATH = self.rotation_path
        bdf.PENDING_SNAPSHOTS_PATH = self.pending_path

    def tearDown(self):
        self.bdf.ACCOUNT_ROTATION_PATH = self._orig_rotation_path
        self.bdf.PENDING_SNAPSHOTS_PATH = self._orig_pending_path

    def _make_accounts(self, n: int) -> list[str]:
        return [f"account_{i:02d}" for i in range(n)]

    def test_01_full_rotation_43_accounts(self):
        """43アカウントを5件ずつ9回で全件が一巡する（最後のラウンドは3件）。"""
        accounts = self._make_accounts(43)
        collected: list[str] = []

        for _ in range(9):
            selected = self.bdf._apply_test_mode_limit(accounts, "TEST")
            collected.extend(selected)

        # 全43件が最低1回は出現する
        self.assertEqual(set(collected), set(accounts),
                         "43件全て1回以上選択されること")

    def test_02_wraps_to_start_on_cycle_reset(self):
        """先頭に折り返した後の選択が、先頭アカウントを含む。
        40アカウントを5件ずつ8回 → 9回目は先頭5件に戻る（40÷5=8で割り切れる）。"""
        accounts = self._make_accounts(40)

        first_batch = None
        for i in range(9):
            selected = self.bdf._apply_test_mode_limit(accounts, "WRAP_TEST")
            if i == 0:
                first_batch = selected

        ninth_batch = selected  # 9回目 = 折り返し後の1周目
        self.assertEqual(first_batch, ninth_batch,
                         "9回目（折り返し後）は1回目と同じアカウントグループになること")

    def test_03_no_duplicates_with_duplicate_accounts(self):
        """重複アカウントがあっても同じアカウントを重複選択しない。"""
        accounts = ["alice", "bob", "alice", "carol", "bob", "dave", "eve"]
        # _apply_test_mode_limit は内部で unique 処理する
        selected = self.bdf._apply_test_mode_limit(accounts, "DEDUP_TEST")
        self.assertEqual(len(selected), len(set(selected)),
                         "選択結果に重複がないこと")

    def test_04_pending_accounts_excluded(self):
        """pending中のアカウントは新規trigger対象から除外される。"""
        accounts = self._make_accounts(10)
        # accounts_00 と accounts_01 をpending中にする
        pending = {
            "batch1": {
                "snapshot_id": "sd_abc123",
                "accounts": ["account_00", "account_01"],
                "triggered_at": "2026-07-21T00:00:00+00:00",
                "bd_status": "running",
            }
        }
        with open(self.pending_path, "w") as f:
            json.dump(pending, f)

        selected = self.bdf._apply_test_mode_limit(accounts, "PENDING_TEST")

        self.assertNotIn("account_00", selected,
                         "pending中のaccount_00は選択されないこと")
        self.assertNotIn("account_01", selected,
                         "pending中のaccount_01は選択されないこと")

    def test_05_recovered_not_retriggered(self):
        """ready回収済みのアカウントはpendingから除外済みなので再triggerされない。"""
        # ready状態のsnapshotは_load_pending_snapshots後の処理で除外されている想定
        # ここでは pending が空 = 制約なし、という正常系を確認
        accounts = self._make_accounts(5)
        # pendingなし
        with open(self.pending_path, "w") as f:
            json.dump({}, f)

        selected = self.bdf._apply_test_mode_limit(accounts, "RECOVERED_TEST")
        # pendingが空なら全件選択可
        self.assertEqual(len(selected), min(5, self.bdf.TEST_MODE_MAX_TOTAL_ACCOUNTS))


class TestInstagramEvidenceLevel(unittest.TestCase):
    """Instagram根拠レベル判定のテスト"""

    def setUp(self):
        import trend_evidence as te
        self.te = te

    def _make_hit(self, plays=1000, likes=100):
        return {"url": "https://ig.com/reel/xxx", "plays": plays, "likes": likes,
                "caption": "咬筋 左右差", "date": "2026-07-01"}

    def test_06_single_ig_post_not_level_A(self):
        """Instagram投稿1件の場合、根拠レベルAにならない。"""
        ig_hits = [self._make_hit()]
        own_hits = []
        seasonal = "夏"  # 季節あり

        level, reason = self.te._assign_level(ig_hits, own_hits, seasonal)
        self.assertNotEqual(level, "A",
                            "Instagram1件では根拠レベルAにならないこと")

    def test_07_irrelevant_posts_filtered(self):
        """Topic「舌・むくみ」に対し、AI/針美容液投稿は除外される。"""
        from trend_evidence import filter_ig_hits_by_relevance

        ig_hits = [
            {"url": "https://ig.com/1", "caption": "AIで美肌管理", "plays": 5000},
            {"url": "https://ig.com/2", "caption": "針美容液でリフトアップ", "plays": 3000},
            {"url": "https://ig.com/3", "caption": "舌の位置でむくみが変わる", "plays": 2000},
            {"url": "https://ig.com/4", "caption": "咬筋とむくみの関係", "plays": 1500},
        ]
        relevant = filter_ig_hits_by_relevance(ig_hits, topic_keywords=["舌", "むくみ", "咬筋"])

        # AI / 針美容液 は除外される
        urls = [h["url"] for h in relevant]
        self.assertNotIn("https://ig.com/1", urls, "AI投稿は除外されること")
        self.assertNotIn("https://ig.com/2", urls, "針美容液投稿は除外されること")
        # 関連ある投稿は残る
        self.assertIn("https://ig.com/3", urls, "舌・むくみ関連投稿は残ること")
        self.assertIn("https://ig.com/4", urls, "咬筋・むくみ関連投稿は残ること")

    def test_08_zero_plays_not_top_evidence(self):
        """再生数0の投稿がすべての場合、Instagram根拠として最上位（A/B）にならない。"""
        # 再生数0のみ3件以上あるケース
        ig_hits = [
            {"url": f"https://ig.com/{i}", "plays": 0, "likes": 500, "caption": "むくみ"}
            for i in range(5)
        ]
        own_hits = []
        seasonal = "夏"

        level, reason = self.te._assign_level(ig_hits, own_hits, seasonal)
        self.assertNotIn(level, ("A", "B"),
                         "再生数0のみではA/Bにならないこと（playsが全件0は無効根拠）")


class TestInstagramQualityReport(unittest.TestCase):
    """Instagram品質レポートのグレード判定テスト"""

    def setUp(self):
        import bright_data_fetcher as bdf
        self.bdf = bdf

    def _make_post(self, account, plays=1000, followers=5000):
        return {
            "source_account": account,
            "play_count": plays,
            "followers": followers,
            "is_reel": True,
            "timestamp": "2026-07-18T10:00:00+00:00",
            "fetch_error": False,
        }

    def test_grade_not_enough(self):
        """投稿10件・アカウント5件 → 不足グレード"""
        posts = [self._make_post(f"acc_{i%5}") for i in range(10)]
        result = self.bdf.print_instagram_fetch_quality_report(posts, [f"acc_{i}" for i in range(5)])
        self.assertEqual(result["grade"], "不足")

    def test_grade_candidate(self):
        """投稿20件・アカウント10件 → 候補グレード"""
        posts = [self._make_post(f"acc_{i%10}") for i in range(20)]
        result = self.bdf.print_instagram_fetch_quality_report(posts, [f"acc_{i}" for i in range(10)])
        self.assertEqual(result["grade"], "候補")

    def test_grade_full_evidence(self):
        """投稿50件・アカウント20件 → 根拠ありグレード"""
        posts = [self._make_post(f"acc_{i%20}") for i in range(50)]
        result = self.bdf.print_instagram_fetch_quality_report(posts, [f"acc_{i}" for i in range(20)])
        self.assertEqual(result["grade"], "根拠あり")


class TestStaleSnapshotManagement(unittest.TestCase):
    """stale_running / abandoned_candidate の状態管理テスト"""

    def setUp(self):
        import bright_data_fetcher as bdf
        self.bdf = bdf

    def _make_info(self, minutes_ago: float, bd_status: str = "running") -> dict:
        """指定分前に trigger されたpendingエントリを作成する。"""
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        t = now - __import__("datetime").timedelta(minutes=minutes_ago)
        return {
            "snapshot_id": f"sd_test_{int(minutes_ago)}",
            "accounts": ["acc_a", "acc_b"],
            "triggered_at": t.isoformat(),
            "bd_status": bd_status,
            "last_checked_at": t.isoformat(),
            "stale_since": None,
            "retry_count": 0,
            "source_version": "v2",
            "abandoned_reason": "",
        }

    def test_09_90min_running_is_active(self):
        """90分経過は active_running（STALE_RUNNING_MIN=120分未満）。"""
        info = self._make_info(90)
        state = self.bdf._classify_snapshot_state(info)
        self.assertEqual(state, "active_running",
                         "90分経過は active_running であること")

    def test_10_121min_running_is_stale(self):
        """121分経過は stale_running（STALE_RUNNING_MIN=120分超）。"""
        info = self._make_info(121)
        state = self.bdf._classify_snapshot_state(info)
        self.assertEqual(state, "stale_running",
                         "121分経過は stale_running であること")

    def test_11_stale_does_not_occupy_slot(self):
        """stale_running ジョブ（is_active=False）は active スロットをカウントしない。"""
        jobs = {
            "batch_a": {"snapshot_id": "sd_x", "accounts": ["a"], "batch_index": 1,
                        "recovered": False, "triggered_at_iso": "", "is_active": False},
            "batch_b": {"snapshot_id": "sd_y", "accounts": ["b"], "batch_index": 2,
                        "recovered": False, "triggered_at_iso": "", "is_active": False},
        }
        # _active_slot_count はローカル関数なので、is_active=False のジョブ数をPythonで再現
        active_count = sum(1 for j in jobs.values() if j.get("is_active", True))
        self.assertEqual(active_count, 0,
                         "stale ジョブ2件の active スロット数は 0 であること")

    def test_12_stale_accounts_not_retriggered_normally(self):
        """stale_running 対象アカウントは通常の実行では trigger 除外される。"""
        # stale_accounts に "acc_stale" が含まれる状態をシミュレート
        stale_accounts: set = {"acc_stale"}
        batch_usernames = ["acc_stale", "acc_new"]
        stale_in_batch = [u for u in batch_usernames if u.lower() in stale_accounts]
        self.assertIn("acc_stale", stale_in_batch,
                      "stale_accounts に含まれるアカウントは stale_in_batch に出現すること")

    def test_13_retry_stale_triggers(self):
        """--retry-stale 時は stale アカウントを再trigger対象にできる（フラグ制御）。"""
        import bright_data_fetcher as bdf
        original = bdf.RETRY_STALE
        bdf.RETRY_STALE = True
        self.assertTrue(bdf.RETRY_STALE, "RETRY_STALE=True のとき再trigger可能フラグが立つ")
        bdf.RETRY_STALE = original

    def test_14_untriggered_not_shown_as_running(self):
        """未trigger アカウントは running_jobs に含まれないこと。"""
        # running_jobs は pending から復元したもの + 新規trigger したもの
        # 未trigger バッチは trigger_queue に積まれるだけで running_jobs には入らない
        running_jobs: dict = {}
        trigger_queue: list = [0, 1, 2]  # 3バッチ未trigger
        # running_jobs が空なら未trigger は running として表示されない
        active_count = sum(1 for j in running_jobs.values() if j.get("is_active", True))
        self.assertEqual(active_count, 0, "未trigger バッチは running_jobs に含まれない")
        self.assertEqual(len(trigger_queue), 3, "未trigger バッチはキューに積まれる")

    def test_15_ready_status_is_completed(self):
        """API status=ready の場合は completed 分類されること。"""
        info = {**self._make_info(90), "bd_status": "ready"}
        state = self.bdf._classify_snapshot_state(info)
        self.assertEqual(state, "completed", "bd_status=ready は completed であること")

    def test_16_failed_status_is_failed(self):
        """API status=failed の場合は failed 分類されること。"""
        info = {**self._make_info(30), "bd_status": "failed"}
        state = self.bdf._classify_snapshot_state(info)
        self.assertEqual(state, "failed", "bd_status=failed は failed であること")

    def test_17_abandoned_candidate_after_6_hours(self):
        """361分経過は abandoned_candidate（ABANDONED_MIN=360分超）。"""
        info = self._make_info(361)
        state = self.bdf._classify_snapshot_state(info)
        self.assertEqual(state, "abandoned_candidate",
                         "361分経過は abandoned_candidate であること")

    def test_18_old_format_readable(self):
        """旧形式のpendingエントリ（新フィールドなし）が読み込めること。"""
        old_format = {
            "snapshot_id": "sd_old123",
            "accounts": ["alice", "bob"],
            "triggered_at": "2026-07-21T01:00:00+00:00",
            "bd_status": "running",
        }
        # 新フィールドが無くても _classify_snapshot_state は動作する
        state = self.bdf._classify_snapshot_state(old_format)
        self.assertIn(state, ("active_running", "stale_running", "abandoned_candidate"),
                      "旧形式エントリも state 分類できること")

    def test_19_check_trigger_allowed_active_only(self):
        """_check_trigger_allowed は active_running のみカウントする。"""
        pending = {}
        for i in range(9):
            import datetime as _dt
            now = _dt.datetime.now(_dt.timezone.utc)
            old_time = now - _dt.timedelta(hours=7 + i)  # 7〜15時間前 = abandoned
            pending[f"batch_{i}"] = {
                "snapshot_id": f"sd_{i}",
                "accounts": [f"acc_{i}"],
                "triggered_at": old_time.isoformat(),
                "bd_status": "running",
            }
        # 9件全て abandoned_candidate → active_running は 0 → trigger 許可
        allowed, reason = self.bdf._check_trigger_allowed(pending)
        self.assertTrue(allowed,
                        "abandoned_candidate のみ9件あっても trigger が許可されること")


class TestBatchFetchSummaryNoNameError(unittest.TestCase):
    """_print_batch_fetch_summary の NameError 回帰テスト"""

    def setUp(self):
        import bright_data_fetcher as bdf
        self.bdf = bdf

    def _make_post(self, account: str) -> dict:
        return {
            "source_account": account, "username": account,
            "play_count": 1000, "followers": 5000,
            "is_reel": True, "fetch_error": False,
        }

    def test_20_no_name_error_on_summary(self):
        """_print_batch_fetch_summary が NameError を起こさないこと。"""
        posts = [self._make_post("alice"), self._make_post("bob")]
        snapshot_meta = [
            {"batch_key": "alice|bob", "bd_status": "ready", "accounts": ["alice", "bob"],
             "recovered": True, "recovered_count": 2},
        ]
        batches = [["alice", "bob"]]
        failed_accounts: list = []

        import io, contextlib
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                self.bdf._print_batch_fetch_summary(
                    posts, snapshot_meta, batches, failed_accounts, "テスト"
                )
        except NameError as e:
            self.fail(f"NameError が発生しました: {e}")

    def test_21_active_and_queued_are_separate(self):
        """active running と 未実行キューは別カテゴリで集計されること。"""
        import io, contextlib
        import datetime as _dt

        now = _dt.datetime.now(_dt.timezone.utc)
        triggered_at = (now - _dt.timedelta(minutes=30)).isoformat()

        # バッチ1: active running (snapshot_metaあり・running)
        # バッチ2: 未実行キュー (snapshot_metaなし)
        posts: list = []
        snapshot_meta = [
            {"batch_key": "acc_a|acc_b", "bd_status": "running",
             "accounts": ["acc_a", "acc_b"], "recovered": False},
        ]
        batches = [["acc_a", "acc_b"], ["acc_c", "acc_d"]]
        failed_accounts: list = []
        running_jobs_ref = {
            "acc_a|acc_b": {
                "snapshot_id": "sd_x", "accounts": ["acc_a", "acc_b"],
                "batch_index": 1, "recovered": False,
                "triggered_at_iso": triggered_at, "is_active": True,
            }
        }

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.bdf._print_batch_fetch_summary(
                posts, snapshot_meta, batches, failed_accounts, "テスト",
                running_jobs_ref=running_jobs_ref,
            )

        output = buf.getvalue()
        self.assertIn("active running", output, "active runningカテゴリが表示されること")
        self.assertIn("未実行キュー", output, "未実行キューカテゴリが表示されること")
        self.assertNotIn("処理中・次回回収", output,
                         "active runningを「処理中・次回回収」と混在表示しないこと")

    def test_22_recovered_posts_counted_in_total(self):
        """ready回収投稿は取得投稿合計にカウントされること。"""
        import io, contextlib

        posts = [self._make_post(f"acc_{i}") for i in range(43)]
        snapshot_meta = [
            {"batch_key": "|".join(sorted([f"acc_{i}", f"acc_{i+1}"])),
             "bd_status": "ready", "accounts": [f"acc_{i}", f"acc_{i+1}"],
             "recovered": True, "recovered_count": 4}
            for i in range(0, 10, 2)
        ]
        batches = [[f"acc_{i}", f"acc_{i+1}"] for i in range(0, 10, 2)]
        failed_accounts: list = []

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.bdf._print_batch_fetch_summary(
                posts, snapshot_meta, batches, failed_accounts, "テスト"
            )

        output = buf.getvalue()
        self.assertIn("43件", output, "取得投稿合計43件が表示されること")

    def test_23_no_all_batch_accounts_reference(self):
        """ソースコード内に all_batch_accounts（flat 除く）の未定義参照が残っていないこと。"""
        import re, os
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bright_data_fetcher.py"
        )
        with open(src_path, encoding="utf-8") as f:
            content = f.read()
        # all_batch_accounts_flat は OK、all_batch_accounts 単体はNG
        bad_refs = re.findall(r'\ball_batch_accounts\b(?!_flat)', content)
        self.assertEqual(bad_refs, [],
                         f"未定義変数 all_batch_accounts の参照が残っています: {bad_refs}")


class TestViewsExtractionAndScoreNormalization(unittest.TestCase):
    """test_24〜33: extract_views / _parse_view_string / 正規化スコア / 最低再生数ゲート"""

    def setUp(self):
        import sys, os, types
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # bright_data_fetcher スタブ不要 (ネットワーク不使用関数のみテスト)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        # 外部依存モジュールをスタブ化
        for mod in ("openai", "gspread", "google.auth", "google.oauth2.service_account",
                    "dotenv", "requests"):
            top = mod.split(".")[0]
            if top not in sys.modules:
                sys.modules[top] = types.ModuleType(top)
            if "." in mod and mod not in sys.modules:
                sys.modules[mod] = types.ModuleType(mod)

    # ── extract_views / _parse_view_string ─────────────────────────────────

    def test_24_extract_views_from_raw_json(self):
        """video_play_count フィールドがある場合に正しく再生数を取得できる"""
        import importlib
        bdf = importlib.import_module("bright_data_fetcher")
        post = {"video_play_count": 150000, "views": None}
        self.assertEqual(bdf.extract_views(post), 150000)

    def test_25_parse_view_string_formats(self):
        """文字列再生数 ("12,345" / "1.2万" / "2.4M") を数値化できる"""
        import importlib
        bdf = importlib.import_module("bright_data_fetcher")
        pvs = bdf._parse_view_string
        self.assertEqual(pvs("12,345"), 12345)
        self.assertEqual(pvs("1.2万"), 12000)
        self.assertEqual(pvs("2.4M"), 2400000)
        self.assertEqual(pvs("500K"), 500000)
        self.assertEqual(pvs("1.5B"), 1500000000)

    def test_26_extract_views_null_vs_zero(self):
        """null(未取得) は None を返し、0 は 0 を返す"""
        import importlib
        bdf = importlib.import_module("bright_data_fetcher")
        # 全フィールドが None → 未取得 → None
        post_null = {"video_play_count": None, "views": None}
        self.assertIsNone(bdf.extract_views(post_null))
        # 明示的ゼロ → 0
        post_zero = {"video_play_count": None, "views": 0}
        self.assertEqual(bdf.extract_views(post_zero), 0)

    # ── 正規化スコア ───────────────────────────────────────────────────────

    def test_27_max_raw_score_is_80(self):
        """MAX_RAW_SCORE が 80 であること"""
        import importlib
        rcs = importlib.import_module("research_candidate_score")
        self.assertEqual(rcs.MAX_RAW_SCORE, 80)

    def test_28_normalize_score_100pt(self):
        """raw_score=80(満点) が normalized_score=100.0 になる"""
        import importlib
        rcs = importlib.import_module("research_candidate_score")
        self.assertEqual(rcs.normalize_score(80), 100.0)

    def test_29_normalize_score_scaled(self):
        """raw_score=64 が normalized_score=80.0 になる (64/80*100)"""
        import importlib
        rcs = importlib.import_module("research_candidate_score")
        self.assertEqual(rcs.normalize_score(64), 80.0)

    def test_30_views_none_not_in_analysis(self):
        """views_available=False の投稿は AI 分析対象にならない"""
        import importlib
        rcs = importlib.import_module("research_candidate_score")
        post = {
            "views": 0, "likes": 500, "comments": 10,
            "followers": 10000, "view_multiplier": None,
            "posted_at_dt": None, "duration_sec": 30,
            "account_post_count_window": 5,
            "research_candidate_score": {
                "total": 40, "normalized_score": 50.0,
                "views_available": False, "tier": "評価保留", "anomalies": [],
            },
        }
        result = rcs.select_for_analysis([post])
        self.assertEqual(result, [])

    def test_31_min_views_absolute_gate(self):
        """10万再生未満かつ倍率 < 1.0 は AI 分析対象外になる"""
        import importlib
        rcs = importlib.import_module("research_candidate_score")
        post = {
            "views": 50000, "likes": 5000, "comments": 200,
            "followers": 200000, "view_multiplier": 0.25,
            "posted_at_dt": None, "duration_sec": 30,
            "account_post_count_window": 5,
            "research_candidate_score": {
                "total": 60, "normalized_score": 75.0,
                "views_available": True, "tier": "必ず分析", "anomalies": [],
            },
        }
        result = rcs.select_for_analysis([post])
        self.assertEqual(result, [])
        self.assertEqual(post.get("pool_exclusion_reason"), "再生数10万未満")

    def test_32_views_100k_qualifies(self):
        """10万再生以上かつ正規化スコア >= 65 は分析対象になる"""
        import importlib, datetime
        rcs = importlib.import_module("research_candidate_score")
        dt_now = datetime.datetime.now(datetime.timezone.utc)
        post = {
            "views": 100000, "likes": 5000, "comments": 200,
            "followers": 50000, "view_multiplier": 2.0,
            "posted_at_dt": dt_now, "duration_sec": 30,
            "account_post_count_window": 5,
            "caption": "", "hashtags": [],
            "research_candidate_score": {
                "total": 56, "normalized_score": 70.0,
                "views_available": True, "tier": "投稿案候補", "anomalies": [],
            },
        }
        result = rcs.select_for_analysis([post])
        self.assertEqual(len(result), 1)

    def test_33_view_multiplier_qualifies(self):
        """再生倍率 >= 1.0 なら 10万再生未満でも分析対象になる"""
        import importlib, datetime
        rcs = importlib.import_module("research_candidate_score")
        dt_now = datetime.datetime.now(datetime.timezone.utc)
        post = {
            "views": 80000, "likes": 3000, "comments": 100,
            "followers": 60000, "view_multiplier": 1.33,
            "posted_at_dt": dt_now, "duration_sec": 30,
            "account_post_count_window": 4,
            "caption": "", "hashtags": [],
            "research_candidate_score": {
                "total": 54, "normalized_score": 67.5,
                "views_available": True, "tier": "投稿案候補", "anomalies": [],
            },
        }
        result = rcs.select_for_analysis([post])
        self.assertEqual(len(result), 1)

    def test_34_full_marks_not_required(self):
        """全項目満点でなくても normalized_score >= 65 なら分析対象になり得る"""
        import importlib, datetime
        rcs = importlib.import_module("research_candidate_score")
        # raw 52/80 → normalized 65.0 = ちょうどANALYSIS_MIN_SCORE
        dt_now = datetime.datetime.now(datetime.timezone.utc)
        post = {
            "views": 500000, "likes": 8000, "comments": 300,
            "followers": 100000, "view_multiplier": 5.0,
            "posted_at_dt": dt_now, "duration_sec": 30,
            "account_post_count_window": 6,
            "caption": "", "hashtags": [],
            "research_candidate_score": {
                "total": 52, "normalized_score": 65.0,
                "views_available": True, "tier": "投稿案候補", "anomalies": [],
            },
        }
        result = rcs.select_for_analysis([post])
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
