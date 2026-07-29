#!/bin/bash
# 完全自動運転 Phase1 — メインラッパー
#
# 呼び出し方:
#   cron:           bash /path/to/run_daily.sh
#   GitHub Actions: .github/workflows/daily_analysis.yml から呼び出す
#   手動確認:       bash run_daily.sh

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

TODAY="$(date '+%Y-%m-%d')"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/$TODAY.log"
mkdir -p "$LOG_DIR"

START_TS=$(date +%s)

{
    echo ""
    echo "=== Phase1 START $(date '+%Y-%m-%d %H:%M:%S') ==="
} | tee -a "$LOG_FILE"

# 仮想環境の有効化（存在する場合）
if [ -f ".venv/bin/activate" ]; then
    source ".venv/bin/activate"
elif [ -f "venv/bin/activate" ]; then
    source "venv/bin/activate"
fi

# main.py 実行（stdout/stderr を両方ログへ記録）
PYTHONPATH="$SCRIPT_DIR" python3 main.py 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))

{
    if [ "$EXIT_CODE" -ne 0 ]; then
        echo "=== Phase1 FAILED (exit=$EXIT_CODE) $(date '+%Y-%m-%d %H:%M:%S') ==="
    else
        echo "=== Phase1 DONE $(date '+%Y-%m-%d %H:%M:%S') ==="
    fi
    echo "実行時間: ${ELAPSED}秒"
} | tee -a "$LOG_FILE"

# cron / GitHub Actions どちらでも常に 0 で終了（エラーはログに記録済み）
exit 0
