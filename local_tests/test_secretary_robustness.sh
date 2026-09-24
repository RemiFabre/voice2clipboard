#!/bin/bash
# Robustness tests for the secretary layer's dictation state (no audio, no iTerm, no real runtime).
# Run: bash local_tests/test_secretary_robustness.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
export SECRETARY_RUNTIME="$TMP/runtime" DICTATION_LOCK="$TMP/recorder.pid" SECRETARY_CUES_MUTED=1
mkdir -p "$SECRETARY_RUNTIME"
source "$ROOT/scripts/mac/secretary/lib.sh"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
age_file() { touch -t "$(date -v-"$2"S '+%Y%m%d%H%M.%S')" "$1"; }

# 1. a fresh pending marker counts as an active dictation (press -> recorder start window)
touch "$DICTATION_PENDING"
check "fresh pending marker is active" "dictation_active"
check "fresh pending marker is pending-only" "dictation_pending_only"

# 2. the incident: recorder killed 12 s after the press, marker still there -> must NOT be active
age_file "$DICTATION_PENDING" 12
check "12 s old marker with no recorder is not active" "! dictation_active"
check "stale marker was removed" "[[ ! -f '$DICTATION_PENDING' ]]"

# 3. a live recorder is active whatever the marker says; a dead pid is not
sleep 30 & live=$!
echo "$live" >"$DICTATION_LOCK"
check "live recorder pid is active" "dictation_active"
check "live recorder is not pending-only" "! dictation_pending_only"
kill "$live" 2>/dev/null; wait "$live" 2>/dev/null
check "dead recorder pid is not active" "! dictation_active"

# 4. the iTerm unique id is the part after the colon of ITERM_SESSION_ID
check "iterm id parsed from env" "[[ \"\$(ITERM_SESSION_ID='w5t0p0:381A5D1E-61CC' iterm_unique_id_from_env)\" == '381A5D1E-61CC' ]]"
check "iterm id empty without env" "[[ -z \"\$(ITERM_SESSION_ID='' iterm_unique_id_from_env)\" ]]"

# 5. a refused press is never silent: refuse_cue logs the reason
refuse_cue "test reason"
check "refuse_cue logs the refusal" "grep -q 'refused: test reason' '$LOG_FILE'"

# 5b. a ding never sounds into a running dictation (2026-09-23): it waits for the recording to end
sleep 30 & live=$!; echo "$live" >"$DICTATION_LOCK"; : >"$LOG_FILE"; rm -f "$DING_STAMP"
bash "$ROOT/scripts/mac/secretary/ding.sh"
check "ding during a dictation is held" "grep -q 'ding held' '$LOG_FILE' && ! grep -q '^.* ding$' '$LOG_FILE'"
kill "$live" 2>/dev/null; wait "$live" 2>/dev/null; rm -f "$DICTATION_LOCK"
for _ in $(seq 1 60); do grep -q '^.* ding$' "$LOG_FILE" && break; /bin/sleep 0.1; done
check "the held ding plays once the dictation is over" "grep -q '^.* ding$' '$LOG_FILE'"

# 6. headset name filter
check "Shokz matches the headset pattern" "is_headset_name 'OpenFit 2+ by Shokz'"
check "a keyboard does not match" "! is_headset_name 'Magic Keyboard'"

# 7. verified cue player: a stream stopped after one buffer means the cue was never heard
CUE="$ROOT/scripts/mac/secretary/play_cue_verified.sh"
cat >"$TMP/stalled.log" <<'LOG'
12:00:00.100 coreaudiod [BTAudio] BluetoothHALPlugIn_register clientID=501 for <private> (PID=4242, )
12:00:00.120 coreaudiod [BTAudio] BluetoothHALPlugIn_StartIO: triggered by clientID=501 for <private> (PID=4242, )
12:00:00.130 coreaudiod [BTAudio] BluetoothHALPlugIn_register clientID=777 for <private> (PID=5555, )
12:00:01.000 coreaudiod (CoreAudio) IO Stopped Context 777 after 30080 frames.
12:00:02.000 coreaudiod (CoreAudio) IO Stopped Context 501 after 320 frames.
LOG
sed 's/Context 501 after 320 frames/Context 501 after 32960 frames/' "$TMP/stalled.log" >"$TMP/played.log"
check "one-buffer stream is a stalled cue" "[[ \"\$(bash '$CUE' --analyze 4242 '$TMP/stalled.log')\" == stalled ]]"
check "full-length stream is a played cue" "[[ \"\$(bash '$CUE' --analyze 4242 '$TMP/played.log')\" == played ]]"
check "other process's stream is not ours" "[[ \"\$(bash '$CUE' --analyze 5555 '$TMP/stalled.log')\" == played ]]"
check "no trace of our player is unknown" "[[ \"\$(bash '$CUE' --analyze 1 '$TMP/stalled.log')\" == unknown ]]"

echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
