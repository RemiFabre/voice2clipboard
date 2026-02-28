#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
LOG_FILE="/Users/remi/voice2clipboard/logs/always_on_voxtral_daemon.log"
RUNTIME_DIR="/Users/remi/voice2clipboard/runtime/always_on"
PID_FILE="${RUNTIME_DIR}/daemon.pid"

mkdir -p "$(dirname "$LOG_FILE")" "$RUNTIME_DIR"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
    echo "Daemon already running (pid=$PID)"
    exit 0
  fi
fi

source "$VENV"
cd "$ROOT_DIR"

python tools/always_on_voxtral_daemon.py --runtime-dir "$RUNTIME_DIR" >>"$LOG_FILE" 2>&1
