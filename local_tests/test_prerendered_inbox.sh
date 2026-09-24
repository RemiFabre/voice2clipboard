#!/bin/bash
# Pre-rendered inbox: the voice is rendered when a message is queued, the ding comes after the
# render, and playback uses the ready file. Stub voice, no audio, temp runtime.
# Run: bash local_tests/test_prerendered_inbox.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; SEC="${TEST_SEC:-$ROOT/scripts/mac/secretary}"   # TEST_SEC: a staged copy
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
export SECRETARY_RUNTIME="$TMP/runtime" DICTATION_LOCK="$TMP/recorder.pid" SECRETARY_CUES_MUTED=1
mkdir -p "$SECRETARY_RUNTIME"
# Stub for kokoro-say: writes 0.2 s of silence per call and records each request.
cat >"$TMP/kokoro-say" <<'STUB'
#!/bin/bash
out=""; voice=""; while [[ $# -gt 0 ]]; do case "$1" in --output) out="$2"; shift 2;; --voice) voice="$2"; shift 2;; --lang) shift 2;; --no-play) shift;; *) text="$1"; shift;; esac; done
printf '%s|%s\n' "$voice" "$text" >>"$STUB_LOG"
python3 - "$out" <<'PY'
import sys, wave
w = wave.open(sys.argv[1], "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\0\0" * 4800); w.close()
PY
STUB
chmod +x "$TMP/kokoro-say"
export KOKORO_SAY="$TMP/kokoro-say" KOKORO_CTL=/usr/bin/true STUB_LOG="$TMP/stub.log"; : >"$STUB_LOG"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
wait_for() { for _ in $(seq 1 100); do eval "$1" && return 0; /bin/sleep 0.1; done; return 1; }
LOG="$SECRETARY_RUNTIME/secretary.log"; INBOX="$SECRETARY_RUNTIME/inbox"

# 1. posting returns at once and renders in the background; the ding only comes after the render
start=$(python3 -c 'import time; print(time.time())')
bash "$SEC/inbox_post.sh" --from "micro duck" "The antenna script is fixed." >/dev/null
took=$(python3 -c "import time; print(time.time() - $start < 1.5)")
check "inbox_post returns without waiting for the voice" "[[ $took == True ]]"
check "the text is queued immediately" "ls '$INBOX'/*.txt >/dev/null 2>&1"
wait_for "ls '$INBOX'/*.wav >/dev/null 2>&1"
check "the voice file appears next to the text" "ls '$INBOX'/*.wav >/dev/null 2>&1"
wait_for "grep -q 'ding' '$LOG'"
render_line=$(grep -n 'pre-rendered' "$LOG" | head -1 | cut -d: -f1); ding_line=$(grep -n 'ding' "$LOG" | head -1 | cut -d: -f1)
check "the ding comes after the render" "[[ -n '$render_line' && -n '$ding_line' && $render_line -lt $ding_line ]]"
check "rendered in the agent's own voice" "grep -q \"^\$(source '$SEC/lib.sh'; voice_for 'micro duck' en)|The antenna script is fixed\" '$STUB_LOG'"
check "the two-word introduction is pre-rendered too" "grep -q '|micro duck here.' '$STUB_LOG'"

# 2. playback uses the ready file: no new synthesis of the body at read time
before=$(wc -l <"$STUB_LOG")
bash "$SEC/inbox_read_next.sh" >/dev/null 2>&1
wait_for "grep -q 'say_now.*pre-rendered' '$LOG'"
check "playback used the pre-rendered audio" "grep -q 'say_now.*pre-rendered' '$LOG'"
check "no synthesis at read time" "[[ \$(wc -l <'$STUB_LOG') -eq $before ]]"
check "the message moved to the archive" "ls '$SECRETARY_RUNTIME'/spoken/*.txt >/dev/null 2>&1 && ! ls '$INBOX'/*.txt >/dev/null 2>&1"
check "no voice file left behind in the inbox" "! ls '$INBOX'/*.wav >/dev/null 2>&1"

# 3. fallback: a message without a voice file is still read (rendered on demand)
printf 'lang=en\nfrom=secretary\n\nFallback message.\n' >"$INBOX/1-secretary.txt"
bash "$SEC/inbox_read_next.sh" >/dev/null 2>&1
wait_for "grep -q '|Fallback message' '$STUB_LOG'"
check "missing pre-render falls back to on-demand synthesis" "grep -q '|Fallback message' '$STUB_LOG'"

# 3b. a message whose voice is still being rendered does not exist for a double press (Remi,
#     2026-09-20): a short cached sentence at once, nothing consumed, and the ding is owed
( source "$SEC/lib.sh"; cached_clip en "$SECRETARY_VOICE" "$NOT_READY_TEXT" >/dev/null )
printf 'lang=en\nfrom=micro duck\n\nStill cooking.\n' >"$INBOX/5-micro_duck.txt"; : >"$INBOX/5-micro_duck.rendering"
check "unrendered only: a press gets speech at once (cached clip)" "( source '$SEC/lib.sh'; next_message_ready )"
: >"$STUB_LOG"; : >"$LOG"
bash "$SEC/inbox_read_next.sh" >/dev/null 2>&1
wait_for "grep -q 'say_now.*Not ready yet' '$LOG'"
check "he hears 'Not ready yet.'" "grep -q 'say_now.*pre-rendered.*Not ready yet' '$LOG'"
check "nothing was synthesised for it" "[[ ! -s '$STUB_LOG' ]]"
check "the unrendered message was not consumed" "[[ -f '$INBOX/5-micro_duck.txt' ]]"
check "the ding is owed" "[[ -f '$SECRETARY_RUNTIME/ding_owed' ]]"
date +%s >"$SECRETARY_RUNTIME/last_ding"; : >"$LOG"
bash "$SEC/ding.sh"
check "an owed ding ignores the cooldown, once" "grep -q '^.* ding\$' '$LOG' && [[ ! -f '$SECRETARY_RUNTIME/ding_owed' ]]"
bash "$SEC/ding.sh"
check "the next ding respects the cooldown again" "grep -q 'ding skipped' '$LOG'"
# an older rendered message is played while the newest is still rendering
printf 'lang=en\nfrom=micro duck\n\nOlder and ready.\n' >"$INBOX/4-micro_duck.txt"
python3 "$SEC/speech_render.py" render --lang en --voice paul --out "$INBOX/4-micro_duck.wav" "Older and ready." >/dev/null 2>&1
for _ in $(seq 1 50); do [[ -z "$(source "$SEC/lib.sh"; tts_pid)" ]] && break; /bin/sleep 0.1; done
bash "$SEC/inbox_read_next.sh" >/dev/null 2>&1
wait_for "ls '$SECRETARY_RUNTIME'/spoken/4-micro_duck.txt >/dev/null 2>&1"
check "an older ready message is played instead" "[[ -f '$SECRETARY_RUNTIME/spoken/4-micro_duck.txt' && -f '$INBOX/5-micro_duck.txt' ]]"
check "the unrendered one is not announced as 'older waiting'" "! grep -q 'older waiting' '$LOG'"
# a render that died: after RENDERING_MAX_S the message is read anyway (on demand)
touch -t "$(date -v-10M '+%Y%m%d%H%M.%S')" "$INBOX/5-micro_duck.rendering"
for _ in $(seq 1 50); do [[ -z "$(source "$SEC/lib.sh"; tts_pid)" ]] && break; /bin/sleep 0.1; done
bash "$SEC/inbox_read_next.sh" >/dev/null 2>&1
wait_for "grep -q '|.*Still cooking' '$STUB_LOG'"
check "a stale rendering marker does not hide a message for ever" "grep -q 'Still cooking' '$STUB_LOG'"
# posting sets and clears the marker
bash "$SEC/inbox_post.sh" --from "micro duck" "Marker check." >/dev/null
check "a posted message is marked as rendering at once" "ls '$INBOX'/*.rendering >/dev/null 2>&1"
wait_for "! ls '$INBOX'/*.rendering >/dev/null 2>&1"
check "the marker goes when the voice is ready" "! ls '$INBOX'/*.rendering >/dev/null 2>&1 && ls '$INBOX'/*.wav >/dev/null 2>&1"

# 4. long texts are rendered in chunks so urgent speech never waits behind a long render
long="$(for i in $(seq 1 30); do printf 'Sentence number %s is here for the test. ' "$i"; done)"
: >"$STUB_LOG"
python3 "$SEC/speech_render.py" render --lang en --voice af_heart --out "$TMP/long.wav" "$long"
check "a 240 word text is split into several requests" "[[ \$(wc -l <'$STUB_LOG') -ge 3 ]]"
check "chunks are joined into one file" "python3 -c \"import wave; w = wave.open('$TMP/long.wav'); assert w.getnframes() >= 3 * 4800\""

echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
