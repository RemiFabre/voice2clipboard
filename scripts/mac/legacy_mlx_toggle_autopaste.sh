#!/bin/bash
set -euo pipefail

# Legacy local MLX Whisper toggle launcher for Mac.
# - first press: start capture
# - second press: stop capture, transcribe, and send to original app/session

ROOT_DIR="/Users/remi/voice2clipboard"
LOCK_FILE="/tmp/voice2clipboard_quick_autopaste.pid"
META_FILE="/tmp/voice2clipboard_quick_autopaste.meta"
LOG_FILE="/tmp/voice2clipboard_quick_autopaste.log"
WORKER_SCRIPT="${ROOT_DIR}/scripts/mac/legacy_mlx_toggle_autopaste_worker.sh"
HELPER_CTL="${ROOT_DIR}/scripts/mac/mlx_whisper_helper_ctl.sh"

# Karabiner launches shell commands in a minimal, non-login environment.
# Add Homebrew and common local bins explicitly so mlx-whisper can find ffmpeg.
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"

get_frontmost_app() {
  osascript -e 'tell application "System Events" to get name of first process whose frontmost is true' | tr -d '\r'
}

get_iterm_session_id() {
  osascript <<'EOF' 2>/dev/null | tr -d '\r'
tell application "iTerm2"
    try
        tell current session of current window
            return unique id
        end tell
    on error
        return ""
    end try
end tell
EOF
}

request_stop() {
  local pid="$1"
  kill -TERM "$pid" >/dev/null 2>&1 || true
  osascript -e 'display notification "Voice capture stop requested." with title "voice2clipboard"' >/dev/null 2>&1 || true
}

if [[ -f "$LOCK_FILE" ]]; then
  EXISTING_PID="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  if [[ -n "${EXISTING_PID}" ]] && kill -0 "${EXISTING_PID}" 2>/dev/null; then
    request_stop "$EXISTING_PID"
    exit 0
  fi
  rm -f "$LOCK_FILE" "$META_FILE"
fi

ORIGINAL_APP="$(get_frontmost_app)"
TARGET_ITERM_SESSION=""
if [[ "$ORIGINAL_APP" == "iTerm2" ]]; then
  TARGET_ITERM_SESSION="$(get_iterm_session_id)"
fi
HELPER_LAUNCH_STATE="$("$HELPER_CTL" start)"

cat > "$META_FILE" <<EOF
started_at=$(date -Iseconds)
target_app=$ORIGINAL_APP
target_iterm_session=$TARGET_ITERM_SESSION
helper_launch_state=$HELPER_LAUNCH_STATE
EOF

osascript <<EOF >>"$LOG_FILE" 2>&1
tell application "iTerm2"
    create window with default profile command "/bin/bash $WORKER_SCRIPT"
end tell
EOF

for _ in {1..50}; do
  if [[ -f "$LOCK_FILE" ]]; then
    exit 0
  fi
  sleep 0.1
done

echo "Timed out waiting for quick-autopaste worker to start." >>"$LOG_FILE"
exit 1
