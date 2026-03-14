#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
SOCKET_PATH="${VOICE2CLIPBOARD_MLX_HELPER_SOCKET:-/tmp/voice2clipboard_mlx_helper.sock}"
STATE_PATH="${VOICE2CLIPBOARD_MLX_HELPER_STATE:-/tmp/voice2clipboard_mlx_helper_state.json}"
PID_PATH="${VOICE2CLIPBOARD_MLX_HELPER_PID:-/tmp/voice2clipboard_mlx_helper.pid}"
LOG_PATH="${VOICE2CLIPBOARD_MLX_HELPER_LOG:-/tmp/voice2clipboard_mlx_helper.log}"

export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"

is_running() {
  if [[ ! -f "$PID_PATH" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "$PID_PATH" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

start_helper() {
  if is_running; then
    echo "already_running"
    return 0
  fi
  rm -f "$SOCKET_PATH" "$PID_PATH"
  nohup /bin/bash -lc "source '$VENV' && cd '$ROOT_DIR' && exec python -u tools/mlx_whisper_helper.py >>'$LOG_PATH' 2>&1" >/dev/null 2>&1 &
  echo "started"
}

status_helper() {
  if [[ -f "$STATE_PATH" ]]; then
    cat "$STATE_PATH"
  else
    printf '{"status":"stopped"}\n'
  fi
}

stop_helper() {
  if is_running; then
    local pid
    pid="$(cat "$PID_PATH")"
    python3 - <<PY
import os, signal
os.kill($pid, signal.SIGTERM)
PY
    echo "stopped"
  else
    rm -f "$SOCKET_PATH" "$PID_PATH"
    echo "not_running"
  fi
}

case "${1:-status}" in
  start) start_helper ;;
  status) status_helper ;;
  stop) stop_helper ;;
  *)
    echo "usage: $0 {start|status|stop}" >&2
    exit 1
    ;;
esac
