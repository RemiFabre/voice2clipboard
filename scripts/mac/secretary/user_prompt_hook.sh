#!/bin/bash
# Claude Code UserPromptSubmit hook: Remi just talked to this session (keyboard, voice or typed),
# so it no longer needs his attention. Silent, never blocks.
source "$(dirname "$0")/lib.sh"
input="$(cat)"
python3 - "$input" "$(dirname "$0")" <<'PY'
import json, sys
sys.path.insert(0, sys.argv[2])
import ledger_lib as L
try:
    d = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)
cwd = d.get("cwd") or ""
if L.is_ping_prompt(d.get("prompt", "")):
    # the Tower's keep-warm ping, not Remi: the ledger must not change (see ledger_lib.py)
    L.ping_mark(d.get("session_id", "unknown"))
    sys.exit(0)
if L.is_secretary(cwd, d.get("session_id", "")):
    # every message the secretary receives re-checks that dictations are aimed at its window
    L.register_secretary_window(sys.argv[2], d.get("session_id", ""))
    sys.exit(0)
L.write(d.get("session_id", "unknown"), project=L.project_name(cwd), cwd=cwd,
        needs_attention=False, reason="", state="working on your request")
PY
exit 0
