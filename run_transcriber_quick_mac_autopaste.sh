#!/bin/bash
set -euo pipefail

# Headless quick mode with auto-paste.
# Records -> transcribes (MLX) -> pastes into original frontmost app.

ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
LOCK_FILE="/tmp/voice2clipboard_quick_autopaste.pid"
LOG_FILE="/tmp/voice2clipboard_quick_autopaste.log"

ORIGINAL_APP="$(osascript -e 'tell application \"System Events\" to get name of first process whose frontmost is true')"

if [[ -f "$LOCK_FILE" ]]; then
  EXISTING_PID="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  if [[ -n "${EXISTING_PID}" ]] && kill -0 "${EXISTING_PID}" 2>/dev/null; then
    osascript -e 'display notification "Voice auto-paste is already running." with title "voice2clipboard"'
    exit 0
  fi
fi

echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

source "$VENV"
cd "$ROOT_DIR"

VOICE2CLIPBOARD_BACKEND=mlx python voice_transcriber.py --quick --target-window "$ORIGINAL_APP" >>"$LOG_FILE" 2>&1

