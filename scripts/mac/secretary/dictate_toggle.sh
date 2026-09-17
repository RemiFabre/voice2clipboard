#!/bin/bash
# Double earbud press: start a dictation aimed at the secretary session (or stop the running one).
# Falls back to the normal keyboard behaviour (frontmost app) when no secretary session is registered.
source "$(dirname "$0")/lib.sh"
tts_stop
session="$(cat "$SESSION_FILE" 2>/dev/null || true)"
if [[ -n "$session" ]]; then
  export VOICE2CLIPBOARD_TARGET_ITERM_SESSION="$session"
  log "dictate_toggle -> secretary session $session"
else
  log "dictate_toggle -> no secretary session, using frontmost app"
fi
exec "$ROOT_DIR/scripts/mac/legacy_mlx_toggle_autopaste.sh"
