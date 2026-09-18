#!/bin/bash
# Claude Code Notification hook: a session is blocked on Remi (permission or input). Always flags
# it in the ledger; in headset mode also says so with a ding.
source "$(dirname "$0")/lib.sh"
input="$(cat)"
python3 - "$input" "$(dirname "$0")" "$([[ -f "$VOICE_MODE_FLAG" ]] && echo 1 || echo 0)" <<'PY'
import json, subprocess, sys
sys.path.insert(0, sys.argv[2])
import ledger_lib as L
try:
    d = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)
cwd = d.get("cwd") or ""
if cwd.rstrip("/").endswith("/secretary"):
    sys.exit(0)
name = L.project_name(cwd)
kind = d.get("notification_type", "")
text = {"permission_prompt": "is waiting for a permission.", "agent_needs_input": "needs your input."}.get(kind)
if not text:
    sys.exit(0)
L.write(d.get("session_id", "unknown"), project=name, cwd=cwd, needs_attention=True,
        reason=text.rstrip("."), state="blocked")
if sys.argv[3] == "1":
    subprocess.run([sys.argv[2] + "/inbox_post.sh", "--from", name, text], check=False)
PY
exit 0
