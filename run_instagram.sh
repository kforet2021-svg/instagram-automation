#!/bin/bash
# CORE HARI FACE — Instagram投稿生成 ワンコマンドランチャー
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 仮想環境の有効化（存在する場合）
if [ -f ".venv/bin/activate" ]; then
    source ".venv/bin/activate"
elif [ -f "venv/bin/activate" ]; then
    source "venv/bin/activate"
fi

exec python3 main.py "$@"
