#!/bin/bash
# Type a message into the secretary Claude session as if dictated. Usage: ask_secretary.sh "text"
source "$(dirname "$0")/lib.sh"
session="$(cat "$SESSION_FILE" 2>/dev/null || true)"
if [[ -z "$session" ]] || ! iterm_session_exists "$session"; then
  exec "$(dirname "$0")/say_now.sh" "The secretary session is not running."
fi
text="${*:-$(cat)}"
cd "$ROOT_DIR" && /Users/remi/.virtualenvs/voice2clipboard/bin/python - "$session" "$text" <<'PY'
import sys, time
sys.path.insert(0, "apps/linux/legacy_whisper")
import voice_transcriber as vt
session, text = sys.argv[1], sys.argv[2]
vt.send_text_to_iterm_session(text, session)
time.sleep(0.4)
vt.send_enter_to_iterm_session(session)
PY
log "ask_secretary: $(printf '%s' "$text" | head -c 80)"
