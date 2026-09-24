#!/bin/bash
# Tests for the output volume guard (the 2026-09-20 "dead buttons" that were a muted headset).
# No sound and no real volume change: osascript is replaced by a stub that keeps its state in a file.
# Run: bash local_tests/test_volume_guard.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
export SECRETARY_RUNTIME="$TMP/runtime" DICTATION_LOCK="$TMP/recorder.pid" SECRETARY_CUES_MUTED=1
mkdir -p "$SECRETARY_RUNTIME"

# Stub volume control: "get volume settings" prints the state file, "set volume ..." edits it.
STATE="$TMP/volume.state"; export STATE
cat >"$TMP/fake_osascript" <<'STUB'
#!/bin/bash
vol="$(cut -d' ' -f1 "$STATE")"; muted="$(cut -d' ' -f2 "$STATE")"
for arg in "$@"; do
  case "$arg" in
    "get volume settings") echo "output volume:$vol, input volume:50, alert volume:100, output muted:$muted" ;;
    "set volume output volume "*) vol="${arg##* }" ;;
    "set volume without output muted") muted=false ;;
  esac
done
echo "$vol $muted" >"$STATE"
STUB
chmod +x "$TMP/fake_osascript"
export SECRETARY_VOLUME_CTL="$TMP/fake_osascript" SECRETARY_OUTPUT_NAME="OpenFit 2+ by Shokz"
source "$ROOT/scripts/mac/secretary/lib.sh"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
state() { cat "$STATE"; }

# 1. the incident: music volume at zero and muted -> a press makes it audible again
echo "0 true" >"$STATE"; ensure_audible
check "zero and muted is raised to the restore level" "[[ \"\$(state)\" == '30 false' ]]"
check "the raise is logged" "grep -q 'volume guard: the headset output was silent (volume=0 muted=true), raised to 30' '$LOG_FILE'"

# 2. an audible volume is never touched, neither up nor down
echo "12 false" >"$STATE"; ensure_audible
check "12 percent is left alone" "[[ \"\$(state)\" == '12 false' ]]"
echo "80 false" >"$STATE"; ensure_audible
check "80 percent is left alone" "[[ \"\$(state)\" == '80 false' ]]"

# 3. muted at a higher level: unmute only, the level is not lowered to the restore level
echo "60 true" >"$STATE"; ensure_audible
check "muted at 60 is unmuted at 60" "[[ \"\$(state)\" == '60 false' ]]"

# 4. unsolicited sounds (the ding) only report: a deliberate zero is respected, but flagged
echo "0 false" >"$STATE"; ensure_audible --report; rc=$?
check "--report does not change the volume" "[[ \"\$(state)\" == '0 false' ]]"
check "--report returns non-zero" "[[ $rc != 0 ]]"
check "--report raises the health flag" "[[ -n \"\$(health_problem output)\" ]]"
ensure_audible
check "the next press clears the health flag" "[[ -z \"\$(health_problem output)\" ]]"

# 5. another output (Mac speakers muted on purpose) is left alone
echo "0 true" >"$STATE"; SECRETARY_OUTPUT_NAME="MacBook Pro Speakers" ensure_audible
check "muted speakers are not touched" "[[ \"\$(state)\" == '0 true' ]]"

# 6. an output without a volume control ("missing value") is ignored without error
cat >"$TMP/no_volume" <<'STUB'
#!/bin/bash
echo "output volume:missing value, input volume:50, alert volume:100, output muted:missing value"
STUB
chmod +x "$TMP/no_volume"
check "output without volume is ignored" "SECRETARY_VOLUME_CTL='$TMP/no_volume' ensure_audible"

# 7. the guard can be switched off
echo "0 true" >"$STATE"; SECRETARY_VOLUME_GUARD=0 ensure_audible
check "guard off leaves everything alone" "[[ \"\$(state)\" == '0 true' ]]"

# 8. whole press path: a double press on a paused message raises the volume, discards the message
#    and logs it (the confirmation cue itself is muted here)
echo "0 true" >"$STATE"
sleep 30 & player=$!; sleep 0.3; kill -STOP "$player"   # let it exec first: a stopped bash fork would run our EXIT trap
echo "$player" >"$TTS_PID_FILE"; echo paused >"$TTS_STATE_FILE"
bash "$ROOT/scripts/mac/secretary/on_gesture.sh" double
check "press path raised the volume" "[[ \"\$(state)\" == '30 false' ]]"
check "paused message was discarded" "! kill -0 $player 2>/dev/null"
check "discard is logged" "grep -q 'tts stopped' '$LOG_FILE'"
kill -CONT "$player" 2>/dev/null; kill "$player" 2>/dev/null

# 9. self-check: reports the silent headset, and with --speak repairs it instead
echo "0 true" >"$STATE"
out="$(SELFCHECK_RETRIES=0 bash "$ROOT/scripts/mac/secretary/selfcheck.sh" 2>/dev/null)"
check "plain self-check names the silent headset" "grep -q 'headset volume is at zero or muted' <<<\"\$out\""
check "plain self-check does not change the volume" "[[ \"\$(state)\" == '0 true' ]]"

echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
