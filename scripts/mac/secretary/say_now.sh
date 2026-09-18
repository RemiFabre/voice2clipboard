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
# Serialization rules:
#  - never start while a dictation is running (or about to start);
#  - press-driven playback (SAY_NOW_INTERRUPT=1: inbox playback, repeat) stops current speech;
#  - anything else (the secretary's direct speech, deferred speech) waits its turn instead of
#    cutting what is playing. Waiting happens in a detached process so the caller returns at once.
if [[ "${SAY_NOW_DEFERRED:-0}" != "1" ]]; then
  if dictation_active || { [[ "${SAY_NOW_INTERRUPT:-0}" != "1" ]] && [[ -n "$(tts_pid)" ]]; }; then
    log "say_now deferred (audio busy): $(printf '%s' "$text" | head -c 60)"
    SAY_NOW_DEFERRED=1 nohup bash -c 'source "$1/lib.sh"; wait_for_audio_free; exec "$1/say_now.sh" --lang "$2" --voice "$3" "$4"' _ "$(cd "$(dirname "$0")" && pwd)" "$lang" "$voice" "$text" >/dev/null 2>&1 &
    echo "deferred until the current audio ends"
    exit 0
  fi
fi
tts_stop
# Hold the "speaking" slot from now on (synthesis takes 1-2 s): otherwise a second message could
# start while this one is still being rendered and the two would overlap.
echo $$ >"$TTS_PID_FILE"; echo preparing >"$TTS_STATE_FILE"
text="$(printf '%s' "$text" | python3 "$(dirname "$0")/dictionary.py" pronounce)"
"$KOKORO_CTL" kokoro-daemon status >/dev/null 2>&1 || "$KOKORO_CTL" kokoro-daemon start >/dev/null 2>&1
if ! "$KOKORO_SAY" --lang "$lang" --voice "$voice" --no-play --output "$TTS_WAV" "$text" >/dev/null 2>&1; then
  log "say_now: kokoro failed"; rm -f "$TTS_PID_FILE" "$TTS_STATE_FILE"; exit 1
fi
afplay "$TTS_WAV" &
echo $! >"$TTS_PID_FILE"; echo playing >"$TTS_STATE_FILE"
log "say_now [$voice]: $(printf '%s' "$text" | head -c 80)"
wait $!
rm -f "$TTS_PID_FILE" "$TTS_STATE_FILE"
