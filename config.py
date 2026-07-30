"""
config.py
.env から各種設定値を読み込むモジュール。

このプロジェクトでは以下の環境変数を使用する:
- OPENAI_API_KEY
- APIFY_API_TOKEN       (instagram_fetcher.py / Apify経由のリール・プロフィール取得)
- GOOGLE_SHEET_ID
- GOOGLE_SERVICE_ACCOUNT_JSON  (※ GOOGLE_ACCOUNT_JSON ではない)
- INSTAGRAM_FETCH_PROVIDER     (省略時 "brightdata"。現在は "apify" を使用)
- BRIGHT_DATA_API_KEY  (旧プロバイダ。現在は未使用、必須チェックから除外)

取得対象アカウント(ジャンル不問のアンテナアカウント)は accounts.py の
ANTENNA_ACCOUNTSで管理する。新規アカウント候補はcandidate_discovery.pyが
取得済み投稿から抽出し、複数のアンテナアカウントから累積で言及されたものは
人の承認なしに自動でANTENNA_ACCOUNTSに追加される(main.pyが実行ごとに
accounts_writer.add_accountsを呼ぶ)。

2026-07-30: Bright Data → Apify に完全移行。BRIGHT_DATA_API_KEY は
バックアップとして読み込むが validate_config() の必須チェックから除外。
APIFY_API_TOKEN を必須に昇格。
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
# 投稿生成に使うモデル（.envで変更可能。未設定時はgpt-4o-mini）
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY", "")  # 旧プロバイダ、現在未使用

# --- Googleスプレッドシート ---
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
# 注意: GOOGLE_ACCOUNT_JSON ではなく GOOGLE_SERVICE_ACCOUNT_JSON を使用する
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")


def validate_config() -> None:
    """必須項目が.envに設定されているか検証する。不足があれば例外を投げる。"""
    required = {
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "APIFY_API_TOKEN": APIFY_API_TOKEN,
        "GOOGLE_SHEET_ID": GOOGLE_SHEET_ID,
        "GOOGLE_SERVICE_ACCOUNT_JSON": GOOGLE_SERVICE_ACCOUNT_JSON,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise EnvironmentError(
            ".envに以下の項目が設定されていません: " + ", ".join(missing)
            + "\n.env.example を参考に .env を作成してください。"
        )
