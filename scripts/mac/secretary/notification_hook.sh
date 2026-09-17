#!/bin/bash
# Claude Code Notification hook: say when a session is blocked waiting for the user.
source "$(dirname "$0")/lib.sh"
[[ -f "$VOICE_MODE_FLAG" ]] || exit 0
input="$(cat)"
python3 - "$input" "$(dirname "$0")/inbox_post.sh" <<'PY'
import json, os, subprocess, sys
try:
    d = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)
cwd = d.get("cwd") or ""
if cwd.rstrip("/").endswith("/secretary"):
    sys.exit(0)
name = (os.path.basename(cwd.rstrip("/")) or "an agent").replace("-", " ").replace("_", " ")
kind = d.get("notification_type", "")
text = {"permission_prompt": "is waiting for a permission.", "agent_needs_input": "needs your input."}.get(kind)
if text:
    subprocess.run([sys.argv[2], "--from", name, text], check=False)
PY
exit 0
