#!/bin/bash
# Entry point called by the earbud button app. Gestures: single | double | triple
# State machine (Remi's spec, 2026-09-17 evening; robustness pass 2026-09-19):
#   idle            single = start dictation      double = hear the latest notification  triple = ask secretary what needs attention
#   dictating       one press = stop and send (the headset hides a double press in call mode; see the runbook)
#   message playing single = pause                double = stop and discard           triple = stop and play the next queued
#   message paused  single = resume               double = stop and discard           triple = stop and play the next queued
# Note: while the headset mic is open (dictating) its buttons arrive as hands-free call commands,
# not media commands; the recorder itself watches the Bluetooth log for them and stops. The
# handling below only serves the keyboard-started path and the second before the recorder is up.
# Rule: every press gets a sound. Anything refused plays the "cannot do that now" cue.
source "$(dirname "$0")/lib.sh"
gesture="${1:-}"
# One source of truth: the recorder lock, plus the short press-to-lock marker (see lib.sh).
dictating=0; dictation_active && dictating=1
# A message whose sound is over is not "playing", even if its player has not exited yet.
tts_finish_if_over
tts="$(tts_pid)"; tts_state="$(cat "$TTS_STATE_FILE" 2>/dev/null || true)"
log "gesture: $gesture (dictating=$dictating tts=${tts:+${tts_state:-playing}})"
echo "$$" >"$GESTURE_LAST_FILE"
# "pause" (button app resting in paused, 2026-09-21): the headset sent Pause instead of Play. It does
# that for a press while it believes something is playing (a message: then this is an ordinary
# single press), and when an earbud is put into its charger. With nothing playing or recording it
# is the charger, and no dictation may start by itself; the short "not now" tone says the press, if
# it was one, was seen. Exception: for a few seconds after a message the headset still believes
# "playing", and answering right after a message is the main use: then a pause is a press.
# Two more moments when the headset believes "playing" (2026-10-28, Remi: "the first press fails,
# the retry works, more and more lately"): after a dictation (the call and the stop cue; until the
# button app's next claim, up to a minute: 20 of the 39 presses within a minute of a dictation's end
# arrived as Pause since 10-01, 1 of 113 later), and while the button app holds "playing" because a
# browser tab keeps taking the buttons. There a pause is a press too, unless the headset drops
# within PAUSE_DOCK_WAIT_S: putting it away right after a dictation is common, and the charger's
# Pause comes up to 0.7 s before the disconnect (2.3 s once in 31 dockings, which the recorder's
# phantom check then catches).
pause_is_press_because() {   # prints why a pause is a press now, or fails
  local now t line until
  now="$(date +%s)"
  if [[ "$(headset_mic_state)" == closed ]]; then
    t="$(date -j -f '%Y-%m-%d %H:%M:%S' "$(cut -f1 "$HEADSET_MIC_FILE" 2>/dev/null | cut -c1-19)" +%s 2>/dev/null || echo 0)"
    if (( now - t < ${SECRETARY_PAUSE_AFTER_DICTATION_S:-75} )); then echo "$(( now - t )) s after a dictation"; return 0; fi
  fi
  line="$(tail -n 300 "$EARBUDS_LOG_FILE" 2>/dev/null | grep 'holding playing for' | tail -n 1)"
  if [[ -n "$line" ]]; then
    t="$(date -j -f '%Y-%m-%d %H:%M:%S' "${line:0:19}" +%s 2>/dev/null || echo 0)"
    until=$(( t + $(sed -E 's/.*holding playing for ([0-9]+) s.*/\1/' <<<"$line") ))
    if (( now < until )); then echo "while the button app holds playing ($(( until - now )) s left)"; return 0; fi
  fi
  return 1
}
if [[ "$gesture" == "pause" ]]; then
  ended_ago=$(( $(date +%s) - $(stat -f %m "$TTS_ENDED_FILE" 2>/dev/null || echo 0) ))
  if [[ "$dictating" == 1 ]] || recorder_alive || [[ -n "$tts" ]]; then gesture="single"
  elif [[ "$ended_ago" -lt "${SECRETARY_PAUSE_IS_PRESS_S:-8}" ]]; then
    log "pause $ended_ago s after a message: taken as a press"; gesture="single"
  elif why="$(pause_is_press_because)"; then
    pressed_at="$(date +%s)"
    sleep "${SECRETARY_PAUSE_DOCK_WAIT_S:-1.5}"
    gone_at="$(stat -f %m "$HEADSET_GONE_FILE" 2>/dev/null || echo 0)"
    if (( gone_at >= pressed_at - 3 )); then
      refuse_cue "pause $why, then the headset disconnected: put away, no dictation"; exit 0
    fi
    if [[ "$(cat "$GESTURE_LAST_FILE" 2>/dev/null)" != "$$" ]]; then
      log "pause $why: a newer press came meanwhile, it decides"; exit 0
    fi
    log "pause $why: taken as a press"; gesture="single"
    dictating=0; dictation_active && dictating=1
  else
    refuse_cue "pause while nothing plays or records: headset put away (or a press sent as pause), no dictation"
    exit 0
  fi
fi
# While a recorder is running, a press is handed to it: the recorder tells one press (stop and
# send) from two (cancel, nothing sent, audio kept) and plays the matching sound. A press already
# classified by the headset arrives here as "double" and cancels at once. If the recorder does
# not react, the old stop path takes over so a press is never lost.
if recorder_alive; then
  printf '%s\n' "$gesture" >>"$DICTATION_PRESS_FILE"
  log "press handed to the recorder: $gesture"
  ( sleep 4
    if recorder_alive && [[ "$(cat "$DICTATION_PHASE_FILE" 2>/dev/null || echo recording)" == "recording" ]]; then
      log "recorder did not react to the press: forcing the stop"
      "$(dirname "$0")/dictate_toggle.sh"
    fi ) >/dev/null 2>&1 &
  exit 0
fi
# All feedback below is sound: make sure the headset is not muted or at zero before any of it.
ensure_audible
status_query='[Voice] Secretary: what needs my attention? First run selfcheck.sh: if it prints problems with the earbud system (buttons held by another app, headset in call mode, volume, microphone), say them first in plain words. Then run ledger.sh and answer by voice with say_now: the sessions waiting on me and what they asked, then a one-line roundup of the others.'

case "$gesture" in
  single)
    if [[ "$dictating" == 1 ]]; then exec "$(dirname "$0")/dictate_toggle.sh"; fi
    if [[ -n "$tts" ]]; then
      # "preparing": the voice is still being rendered; there is nothing to pause yet, and
      # freezing the renderer would be a press with no audible effect. Say "not now" instead.
      if [[ "$tts_state" == "preparing" ]]; then refuse_cue "single press while a message is being prepared"
      elif [[ "$tts_state" == "paused" ]]; then tts_resume "$tts"
      else tts_pause "$tts"; fi
      exit 0
    fi
    exec "$(dirname "$0")/dictate_toggle.sh" ;;
  double)
    if [[ "$dictating" == 1 ]]; then exec "$(dirname "$0")/dictate_toggle.sh"; fi
    # Speech still being prepared (usually an answer that waited for the previous message to
    # end) has not been heard: a double press cannot mean "discard it". It plays in a moment;
    # the ticks say "coming". A preparation stuck for over 45 s is stopped like any message.
    if [[ -n "$tts" && "$tts_state" == "preparing" && $(( $(date +%s) - $(stat -f %m "$TTS_STATE_FILE" 2>/dev/null || echo 0) )) -lt 45 ]]; then
      log "double press while speech is being prepared: left alone, it plays next"
      play_cue "$ROOT_DIR/sounds/cue_ack.aiff"; exit 0
    fi
    # discarding is confirmed by a sound: on a paused message it would otherwise be a silent press
    if [[ -n "$tts" ]]; then tts_stop; log "tts stopped"; play_cue "$ROOT_DIR/sounds/cue_cancel.aiff"; exit 0; fi
    # "working on it" ticks only when the voice still has to be rendered
    next_message_ready || play_cue "$ROOT_DIR/sounds/cue_ack.aiff"
    nohup "$(dirname "$0")/inbox_read_next.sh" >/dev/null 2>&1 & ;;
  triple)
    if [[ "$dictating" == 1 ]]; then exec "$(dirname "$0")/dictate_toggle.sh"; fi
    if [[ -n "$tts" && "$tts_state" == "preparing" && $(( $(date +%s) - $(stat -f %m "$TTS_STATE_FILE" 2>/dev/null || echo 0) )) -lt 45 ]]; then
      log "triple press while speech is being prepared: left alone, it plays next"
      play_cue "$ROOT_DIR/sounds/cue_ack.aiff"; exit 0
    fi
    if [[ -n "$tts" ]]; then
      # while a message plays or is paused: stop it and go straight to the next queued one
      tts_stop; log "tts stopped, next"
      next_message_ready || play_cue "$ROOT_DIR/sounds/cue_ack.aiff"
      nohup "$(dirname "$0")/inbox_read_next.sh" >/dev/null 2>&1 &
      exit 0
    fi
    if ! secretary_target_resolve >/dev/null; then
      play_cue "$FAIL_SOUND"
      SAY_NOW_INTERRUPT=1 nohup "$(dirname "$0")/say_now.sh" "The secretary session is not running, so I cannot read the ledger." >/dev/null 2>&1 &
      exit 0
    fi
    play_cue "$ROOT_DIR/sounds/cue_ack.aiff"   # "working on it" while the secretary thinks
    nohup "$(dirname "$0")/ask_secretary.sh" "$status_query" >/dev/null 2>&1 & ;;
  *) log "unknown gesture: $gesture"; exit 1 ;;
esac
