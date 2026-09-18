#!/bin/bash
# Claude Code Stop hook. Records the session's latest message in the attention ledger (always,
# silently). Notifications are no longer automatic: a flagged turn (question, decision, blocked,
# "Notify:" marker, possible problem) is handed to the secretary session, which decides whether
# Remi hears it in the agent's voice. Per-project overrides: secretary/notify_overrides.json.
# The secretary's own turns trigger the context-rotation check instead. Never blocks (exit 0).
source "$(dirname "$0")/lib.sh"
input="$(cat)"
python3 - "$input" "$(dirname "$0")" <<'PY'
import json, os, subprocess, sys
sys.path.insert(0, sys.argv[2])
import ledger_lib as L
try:
    d = json.loads(sys.argv[1])
except Exception as e:
    print("stop_hook: bad json:", e, file=sys.stderr); sys.exit(0)
scripts = sys.argv[2]
cwd = d.get("cwd") or ""
if d.get("agent_id"):
    sys.exit(0)
if cwd.rstrip("/").endswith("/secretary"):
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
        subprocess.run([scripts + "/inbox_post.sh", "--from", "secretary", "I am restarting with a fresh context; I keep the ledger and my notes."], check=False)
        subprocess.Popen(["nohup", scripts + "/start_secretary.sh", "--rotate"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sys.exit(0)
msg = (d.get("last_assistant_message") or "").strip()
if not msg:
    sys.exit(0)
name = L.project_name(cwd)
text = L.spoken_text(msg)
reason = L.classify(msg)
session_id = d.get("session_id", "unknown")
L.write(session_id, project=name, cwd=cwd, summary=text, needs_attention=(reason == "waiting on Remi"),
        reason=reason, state="finished a turn")
policy = L.policy_for(name)
if policy == "never":
    sys.exit(0)
if policy == "always":
    subprocess.run([scripts + "/inbox_post.sh", "--from", name, text], check=False)
    sys.exit(0)
if reason:
    delivered = L.forward_to_secretary(scripts, name, session_id, reason, text)
    if not delivered and reason == "waiting on Remi":
        # no secretary to decide: a session waiting on Remi must not go unheard
        subprocess.run([scripts + "/inbox_post.sh", "--from", name, text], check=False)
PY
exit 0
