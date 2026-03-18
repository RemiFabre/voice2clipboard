#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
SOCKET_PATH="${VOICE2CLIPBOARD_MLX_HELPER_SOCKET:-/tmp/voice2clipboard_mlx_helper.sock}"
STATE_PATH="${VOICE2CLIPBOARD_MLX_HELPER_STATE:-/tmp/voice2clipboard_mlx_helper_state.json}"
PID_PATH="${VOICE2CLIPBOARD_MLX_HELPER_PID:-/tmp/voice2clipboard_mlx_helper.pid}"
LOG_PATH="${VOICE2CLIPBOARD_MLX_HELPER_LOG:-/tmp/voice2clipboard_mlx_helper.log}"

export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"

cleanup_stale() {
  rm -f "$SOCKET_PATH" "$PID_PATH"
  if [[ -f "$STATE_PATH" ]]; then
    python3 - "$STATE_PATH" <<'PY' >/dev/null 2>&1 || rm -f "$STATE_PATH"
import json
import sys
from datetime import datetime

path = sys.argv[1]
with open(path, "r") as f:
    state = json.load(f)
state["status"] = "stopped"
state["updated_at"] = datetime.now().isoformat()
state["rss_mb"] = 0
with open(path, "w") as f:
    json.dump(state, f, indent=2)
PY
  fi
}

is_running() {
  if [[ ! -f "$PID_PATH" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "$PID_PATH" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 1
  if ! kill -0 "$pid" 2>/dev/null; then
    return 1
  fi
  ps -p "$pid" -o command= 2>/dev/null | grep -q "mlx_whisper_helper.py"
}

start_helper() {
  if is_running; then
    echo "already_running"
    return 0
  fi
  cleanup_stale
  nohup /bin/bash -lc "source '$VENV' && cd '$ROOT_DIR' && exec python -u tools/mlx_whisper_helper.py >>'$LOG_PATH' 2>&1" >/dev/null 2>&1 &
  echo "started"
}

status_helper() {
  if is_running && [[ -f "$STATE_PATH" ]]; then
    cat "$STATE_PATH"
  elif [[ -f "$STATE_PATH" ]]; then
    cleanup_stale
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
    for _ in {1..20}; do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 0.1
    done
    cleanup_stale
    echo "stopped"
  else
    cleanup_stale
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
