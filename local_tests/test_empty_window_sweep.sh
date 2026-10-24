#!/bin/bash
# Empty iTerm frames (2026-10-24): a recorder window whose dictation had worked stayed on screen,
# gray, with no tab. empty_window_sweep.sh closes a window only when it was empty at an earlier
# pass too, re-checks it right before the close, and does nothing while the screen is locked or a
# dictation runs. iTerm is a stand-in (a file of "<id> <tabs> <title>" lines), the runtime is a
# temp folder: no real window is listed or closed, no sound.
# Run: bash local_tests/test_empty_window_sweep.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SWEEP="$ROOT/scripts/mac/secretary/empty_window_sweep.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }

cat >"$TMP/iterm" <<'EOF'
#!/bin/bash
echo "$*" >>"$FAKE/calls"
[[ -f "$FAKE/no_answer" ]] && exit 1
case "$1" in
  list) awk '$2 == 0 { $2 = ""; sub(/  /, " "); print }' "$FAKE/windows" ;;
  close)
    line="$(awk -v id="$2" '$1 == id' "$FAKE/windows")"
    if [[ -z "$line" ]]; then echo gone
    elif [[ -f "$FAKE/race_$2" || "$(awk '{print $2}' <<<"$line")" != 0 ]]; then echo "has tabs"
    elif [[ -f "$FAKE/close_fails" ]]; then echo "still there"
    else awk -v id="$2" '$1 != id' "$FAKE/windows" >"$FAKE/w.tmp" && mv "$FAKE/w.tmp" "$FAKE/windows"; echo closed
    fi ;;
esac
EOF
chmod +x "$TMP/iterm"
export FAKE="$TMP" SECRETARY_RUNTIME="$TMP/runtime" SECRETARY_EMPTY_WINDOW_ITERM="$TMP/iterm" \
       SECRETARY_EMPTY_WINDOW_MIN_AGE_S=1 SECRETARY_EMPTY_WINDOW_EVERY_S=0 SECRETARY_SCREEN_LOCKED=0 \
       DICTATION_LOCK="$TMP/recorder.pid" SECRETARY_CUES_MUTED=1
mkdir -p "$SECRETARY_RUNTIME"
LOG="$SECRETARY_RUNTIME/secretary.log"
sweep() { bash "$SWEEP" "$@"; }
present() { awk -v id="$1" '$1 == id { f = 1 } END { exit !f }' "$TMP/windows"; }
calls() { grep -c "^$1" "$TMP/calls" 2>/dev/null || true; }
reset() { rm -f "$TMP/calls" "$TMP"/race_* "$TMP/no_answer" "$TMP/close_fails" "$SECRETARY_RUNTIME"/empty_windows.*; : >"$LOG"; }

# 1. the leftover recorder frame next to a live session window
printf '%s\n' "2174 0 🎤 Dictation running: closing this window cancels it (audio kept)" "2383 1 ✳ secretary" >"$TMP/windows"
reset; sweep
check "first sight: nothing closed yet" "present 2174 && present 2383 && [[ \$(calls close) == 0 ]]"
check "first sight: the empty window is remembered" "grep -q '^2174 ' '$SECRETARY_RUNTIME/empty_windows.seen'"
sleep 1.2; sweep
check "empty again a pass later: closed" "! present 2174"
check "the window with a session is never touched" "present 2383 && ! grep -q 'close 2383' '$TMP/calls'"
check "one log line names the window and its title" "[[ \$(grep -c 'empty window sweep: closed iTerm window 2174' '$LOG') == 1 ]] && grep -q 'Dictation running' '$LOG'"
check "nothing left in the memory of empty windows" "[[ ! -s '$SECRETARY_RUNTIME/empty_windows.seen' ]]"

# 2. a window coming to life is empty for a moment: never closed
printf '%s\n' "300 0 new window" >"$TMP/windows"
reset; sweep
printf '%s\n' "300 1 new window" >"$TMP/windows"; sleep 1.2; sweep
check "a window that got its tab in between is left alone and forgotten" "present 300 && [[ \$(calls close) == 0 && ! -s '$SECRETARY_RUNTIME/empty_windows.seen' ]]"
printf '%s\n' "301 0 racing window" >"$TMP/windows"
reset; sweep; touch "$TMP/race_301"; sleep 1.2; sweep
check "a tab that appears between the listing and the close: the re-check keeps the window" "present 301 && ! grep -q 'closed iTerm window 301' '$LOG'"

# 3. no pass at all while the screen is locked or a dictation is active
printf '%s\n' "400 0 left over" >"$TMP/windows"
reset; SECRETARY_SCREEN_LOCKED=1 sweep; sleep 1.2; SECRETARY_SCREEN_LOCKED=1 sweep
check "screen locked: iTerm is not even asked" "present 400 && [[ ! -f '$TMP/calls' ]]"
reset; sleep 30 & echo $! >"$TMP/recorder.pid"
sweep; sleep 1.2; sweep
check "dictation running: iTerm is not even asked" "present 400 && [[ ! -f '$TMP/calls' ]]"
{ kill "$(cat "$TMP/recorder.pid")"; wait; } 2>/dev/null; rm -f "$TMP/recorder.pid"
sweep; sleep 1.2; sweep
check "after the dictation and the unlock: closed" "! present 400"

# 4. iTerm does not answer, or the close does not work
printf '%s\n' "500 0 left over" >"$TMP/windows"
reset; sweep; touch "$TMP/no_answer"; sleep 1.2; sweep
check "iTerm silent: nothing closed and the window is not forgotten" "present 500 && grep -q '^500 ' '$SECRETARY_RUNTIME/empty_windows.seen'"
rm -f "$TMP/no_answer"; touch "$TMP/close_fails"; sweep; sweep
check "a close that does not work is logged once and retried" "[[ \$(grep -c 'could not close empty iTerm window 500' '$LOG') == 1 && \$(calls close) == 2 ]]"
rm -f "$TMP/close_fails"; sweep
check "the retry closes it" "! present 500"

# 5. at most one pass every SWEEP_EVERY_S, and --list closes nothing
printf '%s\n' "600 0 left over" >"$TMP/windows"
reset; SECRETARY_EMPTY_WINDOW_EVERY_S=30 sweep; sleep 1.2; SECRETARY_EMPTY_WINDOW_EVERY_S=30 sweep
check "a second call within the interval does not ask iTerm" "[[ \$(calls list) == 1 && \$(calls close) == 0 ]]"
reset; out="$(sweep --list)"
check "--list prints the empty windows and closes nothing" "[[ \"\$out\" == '600 left over' ]] && [[ \$(calls close) == 0 ]] && present 600"

# 6. never the real iTerm from a test runtime
reset; out="$(SECRETARY_EMPTY_WINDOW_ITERM= bash "$SWEEP"; echo "exit=$?")"
check "test runtime without a stand-in: exits at once, no state written" "[[ \"\$out\" == exit=0 && ! -e '$SECRETARY_RUNTIME/empty_windows.swept' ]]"

# 7. memory_guard.sh (the once-a-minute housekeeping) runs the sweep
STAGE="$TMP/stage"; mkdir -p "$STAGE"; cp "$ROOT"/scripts/mac/secretary/*.sh "$ROOT"/scripts/mac/secretary/*.py "$STAGE/"
[[ -f "$ROOT/scripts/mac/secretary/.memory_guard.sh.new" ]] && cp "$ROOT/scripts/mac/secretary/.memory_guard.sh.new" "$STAGE/memory_guard.sh"
reset; SECRETARY_MEM_READING="1 5" bash "$STAGE/memory_guard.sh"
for _ in $(seq 1 30); do [[ -f "$TMP/calls" ]] && break; sleep 0.1; done
check "memory_guard.sh starts a sweep pass" "[[ \$(calls list) == 1 ]]"
reset; SECRETARY_MEM_READING="1 5" bash "$STAGE/memory_guard.sh" --status >/dev/null; sleep 0.5
check "memory_guard.sh --status does not" "[[ ! -f '$TMP/calls' ]]"

echo; [[ "$fails" -eq 0 ]] && echo "all passed" || echo "$fails failed"
exit "$fails"
