#!/bin/bash
# Tests for the end of a spoken message: the player outlives its sound by over a second, and a
# press in that tail must start a dictation, not pause a message that is already over.
# No sound, no microphone: the player and the recorder launcher are stand-ins.
# Run: bash local_tests/test_message_tail.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$TMP"' EXIT
export SECRETARY_RUNTIME="$TMP/runtime" DICTATION_LOCK="$TMP/recorder.pid" SECRETARY_CUES_MUTED=1 SECRETARY_VOLUME_GUARD=0
mkdir -p "$SECRETARY_RUNTIME"
S="$ROOT/scripts/mac/secretary"
# a 2 s silent wav; a player that, like afplay, stays alive 1.5 s after the sound; a launcher that
# only records that it was called
python3 - "$TMP/two_seconds.wav" <<'PY'
import sys, wave
w = wave.open(sys.argv[1], "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
w.writeframes(b"\0\0" * 32000); w.close()
PY
printf '#!/bin/bash\nexec /bin/sleep 4.5\n' >"$TMP/player"; chmod +x "$TMP/player"
printf '#!/bin/bash\necho launched >>"%s"\n' "$TMP/launcher.calls" >"$TMP/launcher"; chmod +x "$TMP/launcher"
export SECRETARY_PLAYER="$TMP/player" SECRETARY_LAUNCHER="$TMP/launcher"
source "$S/lib.sh"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
speak() { bash "$S/say_now.sh" --wav "$TMP/two_seconds.wav" "test message" >/dev/null 2>&1 & /bin/sleep 0.6; }

# 1. in the middle of a message a single press pauses, and the pause does not run the clock
speak
bash "$S/on_gesture.sh" single
check "mid-message single press pauses" "grep -q 'tts paused' '$LOG_FILE' && [[ \"\$(cat '$TTS_STATE_FILE')\" == paused ]]"
/bin/sleep 1.2
check "a paused message keeps its remaining sound" "perl -e 'exit(\$ARGV[0] > 1.0 ? 0 : 1)' \"\$(tts_sound_left)\""
bash "$S/on_gesture.sh" single
check "second single press resumes" "grep -q 'tts resumed' '$LOG_FILE'"
check "no dictation was started so far" "[[ ! -f '$TMP/launcher.calls' ]]"

# 2. sound over, player still alive (the tail): the press starts a dictation
#    (since 2026-09-21 a resume replays 1 s and adds the 0.35 s lead-in: about 2.7 s of sound here)
/bin/sleep 3.2
check "player is still alive in the tail" "[[ -n \"\$(tts_pid)\" ]]"
bash "$S/on_gesture.sh" single
check "tail press is recognised" "grep -q 'message was over' '$LOG_FILE'"
check "tail press starts a dictation" "[[ -f '$TMP/launcher.calls' ]]"
check "tail press did not pause anything" "[[ \"\$(grep -c 'tts paused' '$LOG_FILE')\" == 1 ]]"
check "player was ended" "[[ -z \"\$(tts_pid)\" ]]"
rm -f "$DICTATION_PENDING" "$TMP/launcher.calls"; /bin/sleep 0.3

# 3. while the voice is being prepared a single press is refused aloud, not swallowed
/bin/sleep 30 & prep=$!; /bin/sleep 0.3
echo "$prep" >"$TTS_PID_FILE"; echo preparing >"$TTS_STATE_FILE"
bash "$S/on_gesture.sh" single
check "press during preparation is refused with a cue" "grep -q 'refused: single press while a message is being prepared' '$LOG_FILE'"
check "the renderer was not frozen" "[[ \"\$(ps -o stat= -p $prep | cut -c1)\" != T ]]"
kill "$prep" 2>/dev/null; rm -f "$TTS_PID_FILE" "$TTS_STATE_FILE"

# 4. an interrupted message must not erase the next one's pid and clock when it exits
speak; first="$(tts_pid)"
SAY_NOW_INTERRUPT=1 bash "$S/say_now.sh" --wav "$TMP/two_seconds.wav" "second message" >/dev/null 2>&1 &
/bin/sleep 1.0
check "second message is visible to the buttons" "[[ -n \"\$(tts_pid)\" && \"\$(tts_pid)\" != '$first' ]]"
check "second message has its clock" "[[ -s '$TTS_CLOCK_FILE' ]]"

echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
