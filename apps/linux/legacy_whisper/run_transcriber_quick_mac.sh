#!/bin/bash
set -euo pipefail

# Headless quick mode: no terminal window, no space switch.
# Records -> transcribes (MLX) -> copies to clipboard.
# Hotkey-safe toggle:
# - first press starts capture
# - second press sends SIGTERM to stop capture cleanly

ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
LOCK_FILE="/tmp/voice2clipboard_quick.pid"
LOG_FILE="/tmp/voice2clipboard_quick.log"

if [[ -f "$LOCK_FILE" ]]; then
  EXISTING_PID="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  if [[ -n "${EXISTING_PID}" ]] && kill -0 "${EXISTING_PID}" 2>/dev/null; then
    kill -TERM "${EXISTING_PID}" 2>/dev/null || true
    osascript -e 'display notification "Voice capture stop requested." with title "voice2clipboard"' >/dev/null 2>&1 || true
    exit 0
  fi
fi

cleanup() {
  rm -f "$LOCK_FILE"
}
trap cleanup EXIT

source "$VENV"
cd "$ROOT_DIR"

env VOICE2CLIPBOARD_BACKEND=mlx python voice_transcriber.py --quick --copy-only >>"$LOG_FILE" 2>&1 &
CHILD_PID=$!
echo "$CHILD_PID" > "$LOCK_FILE"
wait "$CHILD_PID"
