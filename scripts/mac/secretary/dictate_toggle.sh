#!/bin/bash
# Earbud press (or the secretary's own shortcut): start a dictation aimed at the secretary session,
# or stop the running one. Falls back to the normal keyboard behaviour (frontmost app) when no
# secretary was ever registered.
source "$(dirname "$0")/lib.sh"
LAUNCHER="${SECRETARY_LAUNCHER:-$ROOT_DIR/scripts/mac/legacy_mlx_toggle_autopaste.sh}"   # overridable: tests never open the microphone
tts_stop
# A second press in the second before the recorder is up: wait for its lock so this press stops
# that recording instead of opening a second recorder next to it.
if dictation_pending_only; then
  for _ in $(seq 1 25); do recorder_alive && break; sleep 0.2; done
fi
if recorder_alive; then
  log "dictate_toggle -> stop the running dictation"
  exec "$LAUNCHER"
fi
# Mark the dictation as pending right away: the recorder lock only appears ~1 s later and no
# speech may start in between. The recorder removes the marker once its lock exists.
touch "$DICTATION_PENDING"
registered="$(cat "$SESSION_FILE" 2>/dev/null || true)"
if session="$(secretary_target_resolve)"; then
  export VOICE2CLIPBOARD_TARGET_ITERM_SESSION="$session"
  log "dictate_toggle -> secretary session $session"
  # Lazy rotation: if the secretary is cold and a fresh one is cheaper (the Session Tower
  # decides), a successor boots while he talks and the transcript goes there. In the background:
  # the start cue must not wait for it, and it can only ever fall back to this session.
  nohup "$(dirname "$0")/lazy_rotate.sh" "$session" >/dev/null 2>&1 &
  # A dialog left open in the secretary's window ("/usage" on 2026-09-22) swallows the transcript.
  # The recording gives time to close it: checked and cleared in the background, never blocking.
  nohup "$(dirname "$0")/secretary_input_check.sh" --clear "$session" >/dev/null 2>&1 &
elif [[ -n "$registered" ]]; then
  # A secretary was registered but its window is gone and its process cannot be found. Typing
  # into a dead window loses the dictation (2026-09-19), so: failure buzz now, record anyway,
  # keep the text (recordings folder + clipboard), and queue a note explaining it.
  export VOICE2CLIPBOARD_TARGET_ITERM_SESSION="$registered" VOICE2CLIPBOARD_COPY_ONLY=1
  log "dictate_toggle -> secretary window $registered is gone: recording to disk and clipboard only"
  play_cue "$FAIL_SOUND"
  "$(dirname "$0")/inbox_post.sh" --from secretary "My window was missing when you dictated, so that dictation was not delivered to anyone. The text is saved in the recordings folder and in the clipboard. Please reopen me." >/dev/null 2>&1
else
  log "dictate_toggle -> no secretary session, using frontmost app"
fi
"$LAUNCHER"; rc=$?
if [[ "$rc" != 0 ]]; then
  # The recorder never came up: do not leave the system looking busy, and say so.
  rm -f "$DICTATION_PENDING"
  log "dictate_toggle: recorder failed to start (exit $rc)"
  play_cue "$FAIL_SOUND"
fi
exit "$rc"
