#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
# The VOICE2CLIPBOARD_* and SECRETARY_RUNTIME overrides exist for local_tests/test_window_closed_delivery.sh,
# which runs this script against stand-ins; the launcher and the real recorder never set them.
VENV="${VOICE2CLIPBOARD_VENV:-/Users/remi/.virtualenvs/voice2clipboard/bin/activate}"
STATE="${VOICE2CLIPBOARD_STATE_PREFIX:-/tmp/voice2clipboard_quick_autopaste}"
LOCK_FILE="$STATE.pid"
META_FILE="$STATE.meta"
LOG_FILE="$STATE.log"
STOP_FILE="$STATE.stop"
AUDIO_STATE_FILE="$STATE.audio"
PHASE_FILE="$STATE.phase"
PRESS_FILE="$STATE.press"
HELPER_CTL="${VOICE2CLIPBOARD_HELPER_CTL:-${ROOT_DIR}/scripts/mac/mlx_whisper_helper_ctl.sh}"
RECOVER="${VOICE2CLIPBOARD_RECOVER_SCRIPT:-${ROOT_DIR}/scripts/mac/recover_orphaned_recording.sh}"
INBOX_POST="${VOICE2CLIPBOARD_INBOX_POST:-${ROOT_DIR}/scripts/mac/secretary/inbox_post.sh}"
# Press-to-lock marker of the secretary layer (scripts/mac/secretary/lib.sh). This worker owns the
# dictation state: the marker goes as soon as the lock exists, and both go when the worker exits,
# however it exits, so a dead recorder can never leave the earbuds looking busy.
SECRETARY_RUNTIME="${SECRETARY_RUNTIME:-${ROOT_DIR}/runtime/secretary}"
DICTATION_PENDING="$SECRETARY_RUNTIME/dictation_pending"
SECRETARY_LOG="$SECRETARY_RUNTIME/secretary.log"
MAX_LOG_SIZE_BYTES=$((5 * 1024 * 1024))

export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"

if [[ -f "$LOG_FILE" ]]; then
  log_size="$(wc -c <"$LOG_FILE" 2>/dev/null || echo 0)"
  if [[ "${log_size:-0}" -gt "$MAX_LOG_SIZE_BYTES" ]]; then
    tail -c "$MAX_LOG_SIZE_BYTES" "$LOG_FILE" > "${LOG_FILE}.tmp" 2>/dev/null || true
    mv "${LOG_FILE}.tmp" "$LOG_FILE" 2>/dev/null || true
  fi
fi

# Name the window (title escape, before the log tee so the bytes stay out of the log), and say what
# closing it does: Remi uses the close button as a cancel (2026-09-24).
[[ -t 1 ]] && printf '\033]0;🎤 Dictation running: closing this window cancels it (audio kept)\007'
# Keep the worker terminal informative while still preserving a logfile.
exec > >(tee -a "$LOG_FILE") 2>&1

# The recorder window closed while recording: that is a cancel, by Remi's decision (2026-09-24
# 09:42: he uses the close button as a cancel from time to time; keeping the audio is fine, the
# text must not reach the secretary). iTerm sends HUP to the whole process group five seconds
# after the click (its "undo close" grace): the recorder, which does not handle HUP, dies of it;
# this script survives thanks to the trap, its window is gone, so its output goes to the log file
# from here on. Nothing is delivered and no note is queued: the cancel cue plays, the audio stays
# on disk with the `cancelled` marker, and recover_cancelled.sh can bring it back (it transcribes
# on demand). The orphan recovery below is skipped: a cancel is not a crash.
window_closed=0
on_window_closed() {
  window_closed=1
  exec >>"$LOG_FILE" 2>&1
  echo
  echo "$(date '+%Y-%m-%d %H:%M:%S') recorder window closed while recording: cancelled, audio kept"
  [[ -n "${CHILD_PID:-}" ]] && kill -KILL "$CHILD_PID" >/dev/null 2>&1 || true
}
cleanup() {
  rm -f "$DICTATION_PENDING"
  if [[ "$window_closed" == 1 ]]; then
    [[ -n "${CHILD_PID:-}" ]] && kill -KILL "$CHILD_PID" >/dev/null 2>&1 || true
    cancelled_audio="$(cat "$AUDIO_STATE_FILE" 2>/dev/null || true)"
    if [[ -n "$cancelled_audio" && -f "$cancelled_audio" ]]; then
      echo "recorder window closed $(date)" >"$(dirname "$cancelled_audio")/cancelled"
      afplay "$ROOT_DIR/sounds/cue_cancel.aiff" >/dev/null 2>&1 || true
    fi
    printf '%s recorder window closed: dictation cancelled, audio kept in %s (recover_cancelled.sh)\n' "$(date '+%Y-%m-%d %H:%M:%S')" \
      "$(dirname "${cancelled_audio:-unknown/x}")" >>"$SECRETARY_LOG" 2>/dev/null || true
  fi
  # The recorder's headset-button watcher is a `log stream` child; make sure none outlives us
  # (a SIGKILLed recorder cannot reap it). Not from the test suite: it would hit a real recorder's.
  [[ -n "${VOICE2CLIPBOARD_TEST_NO_PKILL:-}" ]] || pkill -f '^/usr/bin/log stream --style compact --info --debug --predicate process == "bluetoothd"' >/dev/null 2>&1 || true
  local current_pid=""
  current_pid="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  if [[ -n "${CHILD_PID:-}" && "$current_pid" == "$CHILD_PID" ]]; then
    rm -f "$LOCK_FILE"
  fi

  local meta_session=""
  meta_session="$(sed -n 's/^session_id=//p' "$META_FILE" 2>/dev/null | tail -n 1)"
  if [[ -n "${session_id:-}" && "$meta_session" == "$session_id" ]]; then
    rm -f "$META_FILE" "$STOP_FILE" "$AUDIO_STATE_FILE" "$PHASE_FILE" "$PRESS_FILE"
  fi
}
trap cleanup EXIT
trap on_window_closed HUP

if [[ ! -f "$META_FILE" ]]; then
  echo "Missing meta file: $META_FILE" >>"$LOG_FILE"
  exit 1
fi

source "$META_FILE"
source "$VENV"
cd "$ROOT_DIR"

helper_status_summary() {
  # Plain shell on purpose: spawning python3 here delays the recorder start.
  local state_file="${VOICE2CLIPBOARD_MLX_HELPER_STATE:-/tmp/voice2clipboard_mlx_helper_state.json}"
  if [[ ! -f "$state_file" ]]; then
    echo "Model helper: status unavailable"
    return 0
  fi
  local status repo
  status="$(sed -n 's/.*"status": *"\([^"]*\)".*/\1/p' "$state_file" | head -n 1)"
  repo="$(sed -n 's/.*"model_repo": *"\([^"]*\)".*/\1/p' "$state_file" | head -n 1)"
  echo "Model helper: ${status:-unknown} | repo=${repo:-unknown}"
}

ARGS=(--quick --target-window "${target_app:-}")
if [[ -n "${target_iterm_session:-}" ]]; then
  ARGS+=(--target-iterm-session "$target_iterm_session")
fi
if [[ "${copy_only:-0}" == "1" ]]; then
  ARGS+=(--copy-only)   # the target window is known to be gone: keep the text, deliver nothing
fi

echo "voice2clipboard MLX quick mode"
echo "Started: ${started_at:-unknown}"
echo "Target app: ${target_app:-unknown}"
if [[ -n "${target_iterm_session:-}" ]]; then
  echo "Target iTerm session: $target_iterm_session"
fi
echo "Helper launch state: ${helper_launch_state:-unknown}"
if [[ "${voice_mode:-manual}" == "headset" ]]; then
  echo "Mode: HEADSET — text goes to the secretary, agents notify you with a ding"
else
  echo "Mode: MANUAL — quiet, no notifications (an earbud dictation switches back)"
fi
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
  VOICE2CLIPBOARD_PHASE_FILE="$PHASE_FILE" \
  VOICE2CLIPBOARD_VOICE_MODE="${voice_mode:-manual}" \
  VOICE2CLIPBOARD_PRESS_FILE="$PRESS_FILE" \
  python apps/linux/legacy_whisper/voice_transcriber.py "${ARGS[@]}" &
CHILD_PID=$!
echo "$CHILD_PID" > "$LOCK_FILE"
rm -f "$DICTATION_PENDING"   # the lock is the truth from here on
forced_recovery=0
stop_seen_at=0
while kill -0 "$CHILD_PID" >/dev/null 2>&1; do
  if [[ -f "$STOP_FILE" ]]; then
    phase="$(cat "$PHASE_FILE" 2>/dev/null || echo recording)"
    if [[ "$stop_seen_at" -eq 0 ]]; then
      stop_seen_at="$(date +%s)"
      echo
      echo "Stop requested; monitoring recorder shutdown..."
    fi
    if [[ "$phase" == "transcribing" || "$phase" == "done" ]]; then
      sleep 0.2 || true
      continue
    fi
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
          VOICE2CLIPBOARD_HELPER_LAUNCH_STATE="${helper_launch_state:-unknown}" \
          VOICE2CLIPBOARD_STOP_REQUEST_FILE="$STOP_FILE" \
          VOICE2CLIPBOARD_AUDIO_STATE_FILE="$AUDIO_STATE_FILE" \
          VOICE2CLIPBOARD_PHASE_FILE="$PHASE_FILE" \
          python apps/linux/legacy_whisper/voice_transcriber.py "${ARGS[@]}" "$snapshot"
      else
        echo "No snapshot audio was available for recovery."
      fi
      break
    fi
  fi
  sleep 0.2 || true   # ended by the HUP of a closed window: not an error
done
if [[ "$forced_recovery" -eq 0 ]]; then
  # `wait` returns the recorder's status; under `set -e` a crashed recorder used to end this
  # script right here, so the recovery below never ran (2026-09-19).
  child_status=0
  wait "$CHILD_PID" || child_status=$?
  # Orphaned audio: the recorder ended without producing a transcript (crash, killed, device
  # gone). Never lose a dictation silently: signal it and transcribe what was captured.
  audio_path="$(cat "$AUDIO_STATE_FILE" 2>/dev/null || true)"
  if [[ "$window_closed" == 0 && -n "$audio_path" && -f "$audio_path" && ! -f "$(dirname "$audio_path")/stats.json" ]]; then
    echo
    echo "⚠️ The recorder ended (status $child_status) without a transcript; recovering $audio_path"
    afplay "$ROOT_DIR/sounds/cue_fail.aiff" >/dev/null 2>&1 &
    VOICE2CLIPBOARD_BACKEND=mlx VOICE2CLIPBOARD_HELPER_LAUNCH_STATE="${helper_launch_state:-unknown}" \
      "$RECOVER" "$audio_path" "${ARGS[@]}" \
      || "$INBOX_POST" --from secretary "A dictation was lost. Its audio is saved under recordings, and it could not be transcribed." >/dev/null 2>&1 || true
  fi
fi

echo
echo "Stopping MLX helper for this run..."
"$HELPER_CTL" stop >/dev/null 2>&1 || true
