#!/bin/bash
# Pause and resume of a spoken message. The bug of 2026-09-21: a pause was SIGSTOP on afplay, and
# afplay keeps to the wall clock, so on SIGCONT it rushed through or dropped what "should" have
# played meanwhile. Now a pause ends the player and the rest is played from just before that point.
# No sound, no microphone: the player is a stand-in that records which file it was given and
# lives as long as that file lasts.
# Run: bash local_tests/test_pause_resume.sh      (TEST_SEC=<dir> tests a staged copy)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$TMP"' EXIT
export SECRETARY_RUNTIME="$TMP/runtime" DICTATION_LOCK="$TMP/recorder.pid" SECRETARY_CUES_MUTED=1 \
       SECRETARY_VOLUME_GUARD=0 SECRETARY_END_TONE=0
mkdir -p "$SECRETARY_RUNTIME"
S="${TEST_SEC:-$ROOT/scripts/mac/secretary}"
python3 - "$TMP/ten_seconds.wav" <<'PY'
import sys, wave
w = wave.open(sys.argv[1], "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
w.writeframes(b"\0\0" * 160000); w.close()
PY
cat >"$TMP/player" <<PLAYER
#!/bin/bash
d="\$(afinfo "\$1" | sed -nE 's/^estimated duration: ([0-9.]+) sec.*/\1/p')"
echo "\$(basename "\$1") \$d" >>"$TMP/player.calls"
exec /bin/sleep "\$d"
PLAYER
chmod +x "$TMP/player"
printf '#!/bin/bash\necho launched >>"%s"\n' "$TMP/launcher.calls" >"$TMP/launcher"; chmod +x "$TMP/launcher"
export SECRETARY_PLAYER="$TMP/player" SECRETARY_LAUNCHER="$TMP/launcher"
source "$S/lib.sh"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
wait_for() { local n=0; until eval "$1"; do n=$((n + 1)); [[ $n -gt $(( $2 * 10 )) ]] && return 1; /bin/sleep 0.1; done; }
speak() { bash "$S/say_now.sh" --wav "$TMP/ten_seconds.wav" "test message" >/dev/null 2>&1 & owner=$!; wait_for "[[ \"\$(cat '$TTS_STATE_FILE' 2>/dev/null)\" == playing ]]" 5; }

# 1. pause after about 3 s: the player is ended (not frozen), the message lives on in its owner
speak; /bin/sleep 3
first_player="$(cat "$TTS_PID_FILE")"
bash "$S/on_gesture.sh" single; /bin/sleep 0.3
check "pause is logged and the state says paused" "grep -q 'tts paused\$' '$LOG_FILE' && [[ \"\$(cat '$TTS_STATE_FILE')\" == paused ]]"
check "the player was ended, not frozen" "! kill -0 $first_player 2>/dev/null"
check "the message is still there for the buttons" "[[ -n \"\$(tts_pid)\" && \"\$(tts_pid)\" == \"\$(cat '$TTS_OWNER_FILE')\" ]]"
left_at_pause="$(tts_sound_left)"
/bin/sleep 2
check "the clock does not run during the pause" "[[ \"\$(tts_sound_left)\" == '$left_at_pause' ]]"
check "about 7 s were left" "perl -e 'exit((\$ARGV[0] > 6.2 && \$ARGV[0] < 7.4) ? 0 : 1)' '$left_at_pause'"

# 2. resume: a new player gets the rest, starting 1 s before the pause, after a 0.35 s lead-in
bash "$S/on_gesture.sh" single
check "resume starts a second player" "wait_for \"[[ \\\$(wc -l <'$TMP/player.calls') -eq 2 ]]\" 3"
rest="$(sed -n 2p "$TMP/player.calls" | cut -d' ' -f2)"
check "it plays the rest of the message, not the whole" "grep -q 'rest.wav' <<<\"\$(sed -n 2p '$TMP/player.calls')\""
check "nothing is skipped: rest = what was left + 1 s rewind + lead-in" "perl -e 'my \$want = \$ARGV[1] + 1.0 + 0.35; exit(abs(\$ARGV[0] - \$want) < 0.15 ? 0 : 1)' '$rest' '$left_at_pause'"
check "state is playing again with a running clock" "[[ \"\$(cat '$TTS_STATE_FILE')\" == playing ]] && perl -e 'exit(\$ARGV[0] > 5 ? 0 : 1)' \"\$(tts_sound_left)\""

# 3. a second pause and resume in the same message works too
/bin/sleep 2; bash "$S/on_gesture.sh" single; /bin/sleep 0.3
left2="$(tts_sound_left)"
bash "$S/on_gesture.sh" single
check "second resume starts a third player" "wait_for \"[[ \\\$(wc -l <'$TMP/player.calls') -eq 3 ]]\" 3"
check "second resume also rewinds instead of skipping" "perl -e 'my \$want = \$ARGV[1] + 1.0 + 0.35; exit(abs(\$ARGV[0] - \$want) < 0.2 ? 0 : 1)' \"\$(sed -n 3p '$TMP/player.calls' | cut -d' ' -f2)\" '$left2'"

# 4. discard while paused: everything goes, including the owner
bash "$S/on_gesture.sh" single; /bin/sleep 0.3
bash "$S/on_gesture.sh" double; /bin/sleep 0.5
check "discard while paused ends the owner" "! kill -0 $owner 2>/dev/null"
check "no pause or state files are left" "[[ ! -f '$TTS_PAUSE_FILE' && ! -f '$TTS_STATE_FILE' && ! -f '$TTS_PID_FILE' && -z \"\$(tts_pid)\" ]]"
check "the speech lock is free" "[[ -z \"\$(speech_lock_owner)\" ]]"

# 5. a message that plays to its end cleans up after itself
: >"$TMP/player.calls"
python3 - "$TMP/one_second.wav" <<'PY'
import sys, wave
w = wave.open(sys.argv[1], "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
w.writeframes(b"\0\0" * 16000); w.close()
PY
bash "$S/say_now.sh" --wav "$TMP/one_second.wav" "short" >/dev/null 2>&1
check "natural end: no owner, pause or rest files left" "[[ ! -f '$TTS_OWNER_FILE' && ! -f '$TTS_PAUSE_FILE' && ! -f '$TTS_WAV.rest.wav' && ! -f '$TTS_PID_FILE' ]]"

# 6. a message started by an older say_now (no owner file) is still paused the old way
/bin/sleep 30 & old=$!; echo "$old" >"$TTS_PID_FILE"; echo playing >"$TTS_STATE_FILE"; tts_clock_start 20
tts_pause "$old"
check "no owner: falls back to stopping the player" "grep -q 'stopped player' '$LOG_FILE' && [[ \"\$(ps -o stat= -p $old | cut -c1)\" == T ]]"
tts_resume "$old"
check "no owner: resume continues it" "[[ \"\$(ps -o stat= -p $old | cut -c1)\" != T ]]"
kill "$old" 2>/dev/null

check "no dictation was ever started" "[[ ! -f '$TMP/launcher.calls' ]]"
echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
