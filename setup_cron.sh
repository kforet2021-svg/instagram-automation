#!/bin/bash
# ローカルcron登録ヘルパー（一回だけ実行する）
#
# 使い方: bash setup_cron.sh
# 毎朝 7:00 に run_daily.sh を実行するcronジョブを登録する。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SCRIPT="$SCRIPT_DIR/run_daily.sh"
CRON_ENTRY="0 7 * * * bash \"$RUN_SCRIPT\""

# 既に登録済みかチェック
if crontab -l 2>/dev/null | grep -qF "run_daily.sh"; then
    echo "既にcrontabに登録済みです："
    crontab -l | grep "run_daily.sh"
    exit 0
fi

echo "以下のエントリをcrontabに追加します："
echo "  $CRON_ENTRY"
echo ""
printf "続けますか？ [y/N]: "
read -r confirm

if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
    echo ""
    echo "登録完了。現在のcrontabを確認："
    crontab -l
else
    echo "キャンセルしました。"
    echo ""
    echo "手動で登録する場合は crontab -e を開いて以下を追加してください："
    echo "  $CRON_ENTRY"
fi
