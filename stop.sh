#!/usr/bin/env bash
# 停止 start.sh 启动的 telegram_alert.py 进程

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="logs/telegram_alert.pid"

if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        echo "停止 telegram_alert.py PID=$pid ..."
        kill "$pid"
    else
        echo "进程 PID=$pid 已不在运行 ($PID_FILE)"
    fi
    rm -f "$PID_FILE"
else
    echo "未找到 $PID_FILE，跳过"
fi

echo "完成。"
