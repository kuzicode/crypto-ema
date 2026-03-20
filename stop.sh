#!/usr/bin/env bash
# 停止 start.sh 启动的后台进程

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

for pidfile in logs/app.pid logs/telegram_alert.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            echo "停止 PID=$pid ($pidfile)..."
            kill "$pid"
        else
            echo "进程 PID=$pid 已不在运行 ($pidfile)"
        fi
        rm -f "$pidfile"
    else
        echo "未找到 $pidfile，跳过"
    fi
done

echo "完成。"
