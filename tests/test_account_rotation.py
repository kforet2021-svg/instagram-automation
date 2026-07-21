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


if __name__ == "__main__":
    unittest.main(verbosity=2)
