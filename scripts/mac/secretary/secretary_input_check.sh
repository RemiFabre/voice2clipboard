#!/bin/bash
# Does the secretary's window take typed input? On 2026-09-22 "/usage" had been submitted at its
# keyboard; the dialog stayed open for two hours and every dictation and report typed into the
# window vanished. Claude Code reports such a session as "waiting" in its session file.
#   secretary_input_check.sh [--clear] [<iTerm id>]   prints nothing when fine, one line otherwise
#   --clear: press Escape once to close a dialog, then check again (used at the press)
# Health flag: secretary_input.
source "$(dirname "$0")/lib.sh"
clear=0; [[ "${1:-}" == "--clear" ]] && { clear=1; shift; }
session="${1:-}"; [[ -n "$session" ]] || session="$(secretary_target_resolve)" || exit 0
PY=/Users/remi/.virtualenvs/voice2clipboard/bin/python
status="$(cat "/Users/remi/.claude/sessions/$(cat "$SECRETARY_CLAUDE_PID_FILE" 2>/dev/null).json" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' 2>/dev/null)"
ready() { cd "$ROOT_DIR" && "$PY" - "$session" <<'EOF'
import sys; sys.path.insert(0, "apps/linux/legacy_whisper")
import voice_transcriber as vt
sys.exit(0 if vt.claude_input_ready(sys.argv[1]) else 1)
EOF
}
if ready && [[ "$status" != "waiting" ]]; then
  [[ "$(cut -f2- "$HEALTH_DIR/secretary_input" 2>/dev/null)" == "ok" ]] || health_set secretary_input ok
  exit 0
fi
if [[ "$clear" == 1 ]]; then
  cd "$ROOT_DIR" && "$PY" - "$session" <<'EOF'
import sys; sys.path.insert(0, "apps/linux/legacy_whisper")
import voice_transcriber as vt
vt.send_escape_to_iterm_session(sys.argv[1])
EOF
  sleep 0.8
  if ready; then log "secretary window had a dialog open (status ${status:-?}): closed it with Escape"; health_set secretary_input ok; exit 0; fi
fi
text="the secretary's window is not taking typed messages (a dialog open in it, status ${status:-unknown})"
[[ "$(cut -f2- "$HEALTH_DIR/secretary_input" 2>/dev/null)" == "$text" ]] || { health_set secretary_input "$text"; log "secretary input check: $text"; }
echo "$text"
exit 1
