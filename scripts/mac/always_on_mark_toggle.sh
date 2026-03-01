#!/bin/bash
set -euo pipefail

RUNTIME_DIR="/Users/remi/voice2clipboard/runtime/always_on"
MARKER_FILE="$RUNTIME_DIR/selection_marker.json"
START_SH="/Users/remi/voice2clipboard/scripts/mac/always_on_mark_start.sh"
STOP_SH="/Users/remi/voice2clipboard/scripts/mac/always_on_mark_stop.sh"
TOGGLE_LOG="$RUNTIME_DIR/toggle.log"
LOCK_FILE="$RUNTIME_DIR/toggle.last"
MIN_STOP_AGE_S="${VOICE2CLIP_MIN_STOP_AGE_S:-1.2}"

mkdir -p "$RUNTIME_DIR"

ts="$(date +%Y-%m-%dT%H:%M:%S)"

# Guard against duplicate hotkey delivery (same keypress handled twice).
now_s="$(python3 -c 'import time; print(time.time())')"
if [[ -f "$LOCK_FILE" ]]; then
  prev_s="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  if [[ -n "$prev_s" ]]; then
    ignore="$(python3 - "$prev_s" "$now_s" <<'PY'
import sys
prev_t = float(sys.argv[1])
now_t = float(sys.argv[2])
print("1" if (now_t - prev_t) < 1.0 else "0")
PY
)"
    if [[ "$ignore" == "1" ]]; then
      echo "[$ts] action=ignored reason=debounce" >>"$TOGGLE_LOG"
      exit 0
    fi
  fi
fi
echo "$now_s" >"$LOCK_FILE"

if [[ -f "$MARKER_FILE" ]]; then
  # If marker is extremely recent, treat this as a duplicate delivery, not a real "stop".
  marker_t="$(python3 - "$MARKER_FILE" <<'PY'
import json, sys
p = sys.argv[1]
try:
    d = json.load(open(p, "r", encoding="utf-8"))
    print(float(d.get("started_epoch", 0.0)))
except Exception:
    print(0.0)
PY
)"
  age_s="$(python3 - "$marker_t" "$now_s" <<'PY'
import sys
start_t = float(sys.argv[1]); now_t = float(sys.argv[2])
print(max(0.0, now_t - start_t))
PY
)"
  too_soon="$(python3 - "$age_s" "$MIN_STOP_AGE_S" <<'PY'
import sys
age = float(sys.argv[1]); min_age = float(sys.argv[2])
print("1" if age < min_age else "0")
PY
)"
  if [[ "$too_soon" == "1" ]]; then
    echo "[$ts] action=ignored reason=min_stop_age age_s=${age_s}" >>"$TOGGLE_LOG"
    # Very distinct ignore cue so we can tell this path apart from start/stop.
    afplay /System/Library/Sounds/Basso.aiff >/dev/null 2>&1 &
    exit 0
  fi
  echo "[$ts] action=stop marker=present" >>"$TOGGLE_LOG"
  set +e
  "$STOP_SH"
  rc=$?
  set -e
  echo "[$(date +%Y-%m-%dT%H:%M:%S)] action=stop rc=$rc" >>"$TOGGLE_LOG"
  exit $rc
else
  echo "[$ts] action=start marker=absent" >>"$TOGGLE_LOG"
  set +e
  "$START_SH"
  rc=$?
  set -e
  echo "[$(date +%Y-%m-%dT%H:%M:%S)] action=start rc=$rc" >>"$TOGGLE_LOG"
  exit $rc
fi
