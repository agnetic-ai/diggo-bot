#!/bin/bash
# DIGGO Miner CLI Manager
set -euo pipefail

DIR="/opt/diggo-miner"
if [ -f "$DIR/.venv/bin/python3" ]; then
  PYTHON_BIN="$DIR/.venv/bin/python3"
else
  PYTHON_BIN="python3"
fi
RUNNER="$DIR/runner.py"
LOG_FILE="$DIR/diggo_runner.log"
STATUS_FILE="$DIR/status.json"

cd "$DIR"

ACTION="${1:-status}"

case "$ACTION" in
  start)
    if pgrep -f "$RUNNER.*--loop" >/dev/null; then
      echo "DIGGO Miner daemon is ALREADY running (PID: $(pgrep -f "$RUNNER.*--loop"))"
      exit 0
    fi
    nohup "$PYTHON_BIN" "$RUNNER" --loop >> "$LOG_FILE" 2>&1 &
    PID=$!
    echo "DIGGO Miner daemon started in background (PID: $PID)"
    echo "Logs: tail -f $LOG_FILE"
    ;;
  stop)
    if pgrep -f "$RUNNER.*--loop" >/dev/null; then
      pkill -f "$RUNNER.*--loop" || true
      echo "DIGGO Miner daemon stopped."
    else
      echo "DIGGO Miner daemon is not running."
    fi
    ;;
  restart)
    $0 stop
    sleep 1
    $0 start
    ;;
  status)
    echo "=================================================="
    echo "DIGGO Miner Service Status"
    echo "=================================================="
    if pgrep -f "$RUNNER.*--loop" >/dev/null; then
      echo "Status: RUNNING in background (PID: $(pgrep -f "$RUNNER.*--loop"))"
    else
      echo "Status: STOPPED"
    fi
    echo ""
    if [ -f "$STATUS_FILE" ]; then
      echo "Latest Telemetry ($STATUS_FILE):"
      cat "$STATUS_FILE"
    else
      echo "No telemetry data yet. Run '$0 once' to test."
    fi
    echo "=================================================="
    ;;
  once|run)
    shift || true
    "$PYTHON_BIN" "$RUNNER" --once "$@"
    ;;
  loop|daemon)
    shift || true
    "$PYTHON_BIN" "$RUNNER" --loop "$@"
    ;;
  log|logs)
    tail -n 60 -f "$LOG_FILE"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|once|loop|log}"
    exit 1
    ;;
esac
