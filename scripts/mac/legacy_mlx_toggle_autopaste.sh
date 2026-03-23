#!/bin/bash
set -euo pipefail

# Legacy local MLX Whisper toggle launcher for Mac.
# - first press: start capture
# - second press: stop capture, transcribe, and send to original app/session

ROOT_DIR="/Users/remi/voice2clipboard"
LOCK_FILE="/tmp/voice2clipboard_quick_autopaste.pid"
META_FILE="/tmp/voice2clipboard_quick_autopaste.meta"
LOG_FILE="/tmp/voice2clipboard_quick_autopaste.log"
STOP_FILE="/tmp/voice2clipboard_quick_autopaste.stop"
AUDIO_STATE_FILE="/tmp/voice2clipboard_quick_autopaste.audio"
PHASE_FILE="/tmp/voice2clipboard_quick_autopaste.phase"
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
  : > "$STOP_FILE"
  kill -TERM "$pid" >/dev/null 2>&1 || true
  osascript -e 'display notification "Voice capture stop requested." with title "voice2clipboard"' >/dev/null 2>&1 || true
}

latest_audio_fallback() {
  find "${ROOT_DIR}/recordings" -type f -name audio.wav -mmin -30 -print 2>/dev/null | tail -n 1
}

recover_stuck_run() {
  local pid="$1"
  local target_app="$2"
  local target_iterm_session="$3"
  local helper_launch_state="$4"
  local audio_path=""
  local snapshot=""
  local recovery_args=("--quick")

  if [[ -f "$AUDIO_STATE_FILE" ]]; then
    audio_path="$(cat "$AUDIO_STATE_FILE" 2>/dev/null || true)"
  fi
  if [[ -z "$audio_path" || ! -f "$audio_path" ]]; then
    audio_path="$(latest_audio_fallback)"
  fi
  if [[ -n "$audio_path" && -f "$audio_path" ]]; then
    snapshot="$(mktemp /tmp/voice2clipboard_recover_XXXXXX)"
    snapshot="${snapshot}.wav"
    cp "$audio_path" "$snapshot"
  fi

  echo "Recorder still alive after stop timeout; forcing recovery..." >>"$LOG_FILE"
  kill -KILL "$pid" >/dev/null 2>&1 || true

  if [[ -n "$target_app" ]]; then
    recovery_args+=("--target-window" "$target_app")
  fi
  if [[ -n "$target_iterm_session" ]]; then
    recovery_args+=("--target-iterm-session" "$target_iterm_session")
  fi

  if [[ -n "$snapshot" && -s "$snapshot" ]]; then
    echo "Recovering transcription from snapshot: $snapshot" >>"$LOG_FILE"
    (
      export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
      export VOICE2CLIPBOARD_BACKEND=mlx
      export VOICE2CLIPBOARD_HELPER_LAUNCH_STATE="${helper_launch_state:-recovered}"
      unset VOICE2CLIPBOARD_MLX_HELPER
      cd "$ROOT_DIR"
      source /Users/remi/.virtualenvs/voice2clipboard/bin/activate
      python apps/linux/legacy_whisper/voice_transcriber.py "${recovery_args[@]}" "$snapshot" >>"$LOG_FILE" 2>&1
    ) &
  else
    echo "No audio snapshot available for stuck-run recovery." >>"$LOG_FILE"
  fi
}

if [[ -f "$LOCK_FILE" ]]; then
  EXISTING_PID="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  if [[ -n "${EXISTING_PID}" ]] && kill -0 "${EXISTING_PID}" 2>/dev/null; then
    TARGET_APP="$(sed -n 's/^target_app=//p' "$META_FILE" 2>/dev/null | tail -n 1)"
    TARGET_ITERM_SESSION="$(sed -n 's/^target_iterm_session=//p' "$META_FILE" 2>/dev/null | tail -n 1)"
    HELPER_LAUNCH_STATE="$(sed -n 's/^helper_launch_state=//p' "$META_FILE" 2>/dev/null | tail -n 1)"
    request_stop "$EXISTING_PID"
    for _ in {1..20}; do
      if ! kill -0 "${EXISTING_PID}" 2>/dev/null; then
        exit 0
      fi
      sleep 0.2
    done
    recover_stuck_run "$EXISTING_PID" "$TARGET_APP" "$TARGET_ITERM_SESSION" "$HELPER_LAUNCH_STATE"
    exit 0
  fi
  rm -f "$LOCK_FILE" "$META_FILE" "$STOP_FILE" "$AUDIO_STATE_FILE" "$PHASE_FILE"
fi

rm -f "$STOP_FILE" "$AUDIO_STATE_FILE" "$PHASE_FILE"

ORIGINAL_APP="$(get_frontmost_app)"
TARGET_ITERM_SESSION=""
if [[ "$ORIGINAL_APP" == "iTerm2" ]]; then
  TARGET_ITERM_SESSION="$(get_iterm_session_id)"
fi
HELPER_LAUNCH_STATE="$("$HELPER_CTL" start)"
SESSION_ID="$(uuidgen)"

cat > "$META_FILE" <<EOF
session_id=$SESSION_ID
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
