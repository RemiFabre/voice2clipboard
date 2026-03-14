#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
LOCK_FILE="/tmp/voice2clipboard_quick_autopaste.pid"
META_FILE="/tmp/voice2clipboard_quick_autopaste.meta"
LOG_FILE="/tmp/voice2clipboard_quick_autopaste.log"

export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"

cleanup() {
  rm -f "$LOCK_FILE" "$META_FILE"
}
trap cleanup EXIT

if [[ ! -f "$META_FILE" ]]; then
  echo "Missing meta file: $META_FILE" >>"$LOG_FILE"
  exit 1
fi

source "$META_FILE"
source "$VENV"
cd "$ROOT_DIR"

ARGS=(--quick --target-window "${target_app:-}")
if [[ -n "${target_iterm_session:-}" ]]; then
  ARGS+=(--target-iterm-session "$target_iterm_session")
fi

env VOICE2CLIPBOARD_BACKEND=mlx python apps/linux/legacy_whisper/voice_transcriber.py "${ARGS[@]}" >>"$LOG_FILE" 2>&1 &
CHILD_PID=$!
echo "$CHILD_PID" > "$LOCK_FILE"
wait "$CHILD_PID"
