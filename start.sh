#!/usr/bin/env bash
# 启动脚本：后台运行 app.py 和 telegram_alert.py，日志输出到 logs/

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOGS_DIR"

VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    VENV_PYTHON="python3"
fi

# 停止已有进程（避免重复启动）
for pidfile in logs/app.pid logs/telegram_alert.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            echo "停止已运行的进程 PID=$pid ($pidfile)..."
            kill "$pid"
            sleep 1
        fi
        rm -f "$pidfile"
    fi
done

echo "启动 app.py ..."
nohup "$VENV_PYTHON" app.py >> "$LOGS_DIR/app.log" 2>&1 &
echo $! > "$LOGS_DIR/app.pid"
echo "  PID=$(cat $LOGS_DIR/app.pid)  日志: logs/app.log"

echo "启动 telegram_alert.py ..."
nohup "$VENV_PYTHON" telegram_alert.py >> "$LOGS_DIR/telegram_alert.log" 2>&1 &
echo $! > "$LOGS_DIR/telegram_alert.pid"
echo "  PID=$(cat $LOGS_DIR/telegram_alert.pid)  日志: logs/telegram_alert.log"

echo ""
echo "所有进程已启动，使用 ./stop.sh 停止。"
