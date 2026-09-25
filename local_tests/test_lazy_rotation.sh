#!/bin/bash
# Tests of the secretary's lazy rotation at the press (lazy_rotate.sh). Nothing real is touched:
# the Tower, the window spawner and iTerm are stand-ins, the runtime is a temp folder, and the
# "recorder" is a sleeping process holding the lock. The recorder's side of the hand-over is
# tested in test_rotation_redirect.py.
# Run: bash local_tests/test_lazy_rotation.sh      (TEST_OVERLAY=<dir> tests undeployed copies)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$TMP"' EXIT
STAGE="$TMP/stage"; mkdir -p "$STAGE"
cp "$ROOT"/scripts/mac/secretary/*.sh "$ROOT"/scripts/mac/secretary/*.py "$STAGE/"
[[ -n "${TEST_OVERLAY:-}" ]] && cp "$TEST_OVERLAY"/*.sh "$STAGE/"
export SECRETARY_RUNTIME="$TMP/runtime" DICTATION_LOCK="$TMP/recorder.pid" SECRETARY_CUES_MUTED=1 \
       SECRETARY_TOWER="$TMP/tower" SECRETARY_SPAWN="$TMP/spawn" SECRETARY_ITERM_PROBE="$TMP/probe" \
       SECRETARY_ROTATE_CLOSE_DELAY_S=0 SECRETARY_ROTATE_SETTLE_S=0 SECRETARY_ROTATE_READY_WAIT_S=3
mkdir -p "$SECRETARY_RUNTIME"
source "$STAGE/lib.sh"
ROT="$SECRETARY_RUNTIME/lazy_rotation"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
wait_for() { local n=0; until eval "$1"; do n=$((n + 1)); [[ $n -gt $(( $2 * 10 )) ]] && return 1; /bin/sleep 0.1; done; }
tower() { printf '#!/bin/bash\n%s\n' "$1" >"$TMP/tower"; chmod +x "$TMP/tower"; }
printf '#!/bin/bash\necho "$@" >>"%s/spawn.log"\n[[ -f "%s/spawn_fails" ]] && { echo "no space"; exit 1; }\necho "window=1 iterm=NEW tty=/dev/ttys999 space=3"\n' "$TMP" "$TMP" >"$TMP/spawn"
printf '#!/bin/bash\necho "$1 $2" >>"%s/probe.log"\n[[ "$1" == ready ]] && { [[ -f "%s/new_is_ready" ]]; exit; }\nexit 0\n' "$TMP" "$TMP" >"$TMP/probe"
chmod +x "$TMP/spawn" "$TMP/probe"
reset() { rm -rf "$ROT" "$TMP"/spawn.log "$TMP"/probe.log "$TMP"/new_is_ready "$TMP"/spawn_fails; printf 'OLD' >"$SESSION_FILE"; : >"$LOG_FILE"; }
recorder() { sleep 60 & rec=$!; echo "$rec" >"$DICTATION_LOCK"; }
recorder_done() { kill "$rec" 2>/dev/null; wait "$rec" 2>/dev/null; rm -f "$DICTATION_LOCK"; }

# 1. the Tower says keep, is absent, hangs or talks nonsense: nothing happens
reset; tower 'echo "keep warm until 22:01"'
bash "$STAGE/lazy_rotate.sh" OLD
check "keep: no window opened" "[[ ! -f '$TMP/spawn.log' && ! -e '$ROT/pending' ]]"
check "keep: reason logged" "grep -q 'lazy rotation: keep warm' '$LOG_FILE'"
reset; rm -f "$TMP/tower"; bash "$STAGE/lazy_rotate.sh" OLD
check "no Tower: keep" "[[ ! -f '$TMP/spawn.log' ]] && grep -q 'no usable advice' '$LOG_FILE'"
reset; tower 'sleep 10; echo rotate late'
t0=$(date +%s); bash "$STAGE/lazy_rotate.sh" OLD; t1=$(date +%s)
check "hanging Tower: keep within 3 s" "[[ \$((t1 - t0)) -le 3 && ! -f '$TMP/spawn.log' ]]"
reset; tower 'echo "<html>error</html>"'; bash "$STAGE/lazy_rotate.sh" OLD
check "nonsense from the Tower: keep" "[[ ! -f '$TMP/spawn.log' ]]"
reset; tower 'echo "rotate cold"'; SECRETARY_LAZY_ROTATION=0 bash "$STAGE/lazy_rotate.sh" OLD
check "switch off: nothing" "[[ ! -f '$TMP/spawn.log' ]]"

# 2. rotate, the new session is ready while he still talks
reset; tower 'echo "rotate cold, 339k context"'; recorder; touch "$TMP/new_is_ready"
bash "$STAGE/lazy_rotate.sh" OLD & rot=$!
check "new window asked in danger mode, titled, on Opus 5.5" "wait_for \"grep -q -- '--title secretary .*--model claude-opus-5-5 --effort xhigh --dangerously-skip-permissions' '$TMP/spawn.log' 2>/dev/null\" 3"
check "hand-over published" "wait_for \"[[ \\\"\\\$(cat '$ROT/ready' 2>/dev/null)\\\" == 'OLD NEW' ]]\" 5"
check "new secretary registered" "[[ \"\$(cat '$SESSION_FILE')\" == NEW ]]"
check "old window still open during the dictation" "! grep -q 'close OLD' '$TMP/probe.log'"
recorder_done; wait "$rot"
check "old window closed after the dictation" "grep -q 'close OLD' '$TMP/probe.log'"
check "new window never closed" "! grep -q 'close NEW' '$TMP/probe.log'"
check "claim released" "[[ ! -d '$ROT/claim' ]]"

# 3. the transcript cannot wait: the recorder takes the old secretary (rename pending -> aborted)
reset; recorder
bash "$STAGE/lazy_rotate.sh" OLD & rot=$!
wait_for "[[ -f '$ROT/pending' && -f '$TMP/spawn.log' ]]" 3
mv "$ROT/pending" "$ROT/aborted"; wait "$rot"; recorder_done
check "recorder won: old secretary still registered" "[[ \"\$(cat '$SESSION_FILE')\" == OLD ]]"
check "recorder won: new window closed, old untouched" "grep -q 'close NEW' '$TMP/probe.log' && ! grep -q 'close OLD' '$TMP/probe.log'"
check "recorder won: nothing published" "[[ ! -e '$ROT/ready' ]]"

# 4. the new session never becomes ready
reset; recorder; bash "$STAGE/lazy_rotate.sh" OLD; recorder_done
check "never ready: given up, old stays, new closed" "[[ \"\$(cat '$SESSION_FILE')\" == OLD && ! -e '$ROT/pending' ]] && grep -q 'close NEW' '$TMP/probe.log' && grep -q 'not ready after' '$LOG_FILE'"

# 5. no window could be opened
reset; touch "$TMP/spawn_fails"; bash "$STAGE/lazy_rotate.sh" OLD
check "spawn failure: given up, old stays, nothing pending" "[[ \"\$(cat '$SESSION_FILE')\" == OLD && ! -e '$ROT/pending' ]] && grep -q 'no new window' '$LOG_FILE'"

# 6. two presses in a row: one rotation only
reset; recorder
bash "$STAGE/lazy_rotate.sh" OLD & rot=$!; wait_for "[[ -d '$ROT/claim' ]]" 3
bash "$STAGE/lazy_rotate.sh" OLD
check "second rotation is skipped while one runs" "grep -q 'another one is in progress' '$LOG_FILE' && [[ \$(wc -l <'$TMP/spawn.log') -eq 1 ]]"
wait "$rot"; recorder_done

echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
