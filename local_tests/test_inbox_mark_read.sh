#!/bin/bash
# Marking inbox messages read without hearing them (the Session Tower's list, 2026-10-30): each
# leaves the queue under the lock shared with a double press, is archived with a status line,
# loses its voice file, and a message still rendering never dings and leaves no voice behind.
# Stub voice (slow on purpose), no audio, temp runtime.
# Run: bash local_tests/test_inbox_mark_read.sh      (TEST_SEC=<dir> tests a staged copy)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; SEC="${TEST_SEC:-$ROOT/scripts/mac/secretary}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
export SECRETARY_RUNTIME="$TMP/runtime" DICTATION_LOCK="$TMP/recorder.pid" SECRETARY_CUES_MUTED=1 \
       SECRETARY_PLAYER=/usr/bin/true SECRETARY_VOLUME_GUARD=0 SECRETARY_DING_COOLDOWN_S=0
mkdir -p "$SECRETARY_RUNTIME"
cat >"$TMP/kokoro-say" <<'STUB'
#!/bin/bash
out=""; while [[ $# -gt 0 ]]; do case "$1" in --output) out="$2"; shift 2;; --voice|--lang) shift 2;; --no-play) shift;; *) shift;; esac; done
[[ -f "$STUB_SLOW" ]] && /bin/sleep 1.5
python3 - "$out" <<'PY'
import sys, wave
w = wave.open(sys.argv[1], "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\0\0" * 4800); w.close()
PY
STUB
chmod +x "$TMP/kokoro-say"
export KOKORO_SAY="$TMP/kokoro-say" KOKORO_CTL=/usr/bin/true STUB_SLOW="$TMP/slow"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
wait_for() { for _ in $(seq 1 100); do eval "$1" && return 0; /bin/sleep 0.1; done; return 1; }
LOG="$SECRETARY_RUNTIME/secretary.log"; INBOX="$SECRETARY_RUNTIME/inbox"; SPOKEN="$SECRETARY_RUNTIME/spoken"
MARK="$SEC/inbox_mark_read.sh"
stems() { ls "$INBOX"/*.txt 2>/dev/null | xargs -n1 basename 2>/dev/null | sed 's/\.txt$//'; }
post() { bash "$SEC/inbox_post.sh" --from "$1" --lang en "$2" >/dev/null; /bin/sleep 0.01; }
rendered() { wait_for "[[ \$(ls '$INBOX'/*.rendering 2>/dev/null | wc -l) -eq 0 ]]"; }

# 1. bad usage touches nothing
post "micro duck" "First message."; post "pollen inbox triage" "Second message."; rendered
check "a bad stem is refused with exit 2" "bash '$MARK' --by tower '../../etc' >/dev/null 2>&1; [[ \$? == 2 ]]"
check "no stem at all: exit 2" "bash '$MARK' --by tower >/dev/null 2>&1; [[ \$? == 2 ]]"
check "a bad stem among good ones: nothing moved" "bash '$MARK' \$(stems) 'x y' >/dev/null 2>&1; [[ \$(stems | wc -l) -eq 2 ]]"

# 2. one marked read: archived with its status, voice gone, the other one stays
first="$(stems | head -n 1)"; second="$(stems | tail -n 1)"
/bin/sleep 0.3; dings_before="$(grep -c -E '^.{20}ding$' "$LOG")"   # the two posts' own dings
out="$(bash "$MARK" --by tower "$first")"; rc=$?
check "prints read <stem>, exit 0" "[[ \"\$out\" == 'read $first' && $rc == 0 ]]"
check "out of the inbox, voice file removed" "[[ ! -e '$INBOX/$first.txt' && ! -e '$INBOX/$first.wav' ]]"
check "archived with a status line" "grep -q '^status=marked read via tower ' '$SPOKEN/$first.txt'"
check "messages_search shows it with that status" "bash '$SEC/messages_search.sh' 'First message' | grep -q '\[marked read via tower '"
check "the other message is untouched" "[[ -f '$INBOX/$second.txt' && -f '$INBOX/$second.wav' ]]"
out="$(bash "$MARK" --by tower "$first" "$second")"
check "already gone: 'gone', the rest still marked" "[[ \"\$out\" == \$'gone $first\nread $second' ]]"
check "no ding for any of it" "[[ \$(grep -c -E '^.{20}ding\$' '$LOG') == $dings_before ]]"

# 3. a message still rendering: marked read before its voice is ready
touch "$TMP/slow"; post "session tower" "Third message, slow voice."
third="$(stems)"
check "it is rendering" "[[ -f '$INBOX/$third.rendering' ]]"
bash "$MARK" --by tower "$third" >/dev/null
wait_for "[[ ! -e '$INBOX/$third.rendering' ]]"; /bin/sleep 0.3
check "its render ends without a ding" "[[ \$(grep -c -E '^.{20}ding\$' '$LOG') == $dings_before ]]"
check "and leaves no voice file behind" "[[ -z \"\$(ls '$INBOX' | grep -v -E '\.lock$')\" ]]"
rm -f "$TMP/slow"

# 4. "Not ready yet." owed a ding for a message that is now marked read: nothing owed any more
touch "$TMP/slow"; post "session tower" "Fourth message."; fourth="$(stems)"
: >"$SECRETARY_RUNTIME/ding_owed"
bash "$MARK" --by tower "$fourth" >/dev/null
check "the owed ding is cancelled when no message is rendering" "[[ ! -e '$SECRETARY_RUNTIME/ding_owed' ]]"
wait_for "[[ ! -e '$INBOX/$fourth.rendering' ]]"; rm -f "$TMP/slow"
post "micro duck" "Fifth message."; touch "$TMP/slow"; post "session tower" "Sixth message, slow."
sixth="$(stems | tail -n 1)"; fifth="$(stems | head -n 1)"
: >"$SECRETARY_RUNTIME/ding_owed"
bash "$MARK" --by tower "$fifth" >/dev/null
check "still owed while another message renders" "[[ -e '$SECRETARY_RUNTIME/ding_owed' ]]"
wait_for "[[ ! -e '$INBOX/$sixth.rendering' ]]"; rm -f "$TMP/slow"
bash "$MARK" --by tower "$sixth" >/dev/null

# 5. a ding held through a dictation is dropped when the inbox emptied meanwhile
before="$(grep -c 'ding dropped' "$LOG")"
DING_DEFERRED=1 bash "$SEC/ding.sh"
check "held ding with an empty inbox: dropped" "[[ \$(grep -c 'ding dropped' '$LOG') -gt $before ]]"

# 6. the lock: a double press and the Tower never take the same message
post "micro duck" "Seventh message."; rendered; seventh="$(stems)"
mkdir "$SECRETARY_RUNTIME/inbox.lock"
( /bin/sleep 0.5; rmdir "$SECRETARY_RUNTIME/inbox.lock" ) &
start=$(python3 -c 'import time; print(time.time())')
out="$(bash "$MARK" --by tower "$seventh")"
waited=$(python3 -c "import time; print(time.time() - $start >= 0.4)")
check "waits for a lock held by a double press" "[[ $waited == True && \"\$out\" == 'read $seventh' ]]"
wait
check "and releases it" "[[ ! -e '$SECRETARY_RUNTIME/inbox.lock' ]]"
post "micro duck" "Eighth message."; rendered; eighth="$(stems)"
mkdir "$SECRETARY_RUNTIME/inbox.lock"; touch -t "$(date -v-1M '+%Y%m%d%H%M.%S')" "$SECRETARY_RUNTIME/inbox.lock"
out="$(bash "$MARK" --by tower "$eighth")"
check "a lock left by a dead holder is taken over" "[[ \"\$out\" == 'read $eighth' && ! -e '$SECRETARY_RUNTIME/inbox.lock' ]]"
post "micro duck" "Ninth message."; rendered; ninth="$(stems)"
bash "$SEC/inbox_read_next.sh" >/dev/null 2>&1
check "a double press releases the lock after taking its message" "[[ ! -e '$SECRETARY_RUNTIME/inbox.lock' && -f '$SPOKEN/$ninth.txt' ]]"
check "then the Tower finds it gone" "[[ \"\$(bash '$MARK' --by tower '$ninth')\" == 'gone $ninth' ]]"
bash "$SEC/inbox_read_next.sh" >/dev/null 2>&1
check "an empty inbox press releases the lock too" "[[ ! -e '$SECRETARY_RUNTIME/inbox.lock' ]]"

echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
