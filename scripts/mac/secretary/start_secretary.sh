#!/bin/bash
# Opens the secretary Claude Code session in a new iTerm window, registers its session id as the
# target for earbud dictations, and turns voice mode on. Idempotent: reuses a live session.
source "$(dirname "$0")/lib.sh"
SECRETARY_DIR="$ROOT_DIR/secretary"
rotate=0; [[ "${1:-}" == "--rotate" ]] && rotate=1
existing="$(cat "$SESSION_FILE" 2>/dev/null || true)"
if [[ -n "$existing" && "$rotate" == 0 ]]; then
  if iterm_session_exists "$existing"; then
    echo "secretary already running in iTerm session $existing"
    "$(dirname "$0")/voice_mode.sh" on >/dev/null
    exit 0
  fi
fi
session_id="$(osascript <<EOS
tell application "iTerm2"
    set w to (create window with default profile command "/bin/bash -lc 'cd \"$SECRETARY_DIR\" && claude --dangerously-skip-permissions; echo claude exited; sleep 60'")
    tell current session of w
        return unique id
    end tell
end tell
EOS
)"
session_id="$(printf '%s' "$session_id" | tr -d '\r\n')"
if [[ -z "$session_id" ]]; then echo "failed to open the secretary window"; exit 1; fi
printf '%s' "$session_id" >"$SESSION_FILE"
if [[ "$rotate" == 1 ]]; then
  # Rotation: the new session is registered first, then the exhausted one is closed once the
  # new one has had time to load (its window is closed, which ends its claude process).
  log "secretary rotated: new session $session_id replaces ${existing:-none}"
  echo "secretary rotated to iTerm session $session_id"
  if [[ -n "$existing" ]]; then
    ( sleep 20; iterm_session_action "$existing" "close" >/dev/null 2>&1 ) &
  fi
  exit 0
fi
"$(dirname "$0")/voice_mode.sh" on >/dev/null
log "secretary started, iTerm session $session_id"
echo "secretary started in iTerm session $session_id; voice mode on"
nohup "$(dirname "$0")/say_now.sh" "Secretary ready." >/dev/null 2>&1 &
