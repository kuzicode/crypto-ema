#!/usr/bin/env bash
# 启动脚本：后台运行 telegram_alert.py，日志输出到 logs/

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOGS_DIR"
PID_FILE="$LOGS_DIR/telegram_alert.pid"
LOG_FILE="$LOGS_DIR/telegram_alert.log"

VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    VENV_PYTHON="python3"
fi

echo "启动 telegram_alert.py ..."
if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        echo "停止已运行的 telegram_alert.py PID=$pid ..."
        kill "$pid"
        sleep 1
    fi
    rm -f "$PID_FILE"
fi

nohup "$VENV_PYTHON" telegram_alert.py >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "  PID=$(cat "$PID_FILE")  日志: logs/telegram_alert.log"

echo ""
echo "telegram 监控已启动，使用 ./stop.sh 停止。"
