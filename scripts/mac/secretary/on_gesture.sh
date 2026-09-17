#!/bin/bash
# Entry point called by the earbud button app. Gestures: single | double | triple
# State machine (Remi's spec, 2026-09-17 evening):
#   idle            single = start dictation      double = read next queued message   triple = ask secretary for status
#   dictating       single = stop dictation       double = stop dictation             triple = (ignored)
#   message playing single = pause                double = stop message               triple = stop + status
#   message paused  single = resume               double = stop message               triple = stop + status
# Note: while the headset mic is open (dictating) its buttons arrive as hands-free call commands,
# not media commands; the recorder itself watches the Bluetooth log for them and stops. The
# single/double handling below only serves the keyboard-started path.
source "$(dirname "$0")/lib.sh"
LOCK_FILE="/tmp/voice2clipboard_quick_autopaste.pid"
gesture="${1:-}"
dictating=0
if [[ -f "$LOCK_FILE" ]]; then
  pid="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && dictating=1
fi
tts="$(tts_pid)"; tts_state="$(cat "$TTS_STATE_FILE" 2>/dev/null || true)"
log "gesture: $gesture (dictating=$dictating tts=${tts:+${tts_state:-playing}})"
status_query='[Voice] Secretary: give me a short spoken status. What is pending or waiting on me across the agents, and anything I should know? Answer with say_now.'

case "$gesture" in
  single)
    if [[ "$dictating" == 1 ]]; then exec "$(dirname "$0")/dictate_toggle.sh"; fi
    if [[ -n "$tts" ]]; then
      if [[ "$tts_state" == "paused" ]]; then kill -CONT "$tts" && echo playing >"$TTS_STATE_FILE" && log "tts resumed"
      else kill -STOP "$tts" && echo paused >"$TTS_STATE_FILE" && log "tts paused"; fi
      exit 0
    fi
    exec "$(dirname "$0")/dictate_toggle.sh" ;;
  double)
    if [[ "$dictating" == 1 ]]; then exec "$(dirname "$0")/dictate_toggle.sh"; fi
    if [[ -n "$tts" ]]; then tts_stop; log "tts stopped"; exit 0; fi
    nohup "$(dirname "$0")/inbox_read_next.sh" >/dev/null 2>&1 & ;;
  triple)
    if [[ "$dictating" == 1 ]]; then exit 0; fi
    tts_stop
    nohup "$(dirname "$0")/ask_secretary.sh" "$status_query" >/dev/null 2>&1 & ;;
  *) log "unknown gesture: $gesture"; exit 1 ;;
esac
