#!/bin/bash
# Called by the earbud button app on Bluetooth connect/disconnect, and when the headset's
# microphone opens or closes: on_headset.sh connected|disconnected|present|mic-open|mic-closed "<device name>"
#   present:      the button app (re)started and found the headset already connected. Same check,
#                 but no ready cue: nothing happened from Remi's side, and an unexplained sound
#                 sends him looking for a message. Problems are still announced.
#   disconnected: a running dictation is stopped at once (what was said is transcribed and
#                 delivered) and any speech is stopped, since nobody hears it any more.
#   connected:    the button app takes the buttons back, then a self-check: ready cue, or the
#                 failure buzz and a spoken reason, so Remi knows before he starts talking.
#   mic-open:     some process opened the headset microphone (the list is in HEADSET_MIC_FILE, and
#                 changes of that list arrive as mic-open again). Normal during a dictation. With
#                 no dictation it means call mode: the buttons are dead and Remi cannot know why,
#                 so: health flag "callmode", failure buzz and one spoken sentence per episode.
#   mic-closed:   flag cleared; the ready cue if the problem had been announced.
source "$(dirname "$0")/lib.sh"
event="${1:-}"; name="${2:-}"
is_headset_name "$name" || { log "bluetooth $event: $name (not the headset, ignored)"; exit 0; }
# The framework reports some events twice within milliseconds: only one handler per event may run.
# Atomic claim (mkdir), held until this handler ends; a claim older than 30 s is stale.
CLAIM="$SECRETARY_RUNTIME/headset_event.$event.lock"
if ! mkdir "$CLAIM" 2>/dev/null; then
  age=$(( $(date +%s) - $(stat -f %m "$CLAIM" 2>/dev/null || echo 0) ))
  [[ "$age" -lt 30 ]] && exit 0
  rmdir "$CLAIM" 2>/dev/null; mkdir "$CLAIM" 2>/dev/null || exit 0
fi
trap 'rmdir "$CLAIM" 2>/dev/null' EXIT
log "headset $event: $name"
case "$event" in
  disconnected)
    if recorder_alive; then
      log "headset disconnected during a dictation: asking the recorder to stop"
      : >"$DICTATION_STOP_FILE"
    fi
    [[ -n "$(tts_pid)" ]] && { tts_stop; log "tts stopped (headset gone)"; } ;;
  connected)
    sleep "${SECRETARY_RECONNECT_SETTLE_S:-3}"    # let macOS route audio to the headset first
    "$ROOT_DIR/scripts/mac/earbuds/ctl.sh" reassert >/dev/null 2>&1 || true
    recorder_alive && exit 0                      # never play a cue into a running dictation
    "$(dirname "$0")/selfcheck.sh" --speak >/dev/null ;;
  present)
    sleep "${SECRETARY_RECONNECT_SETTLE_S:-3}"
    recorder_alive && exit 0
    "$(dirname "$0")/selfcheck.sh" --speak-problems >/dev/null ;;
  mic-open)
    # grace: the recorder opens the microphone a moment before its lock exists, and a program
    # that only probes the microphone is gone again within seconds
    sleep "${SECRETARY_CALLMODE_GRACE_S:-8}"
    # Two looks, a few seconds apart. On 2026-09-21 18:39 a single look fell into the two seconds
    # between a dying recorder releasing its lock and its microphone closing: "another program
    # is using the microphone" was flagged and spoken about our own recorder.
    [[ -n "$(CALLMODE_PEEK=1 callmode_problem)" ]] || { callmode_problem >/dev/null; exit 0; }
    sleep "${SECRETARY_CALLMODE_CONFIRM_S:-4}"
    problem="$(callmode_problem)"
    [[ -n "$problem" ]] || { log "call mode: gone at the second look (a recorder winding down), nothing said"; exit 0; }
    holders="$(headset_mic_holders | tr '\n' ' ')"
    log "call mode without a dictation: $problem (holders: $holders)"
    [[ "$(cat "$CALLMODE_NOTIFIED_FILE" 2>/dev/null)" == "$problem" ]] && exit 0   # already told
    # a program that opens and closes the microphone again and again is announced once per 10 min
    if [[ "$(cat "$CALLMODE_NOTIFIED_FILE.last" 2>/dev/null)" == "$problem" ]] &&
       [[ $(( $(date +%s) - $(stat -f %m "$CALLMODE_NOTIFIED_FILE.last" 2>/dev/null || echo 0) )) -lt "${SECRETARY_CALLMODE_REPEAT_S:-600}" ]]; then
      log "call mode: announced less than 10 min ago, staying quiet"; exit 0
    fi
    printf '%s' "$problem" >"$CALLMODE_NOTIFIED_FILE"
    if grep -Eqi "$CALLMODE_QUIET_APPS" <<<"$holders $problem"; then
      log "call mode: looks like a real call, flagged but not spoken"; exit 0
    fi
    ensure_audible
    play_cue "$FAIL_SOUND"; sleep 1.6
    # Short by Remi's order (2026-09-23, after hearing the long version while talking to a web
    # page through Firefox): the program's name and the fact, nothing else.
    who="$(headset_mic_holders | while IFS=: read -r p e; do process_friendly_name "$p" "$e"; done | head -n 1)"
    nohup "$(dirname "$0")/say_now.sh" "Buttons off: ${who:-another program} has the microphone." >/dev/null 2>&1 & ;;
  mic-closed)
    callmode_problem >/dev/null
    if [[ -f "$CALLMODE_NOTIFIED_FILE" ]]; then
      mv -f "$CALLMODE_NOTIFIED_FILE" "$CALLMODE_NOTIFIED_FILE.last"; touch "$CALLMODE_NOTIFIED_FILE.last"
      log "call mode ended: the buttons work again"
      dictation_active || [[ -n "$(tts_pid)" ]] || play_cue "$READY_SOUND"
    fi ;;
esac
