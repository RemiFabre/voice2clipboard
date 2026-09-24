#!/bin/bash
# Tests of the call mode watch: "the headset microphone is open and no dictation is running".
# No audio, no microphone, no real runtime: the button app's state file is written by hand, the
# scripts run from a staged copy with a stand-in say_now.sh, ps is stubbed.
# Run: bash local_tests/test_callmode_watch.sh      (TEST_OVERLAY=<dir> tests undeployed copies)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
STAGE="$TMP/stage"; mkdir -p "$STAGE"
cp "$ROOT"/scripts/mac/secretary/*.sh "$STAGE/"
[[ -n "${TEST_OVERLAY:-}" ]] && cp "$TEST_OVERLAY"/*.sh "$STAGE/"
printf '#!/bin/bash\nprintf "%%s\\n" "$*" >>"%s/said.txt"\n' "$TMP" >"$STAGE/say_now.sh"; chmod +x "$STAGE/say_now.sh"
cat >"$TMP/ps" <<'PS'
#!/bin/bash
# stub: ps -p <pid> -o command=
case "$2" in
  4242) echo "/Users/x/.venv/bin/python3.12 /Users/x/.venv/bin/reachy-mini-daemon --no-wake" ;;
  4343) echo "/Applications/zoom.us.app/Contents/MacOS/zoom.us" ;;
  4444) echo "/usr/bin/python3 -m sounddevice_probe" ;;
esac
PS
chmod +x "$TMP/ps"
export SECRETARY_RUNTIME="$TMP/runtime" DICTATION_LOCK="$TMP/recorder.pid" SECRETARY_CUES_MUTED=1 \
       SECRETARY_PS="$TMP/ps" SECRETARY_CALLMODE_GRACE_S=0 SECRETARY_CALLMODE_CONFIRM_S=0 SECRETARY_VOLUME_GUARD=0
mkdir -p "$SECRETARY_RUNTIME"
source "$STAGE/lib.sh"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
mic() { printf '%s\t%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >"$HEADSET_MIC_FILE"; }
flag() { cut -f2- "$HEALTH_DIR/callmode" 2>/dev/null; }
said() { cat "$TMP/said.txt" 2>/dev/null; }
HS="OpenFit 2+ by Shokz"

# 1. names
check "python daemon is named by its script" "[[ \"\$(process_friendly_name 4242 python3.12)\" == 'reachy mini daemon' ]]"
check "an app is named by its bundle" "[[ \"\$(process_friendly_name 4343 zoom.us)\" == 'zoom.us' ]]"
check "python -m is named by its module" "[[ \"\$(process_friendly_name 4444 python3)\" == 'sounddevice probe' ]]"
check "unknown pid falls back to the executable" "[[ \"\$(process_friendly_name 999 some-tool)\" == 'some tool' ]]"

# 2. closed or absent microphone: no problem, flag ok
mic closed
check "closed microphone is no problem" "[[ -z \"\$(callmode_problem)\" ]]"
check "flag is ok" "[[ \"\$(flag)\" == ok ]]"

# 3. open during a dictation: no problem, nothing said
sleep 30 & rec=$!; echo "$rec" >"$DICTATION_LOCK"
mic "open	$rec:python3.12"
bash "$STAGE/on_headset.sh" mic-open "$HS" "$rec:python3.12"
check "dictation: flag stays ok" "[[ \"\$(flag)\" == ok ]]"
check "dictation: nothing said" "[[ -z \"\$(said)\" ]]"

# 4. the incident: a daemon joins during the dictation, the dictation ends, the daemon stays
mic "open	$rec:python3.12,4242:python3.12"
bash "$STAGE/on_headset.sh" mic-open "$HS" x
check "foreign holder during a dictation: still quiet" "[[ \"\$(flag)\" == ok && -z \"\$(said)\" ]]"
kill "$rec" 2>/dev/null; wait "$rec" 2>/dev/null; rm -f "$DICTATION_LOCK"
mic "open	4242:python3.12"
bash "$STAGE/on_headset.sh" mic-open "$HS" x
for _ in 1 2 3 4 5 6 7 8 9 10; do [[ -s "$TMP/said.txt" ]] && break; /bin/sleep 0.2; done   # spoken in the background
check "flag names the daemon" "grep -q 'call mode because reachy mini daemon is using' <<<\"\$(flag)\""
check "Remi is told once, by name" "[[ \$(said | grep -c 'reachy mini daemon') == 1 ]]"
check "log has the episode" "grep -q 'call mode without a dictation' '$LOG_FILE'"
bash "$STAGE/on_headset.sh" mic-open "$HS" x
check "same episode is not announced twice" "[[ \$(said | wc -l) -eq 1 ]]"
check "selfcheck helper reports it in plain words" "grep -q 'buttons cannot work' <<<\"\$(callmode_problem)\""

# 5. it stops: flag cleared; the same program again within 10 minutes stays quiet but is flagged
mic closed
bash "$STAGE/on_headset.sh" mic-closed "$HS"
check "flag cleared when the microphone closes" "[[ \"\$(flag)\" == ok ]]"
check "end of episode is logged" "grep -q 'call mode ended' '$LOG_FILE'"
mic "open	4242:python3.12"
bash "$STAGE/on_headset.sh" mic-open "$HS" x
check "repeat within 10 min: flagged" "grep -q 'reachy mini daemon' <<<\"\$(flag)\""
check "repeat within 10 min: not spoken again" "[[ \$(said | wc -l) -eq 1 ]]"
mic closed; bash "$STAGE/on_headset.sh" mic-closed "$HS"

# 6. a real call: flagged, never spoken into
mic "open	4343:zoom.us"
bash "$STAGE/on_headset.sh" mic-open "$HS" x
check "video call: flagged" "grep -q 'zoom' <<<\"\$(flag)\""
check "video call: not spoken into" "[[ \$(said | wc -l) -eq 1 ]]"

# 7. a program that only probes the microphone is gone before the grace time ends
mic closed; bash "$STAGE/on_headset.sh" mic-closed "$HS"
rm -f "$CALLMODE_NOTIFIED_FILE" "$CALLMODE_NOTIFIED_FILE.last"
mic closed
bash "$STAGE/on_headset.sh" mic-open "$HS" x
check "short probe: nothing flagged, nothing said" "[[ \"\$(flag)\" == ok && \$(said | wc -l) -eq 1 ]]"

# 8. the false alarm of 2026-09-21 18:39: a recorder that has released its lock but not yet its
#    microphone looks like a foreign program for two seconds. A second look must clear it.
mic closed; bash "$STAGE/on_headset.sh" mic-closed "$HS"
rm -f "$CALLMODE_NOTIFIED_FILE" "$CALLMODE_NOTIFIED_FILE.last"; : >"$LOG_FILE"; said_before=$(said | wc -l)
mic "open	5555:Python"
( /bin/sleep 0.5; mic closed ) &
SECRETARY_CALLMODE_CONFIRM_S=2 bash "$STAGE/on_headset.sh" mic-open "$HS" x
check "recorder winding down: nothing said" "[[ \$(said | wc -l) -eq $said_before ]]"
check "recorder winding down: flag is ok, reason logged" "[[ \"\$(flag)\" == ok ]] && grep -q 'gone at the second look' '$LOG_FILE'"
check "the flag was never raised in between" "! grep -q 'call mode without a dictation' '$LOG_FILE'"

echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
