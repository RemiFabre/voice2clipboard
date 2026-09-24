#!/bin/bash
# Integration test of the button app's Now Playing watchdog. Silent, no microphone, no prompt.
# SIDE EFFECT: for about 30 s the earbud buttons go to test processes instead of the live app, so
# do not run it while Remi is using the earbuds. It ends by handing the buttons back to the live
# app and checks that macOS agrees.
# (2026-09-20: two real presses were lost to a run of this test.) Hence the explicit flag.
# Run: bash local_tests/test_nowplaying_watchdog.sh --borrow-the-buttons
set -u
[[ "${1:-}" == "--borrow-the-buttons" ]] || { echo "this test takes the earbud buttons for 40 s; pass --borrow-the-buttons when Remi is not using them"; exit 2; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
source "$ROOT/scripts/mac/secretary/lib.sh"
if audio_busy; then echo "a dictation or a message is running: not now"; rmdir "$TMP"; exit 2; fi
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
wait_for() { local n=0; until eval "$1"; do n=$((n + 1)); [[ $n -gt $(( $2 * 5 )) ]] && return 1; /bin/sleep 0.2; done; }

sdk_flag=(); xcrun swiftc -O -o "$TMP/app" "$ROOT/scripts/mac/earbuds/EarbudButtons.swift" >/dev/null 2>&1 || {
  sdk_flag=(-sdk "$(ls -d /Library/Developer/CommandLineTools/SDKs/MacOSX15.*.sdk | sort -V | tail -n 1)")
  xcrun swiftc "${sdk_flag[@]}" -O -o "$TMP/app" "$ROOT/scripts/mac/earbuds/EarbudButtons.swift" || exit 1; }
xcrun swiftc "${sdk_flag[@]}" -O -o "$TMP/client" "$ROOT/local_tests/nowplaying_client.swift" || exit 1

LOGF="$TMP/earbuds.log"; HEALTH="$TMP/health"
cleanup() {
  kill "${app_pid:-}" "${thief_pid:-}" 2>/dev/null; exec 3>&- 2>/dev/null
  "$ROOT/scripts/mac/earbuds/ctl.sh" reassert >/dev/null 2>&1
  rm -rf "$TMP"
}
trap cleanup EXIT
start="$(date '+%Y-%m-%d %H:%M:%S')"
MIC="$TMP/headset_mic"
EARBUDS_TEST=1 EARBUDS_LOG="$LOGF" EARBUDS_HEALTH_DIR="$HEALTH" EARBUDS_MIC_STATE="$MIC" EARBUDS_ASSERT_EVERY_S=6 "$TMP/app" /usr/bin/true >/dev/null 2>&1 &
app_pid=$!
ours_count() { grep -c 'Now Playing is ours again' "$LOGF" 2>/dev/null || true; }

# 1. the start claim is seen in the system log: the watchdog is not blind
check "test app sees its own claim" "wait_for \"[[ -f '$HEALTH/nowplaying' ]] && grep -q 'ok' '$HEALTH/nowplaying'\" 8"

# 2. another app starts playing and KEEPS playing (a video he is watching): the buttons come
#    back within seconds anyway (policy of 2026-09-20 evening: always ours), and the other app is
#    sent nothing: a claim must not pause his video.
mkfifo "$TMP/in"; "$TMP/client" thief <"$TMP/in" >"$TMP/thief.out" 2>&1 & thief_pid=$!
exec 3>"$TMP/in"; echo assert >&3
check "theft is logged" "wait_for \"grep -q 'Now Playing taken by' '$LOGF'\" 5"
check "buttons are taken back while the other app still plays" "wait_for '[[ \$(ours_count) -ge 1 ]]' 5"
check "health flag stays ok" "grep -q 'ok' '$HEALTH/nowplaying'"

# 3. an app that insists (play, pause, play, ... as when scrubbing a video): we end up the owner
for _ in 1 2 3; do echo claim >&3; /bin/sleep 1.2; done
check "buttons come back after each of 3 more thefts" "wait_for '[[ \$(ours_count) -ge 4 ]]' 8"

# 4. the safety-net claim (every 6 s here) runs while the other app is still "playing": whatever
#    macOS does with our paused instant, we must still be the owner afterwards
/bin/sleep 8
last="$(grep -E 'Now Playing (taken by|is ours again)' "$LOGF" | tail -n 1)"
check "still ours after a safety-net claim" "grep -q 'ours again' <<<\"\$last\""
check "the other app was sent no command" "! grep -q 'GOT A COMMAND' '$TMP/thief.out'"
check "headset microphone state is written" "grep -Eq 'closed|absent|open' '$MIC'"
if grep -q 'GOT A COMMAND' "$TMP/thief.out" || grep -q '^.* command ' "$LOGF"; then
  echo "WARN a real button press arrived during the test and was lost: tell Remi"
fi

# 5. hand back to the live app and make sure macOS agrees
echo quit >&3; exec 3>&-; kill "$app_pid" 2>/dev/null; wait "$app_pid" 2>/dev/null
live="$(pgrep -f 'EarbudButtons.app/Contents/MacOS/EarbudButtons' | head -n 1)"
if [[ -n "$live" ]]; then
  "$ROOT/scripts/mac/earbuds/ctl.sh" reassert >/dev/null; /bin/sleep 2
  owner="$(/usr/bin/log show --start "$start" --style compact --predicate 'process == "mediaremoted" AND eventMessage CONTAINS "ActiveNowPlayingClient changed"' 2>/dev/null | tail -n 1)"
  check "live app (pid $live) owns the buttons again" "grep -q -- \"-$live \" <<<\"\$owner\""
else
  echo "skip: live button app is not running"
fi
sed 's/^/    app log: /' "$LOGF"
echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
