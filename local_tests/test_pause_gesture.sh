#!/bin/bash
# The "pause" gesture of the button app that rests in paused (2026-09-21): Play is a press; Pause is
# a press only while something plays or records, or right after a message; otherwise it is the
# headset going into its charger, and no dictation may start.
# Stand-in player and launcher, temp runtime: no sound, no microphone.
# Run: bash local_tests/test_pause_gesture.sh      (TEST_OVERLAY=<dir> tests undeployed copies)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$TMP"' EXIT
STAGE="$TMP/stage"; mkdir -p "$STAGE"
cp "$ROOT"/scripts/mac/secretary/*.sh "$ROOT"/scripts/mac/secretary/*.py "$STAGE/"
[[ -n "${TEST_OVERLAY:-}" ]] && cp "$TEST_OVERLAY"/*.sh "$STAGE/"
python3 - "$TMP/six_seconds.wav" <<'PY'
import sys, wave
w = wave.open(sys.argv[1], "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
w.writeframes(b"\0\0" * 96000); w.close()
PY
printf '#!/bin/bash\nexec /bin/sleep 6\n' >"$TMP/player"
printf '#!/bin/bash\necho launched >>"%s/launcher.calls"\n' "$TMP" >"$TMP/launcher"
chmod +x "$TMP/player" "$TMP/launcher"
export SECRETARY_RUNTIME="$TMP/runtime" DICTATION_LOCK="$TMP/recorder.pid" SECRETARY_CUES_MUTED=1 SECRETARY_VOLUME_GUARD=0 \
       SECRETARY_END_TONE=0 SECRETARY_PLAYER="$TMP/player" SECRETARY_LAUNCHER="$TMP/launcher" SECRETARY_LAZY_ROTATION=0
mkdir -p "$SECRETARY_RUNTIME"
source "$STAGE/lib.sh"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
launched() { [[ -f "$TMP/launcher.calls" ]]; }

# 1. the charger: a pause while nothing plays or records starts nothing
bash "$STAGE/on_gesture.sh" pause
check "idle pause: no dictation" "! launched"
check "idle pause: refused aloud, reason logged" "grep -q 'refused: pause while nothing plays or records' '$LOG_FILE'"

# 2. a real press arrives as play -> single: a dictation starts
bash "$STAGE/on_gesture.sh" single
check "play (single): dictation starts" "launched"
rm -f "$TMP/launcher.calls" "$DICTATION_PENDING"

# 3. during a message a pause is an ordinary press: it pauses the message
bash "$STAGE/say_now.sh" --wav "$TMP/six_seconds.wav" "test message" >/dev/null 2>&1 &
for _ in $(seq 1 40); do [[ "$(cat "$TTS_STATE_FILE" 2>/dev/null)" == playing ]] && break; /bin/sleep 0.1; done
bash "$STAGE/on_gesture.sh" pause; /bin/sleep 0.3
check "pause during a message pauses it" "[[ \"\$(cat '$TTS_STATE_FILE' 2>/dev/null)\" == paused ]] && ! launched"
bash "$STAGE/on_gesture.sh" single; /bin/sleep 0.5
check "the next press (play) resumes it" "[[ \"\$(cat '$TTS_STATE_FILE' 2>/dev/null)\" == playing ]]"
bash "$STAGE/on_gesture.sh" double; /bin/sleep 0.5; wait 2>/dev/null

# 4. right after a message the headset still believes "playing": a pause is a press
: >"$TTS_ENDED_FILE"
bash "$STAGE/on_gesture.sh" pause
check "pause 0 s after a message: taken as a press, dictation starts" "launched && grep -q 'taken as a press' '$LOG_FILE'"
rm -f "$TMP/launcher.calls" "$DICTATION_PENDING"
touch -t "$(date -v-20S '+%Y%m%d%H%M.%S')" "$TTS_ENDED_FILE"
bash "$STAGE/on_gesture.sh" pause
check "pause 20 s after a message: the charger again, nothing starts" "! launched"

# 5. while a recorder runs, a pause is handed to it like any press
/bin/sleep 30 & rec=$!; echo "$rec" >"$DICTATION_LOCK"
bash "$STAGE/on_gesture.sh" pause
check "pause during a dictation is handed to the recorder" "grep -q 'press handed to the recorder: single' '$LOG_FILE'"
kill "$rec" 2>/dev/null

echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
