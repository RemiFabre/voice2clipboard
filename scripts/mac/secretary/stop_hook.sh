#!/bin/bash
# Claude Code Stop hook: when voice mode is on, queue the session's final message for the earbuds.
# Reads the hook JSON on stdin. Uses the "Spoken:" paragraph when the agent wrote one, otherwise
# the first sentences of the message. Never blocks Claude (always exits 0).
source "$(dirname "$0")/lib.sh"
[[ -f "$VOICE_MODE_FLAG" ]] || exit 0
input="$(cat)"
python3 - "$input" "$ROOT_DIR" "$(dirname "$0")/inbox_post.sh" <<'PY'
import json, os, re, subprocess, sys
try:
    d = json.loads(sys.argv[1])
except Exception as e:
    print("stop_hook: bad json:", e, file=sys.stderr)
    sys.exit(0)
root, post = sys.argv[2], sys.argv[3]
cwd = d.get("cwd") or ""
if d.get("agent_id") or cwd.rstrip("/").endswith("/secretary"):
    sys.exit(0)  # subagents and the secretary itself stay silent
msg = (d.get("last_assistant_message") or "").strip()
if not msg:
    sys.exit(0)
m = re.search(r"(?ms)^\**Spoken:?\**\s*(.+?)(?:\n\s*\n|\Z)", msg)
if m:
    text = m.group(1).strip()
else:
    plain = re.sub(r"```.*?```", " ", msg, flags=re.S)
    plain = re.sub(r"[`*_#>|]", "", plain)
    plain = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    words = plain.split()
    text = " ".join(words[:70]) + (" ... more on screen." if len(words) > 70 else "")
name = os.path.basename(cwd.rstrip("/")) or "an agent"
name = name.replace("-", " ").replace("_", " ")
subprocess.run([post, "--from", name, text], check=False)
PY
exit 0
