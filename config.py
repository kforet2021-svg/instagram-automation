"""
config.py
.env から各種設定値を読み込むモジュール。

このプロジェクトでは以下の環境変数を使用する:
- OPENAI_API_KEY
- BRIGHT_DATA_API_KEY  (リール/プロフィール取得。bright_data_fetcher.pyが使用)
- GOOGLE_SHEET_ID
- GOOGLE_SERVICE_ACCOUNT_JSON  (※ GOOGLE_ACCOUNT_JSON ではない)

取得対象アカウント(ジャンル不問のアンテナアカウント)は accounts.py の
ANTENNA_ACCOUNTSで管理する。新規アカウント候補はcandidate_discovery.pyが
取得済み投稿から抽出し、複数のアンテナアカウントから累積で言及されたものは
人の承認なしに自動でANTENNA_ACCOUNTSに追加される(main.pyが実行ごとに
accounts_writer.add_accountsを呼ぶ)。

2026-06-29: Apifyを完全停止した。APIFY_API_TOKENはこのモジュールでは
読み込まない(=main.pyの実行経路でApifyの環境変数は一切参照・使用しない)。
apify_fetcher.py / competitor_discovery.py はバックアップとして残しているが、
これらを手動で再度有効化する場合は、APIFY_API_TOKEN の読み込みをこのファイルに
復元する必要がある。
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Creator Intelligence Platform: アクティブVertical ---
# 環境変数 ACTIVE_VERTICAL で上書き可能。
# 将来: ACTIVE_VERTICAL=yoga_studio python3 main.py で別Verticalに切り替え。
ACTIVE_VERTICAL: str = os.getenv("ACTIVE_VERTICAL", "core_hari")

# --- 地域設定 ---
# World Context は全国ニュースより地域情報を優先する。
# 環境変数 REGION で上書き可能: REGION="東京都" python3 main.py
REGION: str = os.getenv("REGION", "北海道札幌市")

# --- API認証情報 ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY", "")

# --- Googleスプレッドシート ---
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
# 注意: GOOGLE_ACCOUNT_JSON ではなく GOOGLE_SERVICE_ACCOUNT_JSON を使用する
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")


def validate_config() -> None:
    """必須項目が.envに設定されているか検証する。不足があれば例外を投げる。"""
    required = {
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "BRIGHT_DATA_API_KEY": BRIGHT_DATA_API_KEY,
        "GOOGLE_SHEET_ID": GOOGLE_SHEET_ID,
        "GOOGLE_SERVICE_ACCOUNT_JSON": GOOGLE_SERVICE_ACCOUNT_JSON,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise EnvironmentError(
            ".envに以下の項目が設定されていません: " + ", ".join(missing)
            + "\n.env.example を参考に .env を作成してください。"
        )
