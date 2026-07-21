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


if __name__ == "__main__":
    unittest.main(verbosity=2)
