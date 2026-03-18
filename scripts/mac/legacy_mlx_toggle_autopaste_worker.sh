#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
LOCK_FILE="/tmp/voice2clipboard_quick_autopaste.pid"
META_FILE="/tmp/voice2clipboard_quick_autopaste.meta"
LOG_FILE="/tmp/voice2clipboard_quick_autopaste.log"
STOP_FILE="/tmp/voice2clipboard_quick_autopaste.stop"
HELPER_CTL="${ROOT_DIR}/scripts/mac/mlx_whisper_helper_ctl.sh"

export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"

# Keep the worker terminal informative while still preserving a logfile.
exec > >(tee -a "$LOG_FILE") 2>&1

cleanup() {
  rm -f "$LOCK_FILE" "$META_FILE" "$STOP_FILE"
}
trap cleanup EXIT

if [[ ! -f "$META_FILE" ]]; then
  echo "Missing meta file: $META_FILE" >>"$LOG_FILE"
  exit 1
fi

source "$META_FILE"
source "$VENV"
cd "$ROOT_DIR"

helper_status_summary() {
  python3 - "$HELPER_CTL" <<'PY'
import json
import subprocess
import sys

ctl = sys.argv[1]
try:
    raw = subprocess.check_output([ctl, "status"], text=True)
    state = json.loads(raw)
except Exception:
    print("Model helper: status unavailable")
    raise SystemExit(0)

status = state.get("status", "unknown")
repo = state.get("model_repo", "unknown")
rss_mb = state.get("rss_mb")
load_s = state.get("model_load_seconds")

parts = [f"Model helper: {status}", f"repo={repo}"]
if rss_mb is not None:
    parts.append(f"rss≈{rss_mb} MB")
if load_s is not None:
    parts.append(f"load={load_s}s")
print(" | ".join(parts))
PY
}

ARGS=(--quick --target-window "${target_app:-}")
if [[ -n "${target_iterm_session:-}" ]]; then
  ARGS+=(--target-iterm-session "$target_iterm_session")
fi

echo "voice2clipboard MLX quick mode"
echo "Started: ${started_at:-unknown}"
echo "Target app: ${target_app:-unknown}"
if [[ -n "${target_iterm_session:-}" ]]; then
  echo "Target iTerm session: $target_iterm_session"
fi
echo "Helper launch state: ${helper_launch_state:-unknown}"
helper_status_summary
echo "Backend: mlx-whisper ${ARGS[*]}"
echo "Press the same shortcut again to stop recording."
echo

env \
  VOICE2CLIPBOARD_BACKEND=mlx \
  VOICE2CLIPBOARD_MLX_HELPER=1 \
  VOICE2CLIPBOARD_HELPER_LAUNCH_STATE="${helper_launch_state:-unknown}" \
  VOICE2CLIPBOARD_STOP_REQUEST_FILE="$STOP_FILE" \
  python apps/linux/legacy_whisper/voice_transcriber.py "${ARGS[@]}" &
CHILD_PID=$!
echo "$CHILD_PID" > "$LOCK_FILE"
stop_reinforced=0
while kill -0 "$CHILD_PID" >/dev/null 2>&1; do
  if [[ -f "$STOP_FILE" && "$stop_reinforced" -eq 0 ]]; then
    echo
    echo "External stop file detected; reinforcing stop signal..."
    kill -TERM "$CHILD_PID" >/dev/null 2>&1 || true
    stop_reinforced=1
  fi
  sleep 0.2
done
wait "$CHILD_PID"

echo
echo "Stopping MLX helper for this run..."
"$HELPER_CTL" stop >/dev/null 2>&1 || true
