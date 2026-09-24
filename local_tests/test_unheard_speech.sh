#!/bin/bash
# Speech that is still being prepared must never be dropped in silence (2026-09-21: an answer of
# the secretary that had waited behind a playing message was killed by a double press meant for
# the next inbox message; never spoken, no trace).
# Stub voice that takes 3 s to render, stand-in player, temp runtime: no sound, no microphone.
# Run: bash local_tests/test_unheard_speech.sh      (TEST_OVERLAY=<dir> tests undeployed copies)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$TMP"' EXIT
STAGE="$TMP/stage"; mkdir -p "$STAGE"
cp "$ROOT"/scripts/mac/secretary/*.sh "$ROOT"/scripts/mac/secretary/*.py "$STAGE/"
[[ -n "${TEST_OVERLAY:-}" ]] && cp "$TEST_OVERLAY"/*.sh "$STAGE/"
cat >"$TMP/slow-say" <<'STUB'
#!/bin/bash
out=""; while [[ $# -gt 0 ]]; do case "$1" in --output) out="$2"; shift 2;; --voice|--lang) shift 2;; --no-play) shift;; *) shift;; esac; done
/bin/sleep "${STUB_RENDER_S:-3}"
python3 - "$out" <<'PY'
import sys, wave
w = wave.open(sys.argv[1], "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\0\0" * 24000); w.close()
PY
STUB
printf '#!/bin/bash\necho "$1" >>"%s/player.calls"\nexec /bin/sleep 2\n' "$TMP" >"$TMP/player"
printf '#!/bin/bash\necho launched >>"%s/launcher.calls"\n' "$TMP" >"$TMP/launcher"
chmod +x "$TMP/slow-say" "$TMP/player" "$TMP/launcher"
export SECRETARY_RUNTIME="$TMP/runtime" DICTATION_LOCK="$TMP/recorder.pid" SECRETARY_CUES_MUTED=1 SECRETARY_VOLUME_GUARD=0 \
       SECRETARY_END_TONE=0 KOKORO_SAY="$TMP/slow-say" KOKORO_CTL=/usr/bin/true FALLBACK_SAY="$TMP/slow-say" \
       SECRETARY_PLAYER="$TMP/player" SECRETARY_LAUNCHER="$TMP/launcher"
mkdir -p "$SECRETARY_RUNTIME"
source "$STAGE/lib.sh"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
wait_for() { local n=0; until eval "$1"; do n=$((n + 1)); [[ $n -gt $(( $2 * 10 )) ]] && return 1; /bin/sleep 0.1; done; }
preparing() { wait_for "[[ \"\$(cat '$TTS_STATE_FILE' 2>/dev/null)\" == preparing ]]" 3; }
inbox_has() { grep -qs "$1" "$INBOX_DIR"/*.txt; }
quiet_end() { tts_stop >/dev/null 2>&1; wait 2>/dev/null; rm -f "$INBOX_DIR"/* "$TMP/player.calls"; : >"$LOG_FILE"; }
mkdir -p "$INBOX_DIR"

# 1. the incident: a double press while the secretary's answer is being prepared
bash "$STAGE/say_now.sh" "Answer number one." >/dev/null 2>&1 & preparing
bash "$STAGE/on_gesture.sh" double
check "double press leaves it alone" "grep -q 'double press while speech is being prepared: left alone' '$LOG_FILE'"
check "it is then spoken" "wait_for \"[[ -s '$TMP/player.calls' ]]\" 6 && grep -q 'say_now \\[.*\\]: Answer number one' '$LOG_FILE'"
check "and not also put in the inbox" "! inbox_has 'Answer number one'"
quiet_end

# 2. a triple press is treated the same way
bash "$STAGE/say_now.sh" "Answer number two." >/dev/null 2>&1 & preparing
bash "$STAGE/on_gesture.sh" triple
check "triple press leaves it alone" "grep -q 'triple press while speech is being prepared: left alone' '$LOG_FILE'"
quiet_end

# 3. anything else that stops it before a word was heard (a dictation starting, another message
#    interrupting) moves it to the inbox
bash "$STAGE/say_now.sh" "Answer number three." >/dev/null 2>&1 & preparing
bash "$STAGE/on_gesture.sh" single; /bin/sleep 0.2     # refused while preparing: nothing may be lost
check "single press while preparing is still refused, nothing queued" "grep -q 'refused: single press' '$LOG_FILE' && ! inbox_has 'Answer number three'"
tts_stop
check "stopped before it was heard: it is in the inbox, from the secretary" "wait_for \"inbox_has 'Answer number three'\" 3 && grep -qs '^from=secretary' '$INBOX_DIR'/*.txt"
check "the move is logged" "grep -q 'speech stopped before it was heard: moved to the inbox' '$LOG_FILE'"
quiet_end

# 4. once it sounds, a stop is a stop
STUB_RENDER_S=0 bash "$STAGE/say_now.sh" "Answer number four." >/dev/null 2>&1 &
wait_for "[[ \"\$(cat '$TTS_STATE_FILE' 2>/dev/null)\" == playing ]]" 5
check "no text is kept once playback has started" "[[ ! -f '$TTS_TEXT_FILE' ]]"
tts_stop; /bin/sleep 0.5
check "a message he stopped while hearing it is not re-queued" "! inbox_has 'Answer number four'"
quiet_end

# 5. an agent's voice is not re-queued as the secretary; inbox playback is never re-queued
bash "$STAGE/say_now.sh" --voice paul "Agent speech." >/dev/null 2>&1 & preparing
tts_stop; /bin/sleep 0.5
check "another voice: logged, not re-queued under the secretary's name" "! inbox_has 'Agent speech' && grep -q 'not re-queued' '$LOG_FILE'"
quiet_end

check "no dictation was ever started" "[[ ! -f '$TMP/launcher.calls' ]]"
echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
