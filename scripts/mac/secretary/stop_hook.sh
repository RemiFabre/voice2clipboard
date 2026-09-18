#!/bin/bash
# Claude Code Stop hook. Always records the session's latest message in the attention ledger
# (both modes, silent). In headset mode (voice_mode.on) it also queues the spoken version with
# a ding. Never blocks Claude (always exits 0).
source "$(dirname "$0")/lib.sh"
input="$(cat)"
python3 - "$input" "$(dirname "$0")" "$([[ -f "$VOICE_MODE_FLAG" ]] && echo 1 || echo 0)" <<'PY'
import json, subprocess, sys
sys.path.insert(0, sys.argv[2])
import ledger_lib as L
try:
    d = json.loads(sys.argv[1])
except Exception as e:
    print("stop_hook: bad json:", e, file=sys.stderr); sys.exit(0)
headset = sys.argv[3] == "1"
cwd = d.get("cwd") or ""
if d.get("agent_id") or cwd.rstrip("/").endswith("/secretary"):
    sys.exit(0)
msg = (d.get("last_assistant_message") or "").strip()
if not msg:
    sys.exit(0)
name = L.project_name(cwd)
text = L.spoken_text(msg)
needs = L.needs_attention(msg)
L.write(d.get("session_id", "unknown"), project=name, cwd=cwd, summary=text,
        needs_attention=needs, reason="asked you something" if needs else "", state="finished a turn")
if headset:
    subprocess.run([sys.argv[2] + "/inbox_post.sh", "--from", name, text], check=False)
PY
exit 0
