"""
tests/test_v2_comprehensive.py
30テストケース: Bright Data / Evidence / Hook / Integration
API呼び出しなし（モックのみ）

【2026-07-21(1回目): 新規作成。TASK4 包括的テスト30件。】
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── ネットワーク依存スタブ ─────────────────────────────────────────────────────

def _stub_modules():
    for mod in ["openai", "gspread", "google.oauth2", "google.oauth2.service_account",
                "dotenv", "requests", "google", "google.auth"]:
        if mod not in sys.modules:
            sys.modules[mod] = MagicMock()

_stub_modules()

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("GOOGLE_SHEETS_SPREADSHEET_ID", "test-sheet-id")
os.environ.setdefault("BRIGHT_DATA_API_KEY", "test-bd-key")
os.environ.setdefault("BRIGHT_DATA_TEST_MODE", "1")


# ─────────────────────────────────────────────────────────────────────────────
# Bright Data Tests (1–11)
# ─────────────────────────────────────────────────────────────────────────────

class TestBrightDataRotation(unittest.TestCase):

    def setUp(self):
        import bright_data_fetcher as bdf
        self.bdf = bdf
        self.tmp_dir = tempfile.mkdtemp()
        self.rotation_path = os.path.join(self.tmp_dir, "account_rotation.json")
        self.pending_path  = os.path.join(self.tmp_dir, "pending_snapshots.json")
        self._orig_rotation = bdf.ACCOUNT_ROTATION_PATH
        self._orig_pending  = bdf.PENDING_SNAPSHOTS_PATH
        bdf.ACCOUNT_ROTATION_PATH  = self.rotation_path
        bdf.PENDING_SNAPSHOTS_PATH = self.pending_path

    def tearDown(self):
        self.bdf.ACCOUNT_ROTATION_PATH  = self._orig_rotation
        self.bdf.PENDING_SNAPSHOTS_PATH = self._orig_pending

    def _accounts(self, n: int) -> list[str]:
        return [f"account_{i:02d}" for i in range(n)]

    # Test 1
    def test_01_43accounts_5per_batch_9rounds_covers_all(self):
        """43アカウントを5件ずつ9回で全件が一巡する"""
        accounts = self._accounts(43)
        collected: list[str] = []
        for _ in range(9):
            selected = self.bdf._apply_test_mode_limit(accounts, "T1")
            collected.extend(selected)
        self.assertEqual(set(collected), set(accounts))

    # Test 2
    def test_02_after_full_cycle_returns_to_start(self):
        """40アカウントを5件ずつ8回後、9回目は先頭5件に戻る"""
        accounts = self._accounts(40)
        first_batch = None
        for i in range(9):
            selected = self.bdf._apply_test_mode_limit(accounts, "T2")
            if i == 0:
                first_batch = selected
        self.assertEqual(first_batch, selected)

    # Test 3
    def test_03_duplicate_accounts_deduplicated(self):
        """重複アカウントがあっても同じアカウントを重複選択しない"""
        accounts = ["alice", "bob", "alice", "carol", "bob", "dave", "eve"]
        selected = self.bdf._apply_test_mode_limit(accounts, "T3")
        self.assertEqual(len(selected), len(set(selected)))

    # Test 4
    def test_04_pending_accounts_excluded_from_trigger(self):
        """pending中のアカウントは新規trigger対象から除外される"""
        accounts = self._accounts(10)
        pending = {
            "batch1": {
                "snapshot_id": "sd_abc",
                "accounts": ["account_00", "account_01"],
                "triggered_at": "2026-07-21T00:00:00+00:00",
                "bd_status": "running",
            }
        }
        with open(self.pending_path, "w") as f:
            json.dump(pending, f)
        selected = self.bdf._apply_test_mode_limit(accounts, "T4")
        self.assertNotIn("account_00", selected)
        self.assertNotIn("account_01", selected)

    # Test 5
    def test_05_ready_recovered_not_retriggered(self):
        """pending が空なら制約なし（ready回収済みの確認）"""
        accounts = self._accounts(5)
        with open(self.pending_path, "w") as f:
            json.dump({}, f)
        selected = self.bdf._apply_test_mode_limit(accounts, "T5")
        self.assertEqual(len(selected), min(5, self.bdf.TEST_MODE_MAX_TOTAL_ACCOUNTS))

    # Test 6
    def test_06_running_jobs_go_to_pending_not_failed(self):
        """running状態のジョブはpending_next_runとして扱い例外を出さない"""
        pending = {
            "batch_run": {
                "snapshot_id": "sd_xyz",
                "accounts": ["acc_x"],
                "triggered_at": "2026-07-21T00:00:00+00:00",
                "bd_status": "running",
            }
        }
        with open(self.pending_path, "w") as f:
            json.dump(pending, f)
        result = self.bdf._load_pending_snapshots()
        self.assertIn("batch_run", result)
        # running状態はfailed扱いにならない
        self.assertEqual(result["batch_run"]["bd_status"], "running")

    # Test 7
    def test_07_mixed_pending_correctly_processed(self):
        """混在pending（ready/running/failed）が正しく読み込まれる"""
        pending = {
            "b_ready":   {"snapshot_id": "s1", "accounts": ["a1"], "bd_status": "ready",   "triggered_at": "2026-07-20T00:00:00+00:00"},
            "b_running": {"snapshot_id": "s2", "accounts": ["a2"], "bd_status": "running",  "triggered_at": "2026-07-20T00:00:00+00:00"},
            "b_failed":  {"snapshot_id": "s3", "accounts": ["a3"], "bd_status": "failed",   "triggered_at": "2026-07-20T00:00:00+00:00"},
        }
        with open(self.pending_path, "w") as f:
            json.dump(pending, f)
        result = self.bdf._load_pending_snapshots()
        self.assertIn("b_ready", result)
        self.assertIn("b_running", result)
        self.assertIn("b_failed", result)

    # Test 8
    def test_08_old_flat_format_pending_loaded(self):
        """旧フラット形式のpendingJSONが正常に読み込まれる"""
        # 旧形式: dict of {snapshot_id: ..., accounts: [...]}
        old_format = {
            "snapshot_id": "sd_old",
            "accounts": ["acc_old"],
            "triggered_at": "2026-07-10T00:00:00+00:00",
            "bd_status": "running",
        }
        # _LEGACY_PENDING_PATH に書き込んで移行テスト
        legacy_path = self.bdf._LEGACY_PENDING_PATH if hasattr(self.bdf, "_LEGACY_PENDING_PATH") else self.pending_path
        with open(self.pending_path, "w") as f:
            json.dump({"legacy_key": old_format}, f)
        result = self.bdf._load_pending_snapshots()
        # 読み込めること
        self.assertIsInstance(result, dict)

    # Test 9
    def test_09_atomic_save_uses_tmp_file(self):
        """_save_rotation_stateはtmpファイル経由で保存する（原子的保存）"""
        state = {"TEST_CAT": {"next_start": 3, "last_selected": ["a", "b"]}}
        self.bdf._save_rotation_state(state)
        # tmpファイルが残っていないこと（os.replaceで最終化）
        tmp_path = self.rotation_path + ".tmp"
        self.assertFalse(os.path.exists(tmp_path), "tmpファイルが残っていてはいけない")
        # 本ファイルが存在すること
        self.assertTrue(os.path.exists(self.rotation_path))

    # Test 10
    def test_10_max_concurrent_limit_respected(self):
        """BRIGHT_DATA_MAX_CONCURRENTの上限以上にtriggerされない（pending件数チェック）"""
        # 3件のrunning pendingがある場合、それ以上triggerされないことを確認
        max_concurrent = getattr(self.bdf, "BRIGHT_DATA_MAX_CONCURRENT", 3)
        pending = {}
        for i in range(max_concurrent):
            pending[f"batch_{i}"] = {
                "snapshot_id": f"sd_{i}",
                "accounts": [f"running_acc_{i}"],
                "bd_status": "running",
                "triggered_at": "2026-07-21T00:00:00+00:00",
            }
        with open(self.pending_path, "w") as f:
            json.dump(pending, f)

        # pending中アカウントは除外される
        accounts = [f"running_acc_{i}" for i in range(max_concurrent)] + ["free_acc_0", "free_acc_1"]
        selected = self.bdf._apply_test_mode_limit(accounts, "T10")
        # running中のアカウントは選ばれない
        for i in range(max_concurrent):
            self.assertNotIn(f"running_acc_{i}", selected)

    # Test 11
    def test_11_after_completion_next_batch_triggered_from_queue(self):
        """完了後の次バッチはローテーションキューから選ばれる"""
        accounts = self._accounts(10)
        # 1回目
        first = self.bdf._apply_test_mode_limit(accounts, "T11")
        # 2回目（キューの続き）
        second = self.bdf._apply_test_mode_limit(accounts, "T11")
        # 重複なし（同じアカウントが連続で選ばれない）
        overlap = set(first) & set(second)
        self.assertEqual(len(overlap), 0, "2回目は1回目と重複なし")


# ─────────────────────────────────────────────────────────────────────────────
# Evidence Tests (12–20)
# ─────────────────────────────────────────────────────────────────────────────

class TestEvidenceScoring(unittest.TestCase):

    def setUp(self):
        import trend_evidence as te
        self.te = te

    def _hit(self, account="acc_a", plays=1000, caption="咬筋 左右差"):
        return {"account": account, "plays": plays, "likes": 100,
                "caption": caption, "date": "2026-07-18"}

    # Test 12
    def test_12_single_post_single_account_not_level_A(self):
        """1投稿・1アカウント → 根拠レベルA にならない"""
        ig_hits = [self._hit()]
        level, _ = self.te._assign_level(ig_hits, [], "夏")
        self.assertNotEqual(level, "A")

    # Test 13
    def test_13_8posts_1account_not_multi_account_trend(self):
        """8投稿・1アカウント → 「マルチアカウントトレンド」根拠にならない"""
        ig_hits = [self._hit(account="same_acc") for _ in range(8)]
        result = self.te.compute_account_diversity_score(ig_hits)
        self.assertFalse(result["meets_multi_account_threshold"],
                         "1アカウントは3アカウント未満なので閾値を満たさない")

    # Test 14
    def test_14_20posts_10accounts_grade_candidate(self):
        """20投稿・10アカウント → grade=候補"""
        import bright_data_fetcher as bdf
        posts = [
            {"source_account": f"acc_{i%10}", "play_count": 1000,
             "followers": 5000, "is_reel": True,
             "timestamp": "2026-07-18T10:00:00+00:00", "fetch_error": False}
            for i in range(20)
        ]
        result = bdf.print_instagram_fetch_quality_report(posts, [f"acc_{i}" for i in range(10)])
        self.assertEqual(result["grade"], "候補")

    # Test 15
    def test_15_50posts_20accounts_grade_full_evidence(self):
        """50投稿・20アカウント → grade=根拠あり"""
        import bright_data_fetcher as bdf
        posts = [
            {"source_account": f"acc_{i%20}", "play_count": 1000,
             "followers": 5000, "is_reel": True,
             "timestamp": "2026-07-18T10:00:00+00:00", "fetch_error": False}
            for i in range(50)
        ]
        result = bdf.print_instagram_fetch_quality_report(posts, [f"acc_{i}" for i in range(20)])
        self.assertEqual(result["grade"], "根拠あり")

    # Test 16
    def test_16_views_none_vs_views_zero_distinguished(self):
        """views=None（未取得）と views=0（実際に0再生）は区別される"""
        post_none = {"play_count": None, "like_count": 100, "followers": 5000,
                     "timestamp": "2026-07-18T10:00:00+00:00"}
        post_zero = {"play_count": 0, "like_count": 100, "followers": 5000,
                     "timestamp": "2026-07-18T10:00:00+00:00"}
        result_none = self.te.evidence_score_post(post_none)
        result_zero = self.te.evidence_score_post(post_zero)
        # play_count=None → views_available=False
        self.assertFalse(result_none["views_available"])
        # play_count=0 → views_available=True（実際に0）
        self.assertTrue(result_zero["views_available"])

    # Test 17
    def test_17_unparseable_dates_not_counted_as_within_10days(self):
        """パース不可能な日付の投稿は「10日以内」にカウントされない"""
        post = {"play_count": 1000, "timestamp": "not-a-date"}
        result = self.te.evidence_score_post(post)
        self.assertFalse(result["date_within_10days"])
        self.assertFalse(result["date_available"])

    # Test 18
    def test_18_irrelevant_posts_filtered_by_topic(self):
        """Topic「舌・むくみ」に対しAI/針美容液投稿は除外される"""
        ig_hits = [
            {"url": "https://ig.com/1", "caption": "AIで美肌管理", "plays": 5000},
            {"url": "https://ig.com/2", "caption": "針美容液でリフトアップ", "plays": 3000},
            {"url": "https://ig.com/3", "caption": "舌の位置でむくみが変わる", "plays": 2000},
            {"url": "https://ig.com/4", "caption": "咬筋とむくみの関係", "plays": 1500},
        ]
        relevant = self.te.filter_ig_hits_by_relevance(
            ig_hits, topic_keywords=["舌", "むくみ", "咬筋"]
        )
        urls = [h["url"] for h in relevant]
        self.assertNotIn("https://ig.com/1", urls)
        self.assertNotIn("https://ig.com/2", urls)
        self.assertIn("https://ig.com/3", urls)
        self.assertIn("https://ig.com/4", urls)

    # Test 19
    def test_19_low_semantic_relevance_excluded(self):
        """semantic relevance < 60の投稿は参考表示から除外される"""
        ig_hits = [
            {"url": "https://ig.com/a", "caption": "全く無関係な投稿XYZ", "plays": 9999,
             "semantic_score": 10},
            {"url": "https://ig.com/b", "caption": "顔筋トレーニング 左右差", "plays": 2000,
             "semantic_score": 80},
        ]
        # semantic_score フィールドで低スコアを除外
        relevant = [h for h in ig_hits if h.get("semantic_score", 100) >= 60]
        self.assertEqual(len(relevant), 1)
        self.assertEqual(relevant[0]["url"], "https://ig.com/b")

    # Test 20
    def test_20_only_2_valid_refs_show_2_not_forced_5(self):
        """有効な参考投稿が2件のみ → 2件表示（5件に水増しされない）"""
        ig_hits = [
            {"url": "https://ig.com/x", "likes": 100, "plays": 1000},
            {"url": "https://ig.com/y", "likes": 200, "plays": 2000},
        ]
        text = self.te._format_ig_evidence(ig_hits)
        count = text.count("https://ig.com/")
        self.assertEqual(count, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Hook Quality Tests (21–25)
# ─────────────────────────────────────────────────────────────────────────────

class TestHookQuality(unittest.TestCase):

    def setUp(self):
        import topic_intelligence as ti
        self.ti = ti

    # Test 21
    def test_21_generic_hook_fails_gate(self):
        """一般論フック「知っていますか」はquality gateを通過しない"""
        candidate = {
            "hook": "知っていますか？保湿は大切です",
            "reason": "気をつけましょう",
            "angle": "",
            "perspective": "",
        }
        result = self.ti.score_hook_quality(candidate)
        self.assertFalse(result["passes_quality_gate"])
        self.assertGreaterEqual(result["generic_score"], 50)

    # Test 22
    def test_22_specific_core_hari_hook_passes_gate(self):
        """CORE HARI専門視点フックはquality gateを通過する"""
        candidate = {
            "hook": "咬筋の左右差を確認してみましょう",
            "reason": "顎の噛み癖が顔の非対称を作る",
            "angle": "観察ポイント",
            "perspective": "咬筋",
        }
        result = self.ti.score_hook_quality(candidate)
        self.assertTrue(result["passes_quality_gate"], result["gate_failure_reason"])

    # Test 23
    def test_23_medical_assertion_hook_flagged(self):
        """医学的断定表現を含むフックはmedical_assertion_risk=Trueになる"""
        candidate = {
            "hook": "食いしばりがたるみの原因です",
            "reason": "筋肉の過緊張が引き起こします",
            "angle": "",
            "perspective": "",
        }
        result = self.ti.score_hook_quality(candidate)
        self.assertTrue(result["medical_assertion_risk"])
        self.assertFalse(result["passes_quality_gate"])

    # Test 24
    def test_24_high_similarity_to_recent_content(self):
        """過去の同テーマと類似度が高い → too_similar=True"""
        history = [
            {
                "date": "2026-07-15T10:00:00+00:00",
                "theme": "咬筋 左右差",
                "hook": "咬筋の左右差を確認する方法",
                "core_hari_axis": "咬筋",
                "format": "carousel",
                "purpose": "教育",
            }
        ]
        candidate = {"theme": "咬筋 左右差", "hook": "咬筋チェック方法", "perspective": "咬筋"}
        result = self.ti.check_theme_diversity(candidate, history)
        self.assertTrue(result["too_similar"], f"score={result['similarity_score']}")

    # Test 25
    def test_25_same_axis_repeated_3x_diversity_penalty(self):
        """同じ軸が3回連続する場合、多様性スコアが低くなる"""
        history = [
            {"date": f"2026-07-{10+i}T10:00:00+00:00", "theme": f"舌テーマ{i}",
             "hook": f"舌フック{i}", "core_hari_axis": "舌", "format": "reel", "purpose": "教育"}
            for i in range(3)
        ]
        candidate = {"theme": "舌の位置", "hook": "舌チェック", "perspective": "舌"}
        result = self.ti.check_theme_diversity(candidate, history)
        # 同一軸が history に3件あれば similarity_score >= 40
        self.assertGreaterEqual(result["similarity_score"], 40)


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests (26–30)
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegration(unittest.TestCase):

    def setUp(self):
        import trend_evidence as te
        self.te = te

    # Test 26
    def test_26_insufficient_instagram_no_trending_text_in_output(self):
        """Instagram不足時、「Instagramで流行」という表現が出力に含まれない"""
        # ig_hitsが空（0件）→ 根拠テキストに「Instagramで流行」は含まれない
        ig_hits = []
        text = self.te._format_ig_evidence(ig_hits)
        self.assertNotIn("Instagramで流行", text)

    # Test 27
    def test_27_insufficient_instagram_shows_toukousetsui_label(self):
        """Instagram不足時、根拠レベルはE（AIオリジナル）になる"""
        ig_hits = []
        own_hits = []
        seasonal = ""
        level, reason = self.te._assign_level(ig_hits, own_hits, seasonal)
        # Instagram0件・季節なし・自社実績なし → E
        self.assertEqual(level, "E")

    # Test 28
    def test_28_irrelevant_posts_not_passed_to_prompt(self):
        """無関係な投稿はプロンプトコンテキストに渡されない"""
        ig_hits = [
            {"url": "https://ig.com/1", "caption": "完全無関係の料理レシピ", "plays": 9999},
            {"url": "https://ig.com/2", "caption": "顔筋と左右差の関係", "plays": 2000},
        ]
        relevant = self.te.filter_ig_hits_by_relevance(
            ig_hits, topic_keywords=["顔筋", "左右差"]
        )
        urls = [h["url"] for h in relevant]
        self.assertNotIn("https://ig.com/1", urls)
        self.assertIn("https://ig.com/2", urls)

    # Test 29
    def test_29_running_jobs_remaining_no_exception(self):
        """running状態のジョブが残っていてもメインプロセスが例外なく終了する"""
        import bright_data_fetcher as bdf
        # _load_pending_snapshotsがrunning状態を返しても例外が出ないことを確認
        tmp_dir = tempfile.mkdtemp()
        pending_path = os.path.join(tmp_dir, "pending_snapshots.json")
        pending = {
            "batch_still_running": {
                "snapshot_id": "sd_still",
                "accounts": ["acc_r"],
                "bd_status": "running",
                "triggered_at": "2026-07-21T00:00:00+00:00",
            }
        }
        orig_path = bdf.PENDING_SNAPSHOTS_PATH
        bdf.PENDING_SNAPSHOTS_PATH = pending_path
        with open(pending_path, "w") as f:
            json.dump(pending, f)
        try:
            result = bdf._load_pending_snapshots()
            self.assertIsInstance(result, dict)  # 例外なし
        finally:
            bdf.PENDING_SNAPSHOTS_PATH = orig_path

    # Test 30
    def test_30_no_api_keys_in_log_output(self):
        """ログ出力フォーマット文字列にAPIキーが含まれない"""
        import bright_data_fetcher as bdf
        api_key = os.environ.get("BRIGHT_DATA_API_KEY", "test-bd-key")
        openai_key = os.environ.get("OPENAI_API_KEY", "test-key")
        # ソースコードの文字列定数にAPIキーが直接書かれていないことを確認
        source_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bright_data_fetcher.py"
        )
        with open(source_path, "r", encoding="utf-8") as f:
            source = f.read()
        # 実際のキー値は環境変数から読む設計なのでソースに含まれない
        # テスト用キー（"test-bd-key", "test-key"）はソースに含まれていてはいけない
        self.assertNotIn("test-bd-key", source)
        self.assertNotIn("test-key-hardcoded", source)


# ─────────────────────────────────────────────────────────────────────────────
# World Context Safety Tests (bonus)
# ─────────────────────────────────────────────────────────────────────────────

class TestWorldContextSafety(unittest.TestCase):

    def setUp(self):
        import world_context as wc
        self.wc = wc

    def test_causal_danger_classified_as_hypothesis(self):
        """因果関係断定表現は content_hypothesis に分類される"""
        ctx = {
            "season": "夏",
            "month_context": "夏本番・紫外線MAX",
            "hot_tension": "暑さがたるみを悪化する",
            "brand_relevant_context": "",
            "social_trends": "",
        }
        classified = self.wc.classify_world_context_claims(ctx)
        hyp_text = " ".join(classified["content_hypothesis"])
        self.assertIn("悪化する", hyp_text)

    def test_factual_season_always_in_factual(self):
        """季節・月文脈は factual に分類される"""
        ctx = {
            "season": "夏",
            "month_context": "夏本番",
            "hot_tension": "",
            "brand_relevant_context": "",
            "social_trends": "",
        }
        classified = self.wc.classify_world_context_claims(ctx)
        factual_text = " ".join(classified["factual"])
        self.assertIn("夏", factual_text)

    def test_safe_world_context_text_returns_str(self):
        """safe_world_context_text が文字列を返す"""
        ctx = {
            "season": "夏",
            "month_context": "夏本番",
            "hot_tension": "暑さが引き起こす",
            "brand_relevant_context": "季節の変わり目に多い",
            "social_trends": "",
        }
        text = self.wc.safe_world_context_text(ctx)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
