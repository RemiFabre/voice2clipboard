#!/bin/bash
# Shared paths for the voice secretary layer (earbuds -> dictation -> Claude sessions -> spoken replies).
ROOT_DIR="/Users/remi/voice2clipboard"
SECRETARY_RUNTIME="$ROOT_DIR/runtime/secretary"
INBOX_DIR="$SECRETARY_RUNTIME/inbox"          # queued spoken messages, oldest first
SPOKEN_DIR="$SECRETARY_RUNTIME/spoken"        # archive of what was read
TTS_PID_FILE="$SECRETARY_RUNTIME/tts.pid"     # afplay pid while speaking
TTS_STATE_FILE="$SECRETARY_RUNTIME/tts.state" # playing | paused
TTS_WAV="$SECRETARY_RUNTIME/tts_current.wav"
VOICE_MODE_FLAG="$SECRETARY_RUNTIME/voice_mode.on"
SESSION_FILE="$SECRETARY_RUNTIME/secretary_iterm_session"
LOG_FILE="$SECRETARY_RUNTIME/secretary.log"
DING_SOUND="/System/Library/Sounds/Glass.aiff"
KOKORO_SAY="/Users/remi/local-tts-lab/.venv/bin/kokoro-say"
KOKORO_CTL="/Users/remi/local-tts-lab/.venv/bin/local-tts"
export PYTORCH_ENABLE_MPS_FALLBACK=1
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
mkdir -p "$INBOX_DIR" "$SPOKEN_DIR"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG_FILE"; }

tts_pid() {
  local pid
  pid="$(cat "$TTS_PID_FILE" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then echo "$pid"; else rm -f "$TTS_PID_FILE" "$TTS_STATE_FILE"; fi
}

tts_stop() {
  local pid; pid="$(tts_pid)"
  if [[ -n "$pid" ]]; then kill -CONT "$pid" 2>/dev/null; kill -TERM "$pid" 2>/dev/null; fi
  rm -f "$TTS_PID_FILE" "$TTS_STATE_FILE"
}
