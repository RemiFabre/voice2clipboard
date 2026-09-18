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
if d.get("agent_id"):
    sys.exit(0)
if cwd.rstrip("/").endswith("/secretary"):
    # The secretary itself: no ledger entry, but rotate it when its context grows too large.
    import os
    limit = int(os.getenv("SECRETARY_ROTATE_TOKENS", "700000"))
    used = 0
    try:
        with open(d.get("transcript_path", "")) as f:
            for line in f:
                if '"type":"assistant"' not in line:
                    continue
                try:
                    u = json.loads(line)["message"].get("usage", {})
                except Exception:
                    continue
                used = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
    except Exception:
        used = 0
    if used >= limit:
        subprocess.run([sys.argv[2] + "/inbox_post.sh", "--from", "secretary", "I am restarting with a fresh context; I keep the ledger and my notes."], check=False)
        subprocess.Popen(["nohup", sys.argv[2] + "/start_secretary.sh", "--rotate"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
