#!/bin/bash
# Type a message into the secretary Claude session as if dictated. Usage: ask_secretary.sh "text"
source "$(dirname "$0")/lib.sh"
if ! session="$(secretary_target_resolve)"; then
  if [[ "${ASK_SECRETARY_QUIET:-0}" == "1" ]]; then echo "secretary not running"; exit 3; fi
  exec "$(dirname "$0")/say_now.sh" "The secretary session is not running."
fi
text="${*:-$(cat)}"
cd "$ROOT_DIR" && /Users/remi/.virtualenvs/voice2clipboard/bin/python - "$session" "$text" <<'PY'
import sys, time
sys.path.insert(0, "apps/linux/legacy_whisper")
import voice_transcriber as vt
session, text = sys.argv[1], sys.argv[2]
# verified: a dialog left open in the window (2026-09-22, "/usage") swallows typed text
ok = vt.deliver_to_claude_session(text, session, vt.secretary_log)
sys.exit(0 if ok else 4)
PY
rc=$?
if [[ "$rc" != 0 ]]; then
  log "ask_secretary: NOT delivered (the secretary's window does not take input): $(printf '%s' "$text" | head -c 80)"
  health_set secretary_input "the secretary's window is not taking typed messages (a dialog open in it?)"
  exit "$rc"
fi
[[ "$(cut -f2- "$HEALTH_DIR/secretary_input" 2>/dev/null)" == "ok" ]] || health_set secretary_input ok
log "ask_secretary: $(printf '%s' "$text" | head -c 80)"
