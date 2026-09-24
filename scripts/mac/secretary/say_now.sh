#!/bin/bash
# Speak text immediately (interrupting any current speech).
# Usage: say_now.sh [--lang en|fr] [--voice kokoro_voice] [--wav ready.wav] "text"
#   --wav: audio rendered ahead of time (queued messages); the text is then only logged and
#          archived, and playback starts at once. Without it the text is rendered here.
# Playback runs through afplay whose pid is recorded, so tts_toggle.sh can pause/resume it.
source "$(dirname "$0")/lib.sh"
lang="en"; voice=""; wav=""
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --lang) lang="$2"; shift 2 ;;
    --voice) voice="$2"; shift 2 ;;
    --wav) wav="$2"; shift 2 ;;
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
    SAY_NOW_DEFERRED=1 nohup bash -c 'source "$1/lib.sh"; wait_for_audio_free; exec "$1/say_now.sh" --lang "$2" --voice "$3" ${5:+--wav "$5"} "$4"' _ "$(cd "$(dirname "$0")" && pwd)" "$lang" "$voice" "$text" "$wav" >/dev/null 2>&1 &
    echo "deferred until the current audio ends"
    exit 0
  fi
fi
if [[ "${SAY_NOW_INTERRUPT:-0}" == "1" ]]; then tts_stop; fi
# Hard guard: the speech lock. If someone else holds it, this message waits in the background.
if ! speech_lock_acquire; then
  log "say_now deferred (speech lock held by $(speech_lock_owner)): $(printf '%s' "$text" | head -c 60)"
  SAY_NOW_DEFERRED=1 nohup bash -c 'source "$1/lib.sh"; wait_for_audio_free; exec "$1/say_now.sh" --lang "$2" --voice "$3" ${5:+--wav "$5"} "$4"' _ "$(cd "$(dirname "$0")" && pwd)" "$lang" "$voice" "$text" "$wav" >/dev/null 2>&1 &
  echo "deferred until the current audio ends"
  exit 0
fi
trap 'speech_lock_release' EXIT
# Hold the "speaking" slot from now on (synthesis takes 1-2 s).
echo $$ >"$TTS_PID_FILE"; echo preparing >"$TTS_STATE_FILE"; rm -f "$TTS_CLOCK_FILE"
# Direct speech that still has to be rendered: keep its text until it starts to sound, so a stop
# in between moves it to the inbox instead of losing it (tts_requeue_if_unheard in lib.sh).
# Inbox playback is not concerned: its text is already in the archive.
rm -f "$TTS_TEXT_FILE"
if [[ -z "$wav" && -z "${SAY_NOW_ARCHIVE:-}" ]]; then printf '%s\n%s\n%s\n' "$lang" "$voice" "$text" >"$TTS_TEXT_FILE"; fi
# Archived file of the message being read (set by inbox playback), for the played/stopped note.
[[ -n "${SAY_NOW_ARCHIVE:-}" ]] && printf '%s' "$SAY_NOW_ARCHIVE" >"$TTS_CURRENT_FILE"
source_note=""
if [[ -n "$wav" && -s "$wav" ]]; then
  cp "$wav" "$TTS_WAV"; source_note=" pre-rendered"
elif ! render_speech "$lang" "$voice" "$TTS_WAV" "$text"; then
  # never a silent failure: a press may be waiting for this speech
  log "say_now: kokoro failed"; rm -f "$TTS_PID_FILE" "$TTS_STATE_FILE" "$TTS_TEXT_FILE"; play_cue "$FAIL_SOUND"; exit 1
fi
# Every message ends with a very discreet tone (Remi, 2026-09-20): a pause inside a message sounds
# like its end, and a press meant to start a dictation then paused the message instead. The tone
# is joined to the audio, so it only plays at the natural end, never after a stop or a discard,
# and it is the moment from which a single press starts a dictation (see TTS_TAIL_S in lib.sh).
END_TONE="$ROOT_DIR/sounds/cue_message_end.wav"
if [[ "${SECRETARY_END_TONE:-1}" == "1" && -s "$END_TONE" ]]; then
  python3 "$SPEECH_RENDER" concat --lead-in-ms 0 --gap-ms 0 --out "$TTS_WAV" "$TTS_WAV" "$END_TONE" >/dev/null 2>&1 \
    || log "say_now: end tone could not be joined (format mismatch?), message plays without it"
fi
log "say_now [$voice$source_note]: $(printf '%s' "$text" | head -c 80)"
rm -f "$TTS_TEXT_FILE"   # from here on it is being heard
player_pid=""
# muted: tests run the whole path without sound, or with a stand-in player (SECRETARY_PLAYER)
if [[ "${SECRETARY_CUES_MUTED:-0}" != "1" || -n "${SECRETARY_PLAYER:-}" ]]; then
  ensure_audible   # speech is either asked for by a press or important enough to speak unasked
  # This process owns the message for its whole life, pauses included: a pause ends the player
  # (tts_pause in lib.sh explains why), and the rest is played from here on resume, starting
  # SECRETARY_TTS_REWIND_S before the point of the pause so that no word is lost.
  echo $$ >"$TTS_OWNER_FILE"; rm -f "$TTS_PAUSE_FILE" "$TTS_RESUME_FILE"
  total="$(wav_seconds "$TTS_WAV")"; playing="$TTS_WAV"
  while :; do
    "${SECRETARY_PLAYER:-afplay}" "$playing" &
    player_pid=$!
    echo "$player_pid" >"$TTS_PID_FILE"; echo playing >"$TTS_STATE_FILE"
    tts_clock_start "$(wav_seconds "$playing")"
    wait "$player_pid" 2>/dev/null
    [[ -f "$TTS_PAUSE_FILE" && "$(cat "$TTS_PID_FILE" 2>/dev/null)" == "$$" ]] || break   # ended, stopped or replaced
    until [[ -f "$TTS_RESUME_FILE" ]]; do
      [[ -f "$TTS_PAUSE_FILE" && "$(cat "$TTS_PID_FILE" 2>/dev/null)" == "$$" ]] || break 2   # discarded while paused
      /bin/sleep 0.1
    done
    left="$(cat "$TTS_PAUSE_FILE" 2>/dev/null)"; rm -f "$TTS_PAUSE_FILE" "$TTS_RESUME_FILE"
    from="$(perl -e 'my $f = $ARGV[0] - $ARGV[1] - $ARGV[2]; printf "%.2f", $f > 0 ? $f : 0' -- "${total:-0}" "${left:-0}" "${SECRETARY_TTS_REWIND_S:-1.0}")"
    playing="$TTS_WAV.rest.wav"
    if ! python3 "$SPEECH_RENDER" tail --from-s "$from" --out "$playing" "$TTS_WAV" >/dev/null 2>&1; then
      log "say_now: could not cut the rest of the message, replaying it from the start"; playing="$TTS_WAV"
    fi
  done
  [[ "$(cat "$TTS_OWNER_FILE" 2>/dev/null)" == "$$" ]] && rm -f "$TTS_OWNER_FILE"
  rm -f "$TTS_WAV.rest.wav"
fi
# The message no longer sounds: note when, and let the button app tell the headset "paused" again
# (audio makes it believe "playing", and then a press arrives as Pause instead of Play).
: >"$TTS_ENDED_FILE"
[[ "${SECRETARY_CUES_MUTED:-0}" == "1" ]] || "$ROOT_DIR/scripts/mac/earbuds/ctl.sh" settle >/dev/null 2>&1 || true
archive_note played
# Clean up only what is still ours: after an interruption the next message has already written
# its own pid and clock, and removing those would make it invisible to the buttons.
current="$(cat "$TTS_PID_FILE" 2>/dev/null || true)"
if [[ -z "$current" || "$current" == "$player_pid" || "$current" == "$$" ]]; then
  rm -f "$TTS_PID_FILE" "$TTS_STATE_FILE" "$TTS_CURRENT_FILE" "$TTS_CLOCK_FILE"
fi
