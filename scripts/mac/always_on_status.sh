#!/bin/bash
set -euo pipefail
ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
RUNTIME_DIR="/Users/remi/voice2clipboard/runtime/always_on"
source "$VENV"
cd "$ROOT_DIR"
python tools/always_on_capture.py status --runtime-dir "$RUNTIME_DIR"
echo
echo "Audio diagnostics:"
python - <<'PY'
import json, os
try:
    import sounddevice as sd
    print(f"- default devices: {sd.default.device}")
    try:
        ins = [f"{i}:{d['name']}" for i,d in enumerate(sd.query_devices()) if d.get('max_input_channels',0)>0]
        print(f"- input devices found: {len(ins)}")
        if ins:
            print(f"- first inputs: {', '.join(ins[:3])}")
    except Exception as e:
        print(f"- input device query error: {e}")
except Exception as e:
    print(f"- sounddevice unavailable: {e}")
PY
echo
echo "Transcript diagnostics:"
python - <<'PY'
import json, os
runtime = "/Users/remi/voice2clipboard/runtime/always_on"
seg_path = os.path.join(runtime, "segments.jsonl")
last_ts = None
count = 0
if os.path.exists(seg_path):
    with open(seg_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                o = json.loads(line)
            except Exception:
                continue
            count += 1
            if o.get("ts"):
                last_ts = o["ts"]
print(f"- committed segments: {count}")
print(f"- last committed segment ts: {last_ts}")
PY
echo
echo "Recent timeline files:"
ls -lt "$RUNTIME_DIR"/timeline/*.txt 2>/dev/null | head -n 5 || echo "none"
