#!/bin/bash
set -euo pipefail
ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
RUNTIME_DIR="/Users/remi/voice2clipboard/runtime/always_on"
LATENCY_LOG="$RUNTIME_DIR/feedback_latency.jsonl"
source "$VENV"
cd "$ROOT_DIR"
t0="$(python3 -c 'import time; print(time.time())')"
set +e
python tools/always_on_capture.py stop --runtime-dir "$RUNTIME_DIR"
RC=$?
set -e
t1="$(python3 -c 'import time; print(time.time())')"
# Fast non-blocking cue (distinct stop sound)
afplay /System/Library/Sounds/Glass.aiff >/dev/null 2>&1 &
t2="$(python3 -c 'import time; print(time.time())')"
if [[ "$RC" -eq 0 ]]; then
  if [[ "${VOICE2CLIP_NOTIFY:-1}" == "1" ]]; then
    osascript -e 'display notification "Selection copied to clipboard" with title "voice2clipboard"' >/dev/null 2>&1 &
  fi
else
  if [[ "${VOICE2CLIP_NOTIFY:-1}" == "1" ]]; then
    osascript -e 'display notification "No selection copied" with title "voice2clipboard"' >/dev/null 2>&1 &
  fi
fi
t3="$(python3 -c 'import time; print(time.time())')"
python3 - "$LATENCY_LOG" "$t0" "$t1" "$t2" "$t3" "$RC" <<'PY'
import json, os, sys
path, t0, t1, t2, t3, rc = sys.argv[1:]
t0, t1, t2, t3 = map(float, (t0, t1, t2, t3))
row = {
    "action": "stop",
    "rc": int(rc),
    "start_to_selection_s": round(t1 - t0, 4),
    "selection_to_cue_launch_s": round(t2 - t1, 4),
    "post_cue_to_end_s": round(t3 - t2, 4),
    "total_script_s": round(t3 - t0, 4),
}
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "a", encoding="utf-8") as f:
    f.write(json.dumps(row) + "\n")
PY
exit "$RC"
