#!/bin/bash
# Claude Code Notification hook: a session is blocked on Remi (permission or input). Flags it in
# the ledger and hands it to the secretary, which decides; "always" projects post directly, and
# so does anything when no secretary session is running.
source "$(dirname "$0")/lib.sh"
input="$(cat)"
python3 - "$input" "$(dirname "$0")" <<'PY'
import json, subprocess, sys
sys.path.insert(0, sys.argv[2])
import ledger_lib as L
try:
    d = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)
scripts = sys.argv[2]
cwd = d.get("cwd") or ""
if cwd.rstrip("/").endswith("/secretary"):
    sys.exit(0)
name = L.project_name(cwd)
kind = d.get("notification_type", "")
text = {"permission_prompt": "is waiting for a permission.", "agent_needs_input": "needs your input."}.get(kind)
if not text:
    sys.exit(0)
session_id = d.get("session_id", "unknown")
L.write(session_id, project=name, cwd=cwd, needs_attention=True, reason=text.rstrip("."), state="blocked")
policy = L.policy_for(name)
if policy == "never":
    sys.exit(0)
if policy == "always" or not L.forward_to_secretary(scripts, name, session_id, "waiting on Remi, " + text.rstrip("."), name + " " + text):
    subprocess.run([scripts + "/inbox_post.sh", "--from", name, text], check=False)
PY
exit 0
