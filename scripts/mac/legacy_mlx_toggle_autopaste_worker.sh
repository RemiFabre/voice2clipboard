#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
LOCK_FILE="/tmp/voice2clipboard_quick_autopaste.pid"
META_FILE="/tmp/voice2clipboard_quick_autopaste.meta"
LOG_FILE="/tmp/voice2clipboard_quick_autopaste.log"
STOP_FILE="/tmp/voice2clipboard_quick_autopaste.stop"
AUDIO_STATE_FILE="/tmp/voice2clipboard_quick_autopaste.audio"
HELPER_CTL="${ROOT_DIR}/scripts/mac/mlx_whisper_helper_ctl.sh"
MAX_LOG_SIZE_BYTES=$((5 * 1024 * 1024))

export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"

if [[ -f "$LOG_FILE" ]]; then
  log_size="$(wc -c <"$LOG_FILE" 2>/dev/null || echo 0)"
  if [[ "${log_size:-0}" -gt "$MAX_LOG_SIZE_BYTES" ]]; then
    tail -c "$MAX_LOG_SIZE_BYTES" "$LOG_FILE" > "${LOG_FILE}.tmp" 2>/dev/null || true
    mv "${LOG_FILE}.tmp" "$LOG_FILE" 2>/dev/null || true
  fi
fi

# Keep the worker terminal informative while still preserving a logfile.
exec > >(tee -a "$LOG_FILE") 2>&1

cleanup() {
  local current_pid=""
  current_pid="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  if [[ -n "${CHILD_PID:-}" && "$current_pid" == "$CHILD_PID" ]]; then
    rm -f "$LOCK_FILE"
  fi

  local meta_session=""
  meta_session="$(sed -n 's/^session_id=//p' "$META_FILE" 2>/dev/null | tail -n 1)"
  if [[ -n "${session_id:-}" && "$meta_session" == "$session_id" ]]; then
    rm -f "$META_FILE" "$STOP_FILE" "$AUDIO_STATE_FILE"
  fi
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
  VOICE2CLIPBOARD_AUDIO_STATE_FILE="$AUDIO_STATE_FILE" \
  python apps/linux/legacy_whisper/voice_transcriber.py "${ARGS[@]}" &
CHILD_PID=$!
echo "$CHILD_PID" > "$LOCK_FILE"
stop_reinforced=0
forced_recovery=0
stop_seen_at=0
while kill -0 "$CHILD_PID" >/dev/null 2>&1; do
  if [[ -f "$STOP_FILE" && "$stop_reinforced" -eq 0 ]]; then
    echo
    echo "External stop file detected; reinforcing stop signal..."
    kill -TERM "$CHILD_PID" >/dev/null 2>&1 || true
    stop_reinforced=1
    stop_seen_at="$(date +%s)"
  elif [[ -f "$STOP_FILE" && "$stop_reinforced" -eq 1 ]]; then
    now="$(date +%s)"
    if (( now - stop_seen_at >= 2 )); then
      audio_path="$(cat "$AUDIO_STATE_FILE" 2>/dev/null || true)"
      snapshot=""
      if [[ -n "$audio_path" && -f "$audio_path" ]]; then
        snapshot="$(mktemp /tmp/voice2clipboard_recover_XXXXXX)"
        snapshot="${snapshot}.wav"
        cp "$audio_path" "$snapshot"
      fi
      echo
      echo "Recorder still alive after stop request; forcing recovery..."
      kill -KILL "$CHILD_PID" >/dev/null 2>&1 || true
      wait "$CHILD_PID" >/dev/null 2>&1 || true
      forced_recovery=1
      if [[ -n "$snapshot" && -s "$snapshot" ]]; then
        echo "Recovering transcription from snapshot: $snapshot"
        env \
          VOICE2CLIPBOARD_BACKEND=mlx \
          VOICE2CLIPBOARD_MLX_HELPER=1 \
          VOICE2CLIPBOARD_HELPER_LAUNCH_STATE="${helper_launch_state:-unknown}" \
          VOICE2CLIPBOARD_STOP_REQUEST_FILE="$STOP_FILE" \
          VOICE2CLIPBOARD_AUDIO_STATE_FILE="$AUDIO_STATE_FILE" \
          python apps/linux/legacy_whisper/voice_transcriber.py "${ARGS[@]}" "$snapshot"
      else
        echo "No snapshot audio was available for recovery."
      fi
      break
    fi
  fi
  sleep 0.2
done
if [[ "$forced_recovery" -eq 0 ]]; then
  wait "$CHILD_PID"
fi

echo
echo "Stopping MLX helper for this run..."
"$HELPER_CTL" stop >/dev/null 2>&1 || true
