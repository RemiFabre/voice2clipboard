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
if cwd.rstrip("/").endswith("/secretary"):
    sys.exit(0)
L.write(d.get("session_id", "unknown"), project=L.project_name(cwd), cwd=cwd,
        needs_attention=False, reason="", state="working on your request")
PY
exit 0
