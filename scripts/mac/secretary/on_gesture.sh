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
# "pause" (button app resting in paused, 2026-09-21): the headset sent Pause instead of Play. It does
# that for a press while it believes something is playing (a message: then this is an ordinary
# single press), and when an earbud is put into its charger. With nothing playing or recording it
# is the charger, and no dictation may start by itself; the short "not now" tone says the press, if
# it was one, was seen. Exception: for a few seconds after a message the headset still believes
# "playing", and answering right after a message is the main use: then a pause is a press.
if [[ "$gesture" == "pause" ]]; then
  ended_ago=$(( $(date +%s) - $(stat -f %m "$TTS_ENDED_FILE" 2>/dev/null || echo 0) ))
  if [[ "$dictating" == 1 ]] || recorder_alive || [[ -n "$tts" ]]; then gesture="single"
  elif [[ "$ended_ago" -lt "${SECRETARY_PAUSE_IS_PRESS_S:-8}" ]]; then
    log "pause $ended_ago s after a message: taken as a press"; gesture="single"
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
