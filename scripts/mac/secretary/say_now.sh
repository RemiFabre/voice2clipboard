#!/bin/bash
# Speak text immediately (interrupting any current speech). Usage: say_now.sh [--lang en|fr] "text"
# Playback runs through afplay whose pid is recorded, so tts_toggle.sh can pause/resume it.
source "$(dirname "$0")/lib.sh"
lang="en"
if [[ "${1:-}" == "--lang" ]]; then lang="$2"; shift 2; fi
text="${*:-$(cat)}"
[[ -z "$text" ]] && exit 0
tts_stop
"$KOKORO_CTL" kokoro-daemon status >/dev/null 2>&1 || "$KOKORO_CTL" kokoro-daemon start >/dev/null 2>&1
if ! "$KOKORO_SAY" --lang "$lang" --no-play --output "$TTS_WAV" "$text" >/dev/null 2>&1; then
  log "say_now: kokoro failed"; exit 1
fi
afplay "$TTS_WAV" &
echo $! >"$TTS_PID_FILE"; echo playing >"$TTS_STATE_FILE"
log "say_now: $(printf '%s' "$text" | head -c 80)"
wait $!
rm -f "$TTS_PID_FILE" "$TTS_STATE_FILE"
