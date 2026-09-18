#!/bin/bash
# Speak text immediately (interrupting any current speech).
# Usage: say_now.sh [--lang en|fr] [--voice kokoro_voice] "text"
# Playback runs through afplay whose pid is recorded, so tts_toggle.sh can pause/resume it.
source "$(dirname "$0")/lib.sh"
lang="en"; voice=""
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --lang) lang="$2"; shift 2 ;;
    --voice) voice="$2"; shift 2 ;;
    *) shift ;;
  esac
done
[[ -z "$voice" ]] && voice="$(voice_for "" "$lang")"
text="${*:-$(cat)}"
[[ -z "$text" ]] && exit 0
# Never talk over a dictation: defer to a background waiter and return at once.
if dictation_active && [[ "${SAY_NOW_DEFERRED:-0}" != "1" ]]; then
  log "say_now deferred (dictation active): $(printf '%s' "$text" | head -c 60)"
  SAY_NOW_DEFERRED=1 nohup bash -c 'source "$1/lib.sh"; wait_for_dictation_end; exec "$1/say_now.sh" --lang "$2" --voice "$3" "$4"' _ "$(cd "$(dirname "$0")" && pwd)" "$lang" "$voice" "$text" >/dev/null 2>&1 &
  echo "deferred until the dictation ends"
  exit 0
fi
tts_stop
"$KOKORO_CTL" kokoro-daemon status >/dev/null 2>&1 || "$KOKORO_CTL" kokoro-daemon start >/dev/null 2>&1
if ! "$KOKORO_SAY" --lang "$lang" --voice "$voice" --no-play --output "$TTS_WAV" "$text" >/dev/null 2>&1; then
  log "say_now: kokoro failed"; exit 1
fi
afplay "$TTS_WAV" &
echo $! >"$TTS_PID_FILE"; echo playing >"$TTS_STATE_FILE"
log "say_now [$voice]: $(printf '%s' "$text" | head -c 80)"
wait $!
rm -f "$TTS_PID_FILE" "$TTS_STATE_FILE"
