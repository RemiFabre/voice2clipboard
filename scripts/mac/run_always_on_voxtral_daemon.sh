#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
LOG_FILE="/Users/remi/voice2clipboard/logs/always_on_voxtral_daemon.log"
RUNTIME_DIR="/Users/remi/voice2clipboard/runtime/always_on"
PID_FILE="${RUNTIME_DIR}/daemon.pid"
VOXMLX_HOST="${VOXMLX_HOST:-127.0.0.1}"
VOXMLX_PORT="${VOXMLX_PORT:-8010}"
WAIT_SERVER_S="${VOICE2CLIP_WAIT_SERVER_S:-180}"
WAIT_POLL_S="${VOICE2CLIP_WAIT_POLL_S:-0.5}"

mkdir -p "$(dirname "$LOG_FILE")" "$RUNTIME_DIR"

is_expected_daemon_pid() {
  local pid="$1"
  local cmd
  cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  [[ "$cmd" == *"tools/always_on_voxtral_daemon.py"* ]]
}

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null && is_expected_daemon_pid "$PID"; then
      echo "Daemon already running (pid=$PID)"
      exit 0
  fi
  rm -f "$PID_FILE"
fi

source "$VENV"
cd "$ROOT_DIR"

EXTRA_ARGS=()
EXTRA_ARGS+=(--url "ws://${VOXMLX_HOST}:${VOXMLX_PORT}/v1/realtime")
EXTRA_ARGS+=(--wait-server-s "$WAIT_SERVER_S" --wait-poll-s "$WAIT_POLL_S")
if [[ "${VOICE2CLIP_VOICE_COMMANDS:-1}" == "1" ]]; then
  EXTRA_ARGS+=(--voice-commands)
fi
if [[ -n "${VOICE2CLIP_VOICE_START_PHRASES:-}" ]]; then
  EXTRA_ARGS+=(--voice-start-phrases "$VOICE2CLIP_VOICE_START_PHRASES")
fi
if [[ -n "${VOICE2CLIP_VOICE_STOP_PHRASES:-}" ]]; then
  EXTRA_ARGS+=(--voice-stop-phrases "$VOICE2CLIP_VOICE_STOP_PHRASES")
fi
if [[ -n "${VOICE2CLIP_VOICE_COMMAND_COOLDOWN:-}" ]]; then
  EXTRA_ARGS+=(--voice-command-cooldown "$VOICE2CLIP_VOICE_COMMAND_COOLDOWN")
fi

python tools/always_on_voxtral_daemon.py --runtime-dir "$RUNTIME_DIR" "${EXTRA_ARGS[@]}" >>"$LOG_FILE" 2>&1
