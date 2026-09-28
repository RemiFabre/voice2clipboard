#!/bin/bash
# Deferred speech is never lost (2026-09-28: an answer of the secretary deferred behind a playing
# message was never spoken and left no trace; its waiter was gone before it tried to speak).
# Stub voice, stand-in player, fake "playing" message, temp runtime: no sound, no microphone.
# Run: bash local_tests/test_deferred_speech.sh      (TEST_OVERLAY=<dir> tests undeployed copies)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
STAGE="$TMP/stage"; mkdir -p "$STAGE"
cp "$ROOT"/scripts/mac/secretary/*.sh "$ROOT"/scripts/mac/secretary/*.py "$STAGE/"
[[ -n "${TEST_OVERLAY:-}" ]] && cp "$TEST_OVERLAY"/*.sh "$STAGE/"
cat >"$TMP/say" <<'STUB'
#!/bin/bash
out=""; while [[ $# -gt 0 ]]; do case "$1" in --output) out="$2"; shift 2;; --voice|--lang) shift 2;; --no-play) shift;; *) shift;; esac; done
/bin/sleep "$(cat "$STUB_RENDER_S_FILE" 2>/dev/null || echo 0.2)"
python3 - "$out" <<'PY'
import sys, wave
w = wave.open(sys.argv[1], "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\0\0" * 24000); w.close()
PY
STUB
printf '#!/bin/bash\nexec /bin/sleep 1\n' >"$TMP/player"
chmod +x "$TMP/say" "$TMP/player"
export SECRETARY_RUNTIME="$TMP/runtime" DICTATION_LOCK="$TMP/recorder.pid" SECRETARY_CUES_MUTED=1 SECRETARY_VOLUME_GUARD=0 \
       SECRETARY_END_TONE=0 KOKORO_SAY="$TMP/say" KOKORO_CTL=/usr/bin/true FALLBACK_SAY="$TMP/say" \
       SECRETARY_PLAYER="$TMP/player" STUB_RENDER_S_FILE="$TMP/render_s"
mkdir -p "$SECRETARY_RUNTIME"
source "$STAGE/lib.sh"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
wait_for() { local n=0; until eval "$1"; do n=$((n + 1)); [[ $n -gt $(( $2 * 10 )) ]] && return 1; /bin/sleep 0.1; done; }
records() { ls "$DEFERRED_DIR"/*.txt 2>/dev/null | wc -l | tr -d ' '; }
record_pid() { basename "$(ls "$DEFERRED_DIR"/*.txt 2>/dev/null | head -n 1)" .txt; }
inbox_count() { grep -ls "$1" "$INBOX_DIR"/*.txt 2>/dev/null | wc -l | tr -d ' '; }
# a message "playing": a live pid in the tts pid file
playing() { /bin/sleep 600 & FAKE=$!; echo "$FAKE" >"$TTS_PID_FILE"; echo playing >"$TTS_STATE_FILE"; }
stop_playing() { kill "$FAKE" 2>/dev/null; wait "$FAKE" 2>/dev/null; }
reset() { stop_playing; for f in "$DEFERRED_DIR"/*.txt; do [[ -f "$f" ]] && kill -9 "$(basename "$f" .txt)" 2>/dev/null; done
          /bin/sleep 0.3; rm -rf "$DEFERRED_DIR" "$SPEECH_LOCK"; rm -f "$INBOX_DIR"/*.txt "$INBOX_DIR"/*.wav "$INBOX_DIR"/*.rendering "$TTS_PID_FILE" "$TTS_STATE_FILE" "$TTS_TEXT_FILE"; : >"$LOG_FILE"; }
trap 'reset; rm -rf "$TMP"' EXIT
mkdir -p "$INBOX_DIR"; : >"$LOG_FILE"

# 1. a deferral writes a record under the waiter's pid; the waiter lives in a session of its own
playing
out="$(bash "$STAGE/say_now.sh" "Answer one." 2>&1)"
check "the caller is told it is deferred" "[[ '$out' == 'deferred until the current audio ends' ]]"
check "one record, named after a live waiter" "[[ \$(records) == 1 ]] && kill -0 \$(record_pid)"
w="$(record_pid)"
check "the record holds the text and the language" "grep -q '^lang=en' '$DEFERRED_DIR/$w.txt' && grep -q 'Answer one.' '$DEFERRED_DIR/$w.txt'"
check "the waiter leads its own process group, away from the caller's" "[[ \$(ps -o pgid= -p $w | tr -d ' ') == $w && \$(ps -o pgid= -p $w | tr -d ' ') != \$(ps -o pgid= -p \$\$ | tr -d ' ') ]]"
deferred_recover
check "a live waiter is left alone by the rescuer" "[[ \$(records) == 1 && \$(inbox_count 'Answer one') == 0 ]]"
# 2. audio free: the waiter speaks, and its record goes once the speech sounds
stop_playing
wait_for "grep -q 'say_now \\[anna\\]: Answer one.' '$LOG_FILE'" 10
check "the deferred answer is spoken when the audio is free" "grep -q 'say_now \\[anna\\]: Answer one.' '$LOG_FILE'"
wait_for "[[ \$(records) == 0 ]]" 3
check "its record is gone once it sounds, nothing in the inbox" "[[ \$(records) == 0 && \$(inbox_count 'Answer one') == 0 ]]"
wait_for "! kill -0 $w 2>/dev/null" 5; reset

# 3. the incident: the waiter dies before speaking (SIGKILL: no trace of its own)
playing
bash "$STAGE/say_now.sh" --lang fr "Réponse deux." >/dev/null 2>&1; w="$(record_pid)"
kill -9 "$w"; wait_for "! kill -0 $w 2>/dev/null" 3
deferred_recover
check "a dead waiter's speech goes to the inbox, language kept" "[[ \$(inbox_count 'Réponse deux') == 1 ]] && grep -q '^lang=fr' \$(grep -l 'Réponse deux' '$INBOX_DIR'/*.txt)"
check "it is logged, and the record is gone" "grep -q 'deferred speech lost its waiter (pid $w)' '$LOG_FILE' && [[ \$(records) == 0 ]]"
deferred_recover
check "rescued once, not twice" "[[ \$(inbox_count 'Réponse deux') == 1 ]]"
wait_for "! ls '$INBOX_DIR'/*.rendering >/dev/null 2>&1" 5; reset

# 4. a waiter ended by SIGTERM says so in the log
playing
bash "$STAGE/say_now.sh" "Answer three." >/dev/null 2>&1; w="$(record_pid)"
/bin/sleep 0.5; kill -TERM "$w"; wait_for "! kill -0 $w 2>/dev/null" 3
check "a terminated waiter leaves a log line" "grep -q 'deferred speech: waiter $w ended by SIGTERM before speaking' '$LOG_FILE'"
# 5. a double press rescues it before looking at the inbox
stop_playing
bash "$STAGE/inbox_read_next.sh" >/dev/null 2>&1
check "the next double press moves it to the inbox" "[[ \$(inbox_count 'Answer three') == 1 && \$(records) == 0 ]]"
wait_for "! ls '$INBOX_DIR'/*.rendering >/dev/null 2>&1" 5; wait_for "[[ -z \"\$(tts_pid)\" ]]" 5; reset

# 6. the minute housekeeping (memory_guard.sh, run by the Tower) rescues it too
playing
bash "$STAGE/say_now.sh" "Answer four." >/dev/null 2>&1; w="$(record_pid)"
kill -9 "$w"; wait_for "! kill -0 $w 2>/dev/null" 3
SECRETARY_MEM_READING="1 5" bash "$STAGE/memory_guard.sh" >/dev/null 2>&1
check "memory_guard.sh moves it to the inbox" "[[ \$(inbox_count 'Answer four') == 1 && \$(records) == 0 ]]"
wait_for "! ls '$INBOX_DIR'/*.rendering >/dev/null 2>&1" 5; reset

# 7. waiting again behind the speech lock hands the record to the new waiter (one record only)
/bin/sleep 600 & HOLDER=$!; mkdir -p "$SPEECH_LOCK"; echo "$HOLDER" >"$SPEECH_LOCK/pid"
bash "$STAGE/say_now.sh" "Answer five." >/dev/null 2>&1; w1="$(record_pid)"
wait_for "[[ \$(records) == 1 && \$(record_pid) != $w1 ]]" 5
w2="$(record_pid)"
check "a waiter that has to wait again passes its record on" "[[ \$(records) == 1 && '$w2' != '$w1' ]] && ! kill -0 $w1 2>/dev/null && grep -q 'speech lock held by $HOLDER' '$LOG_FILE'"
kill "$HOLDER"; wait "$HOLDER" 2>/dev/null
wait_for "grep -q 'say_now \\[anna\\]: Answer five.' '$LOG_FILE'" 10
check "and it is spoken once the lock is free" "grep -q 'say_now \\[anna\\]: Answer five.' '$LOG_FILE' && [[ \$(inbox_count 'Answer five') == 0 ]]"
wait_for "[[ \$(records) == 0 ]]" 3; wait_for "[[ -z \"\$(tts_pid)\" ]]" 5; reset

# 8. speech stopped while it is being prepared is queued exactly once (not again by the rescuer)
echo 3 >"$TMP/render_s"
playing
bash "$STAGE/say_now.sh" "Answer six." >/dev/null 2>&1; w="$(record_pid)"
stop_playing
wait_for "[[ \"\$(cat '$TTS_STATE_FILE' 2>/dev/null)\" == preparing ]]" 5
echo 0.2 >"$TMP/render_s"
SAY_NOW_INTERRUPT=1 bash "$STAGE/say_now.sh" "Press-driven message." >/dev/null 2>&1 &
wait_for "grep -q 'speech stopped before it was heard' '$LOG_FILE'" 5
wait_for "! kill -0 $w 2>/dev/null" 5
deferred_recover
check "stopped while preparing: in the inbox once" "[[ \$(inbox_count 'Answer six') == 1 && \$(records) == 0 ]]"
wait
# 9. the text is written before "preparing": a stop never finds "preparing" without it
check "say_now writes the text before it claims the preparing state" "[[ \$(grep -n 'TTS_TEXT_FILE\"; fi' '$STAGE/say_now.sh' | cut -d: -f1) -lt \$(grep -n 'echo preparing' '$STAGE/say_now.sh' | cut -d: -f1) ]]"

echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
