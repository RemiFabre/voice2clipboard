#!/bin/bash
# Empty iTerm frames left on screen (2026-10-24). Remi kept finding gray recorder windows after
# dictations that had worked: only the title ("🎤 Dictation running: ...") and no text. The one he
# kept for inspection (window ⌥⌘8, CGWindowID 2174) was the 23:14 dictation of 2026-10-23, which
# ended normally at 23:17:12 (transcript saved and delivered, worker exited). iTerm did close that
# window: its controller was gone (zero tabs, its number 8 handed to the next window at 23:18), but
# the frame itself stayed on screen, and AppleScript still lists it because iTerm enumerates
# NSApp's ordered windows. That dictation had run through a display sleep and wake with the
# external monitor re-plugged (23:14:49 to 23:14:58; WindowServer then failed to move this very
# window, "likely misplaced"), and it ended while the screen was still locked (unlock at 23:17:17).
# A macOS/iTerm fault, not the recorder's: nothing in the worker can make the frame go away.
# So the frames are swept: an iTerm window with no tab holds no session and runs nothing, so
# closing it (AppleScript `close`, the same performClose as its close button) cannot cancel
# anything. Safety: a window is closed only when it was already empty at a pass at least
# MIN_AGE_S earlier (a window being created is empty for a moment), its tab count is re-checked
# right before the close, and no pass runs while the screen is locked or a dictation is active.
#   empty_window_sweep.sh          one pass (memory_guard.sh runs it, at most every SWEEP_EVERY_S)
#   empty_window_sweep.sh --list   print the empty windows ("<id> <title>") and close nothing
source "$(dirname "$0")/lib.sh"
SEEN="$SECRETARY_RUNTIME/empty_windows.seen"     # "<window id> <epoch first seen empty> [failed]" per line
STAMP="$SECRETARY_RUNTIME/empty_windows.swept"   # mtime = last pass
LOCK="$SECRETARY_RUNTIME/empty_windows.lock"
MIN_AGE_S="${SECRETARY_EMPTY_WINDOW_MIN_AGE_S:-20}"
SWEEP_EVERY_S="${SECRETARY_EMPTY_WINDOW_EVERY_S:-30}"
# All iTerm access can be replaced for tests: a command taking "list" or "close <id>".
ITERM_CMD="${SECRETARY_EMPTY_WINDOW_ITERM:-}"

with_timeout() { perl -e 'alarm shift; exec @ARGV or exit 127' "$@"; }   # iTerm can hang on a dialog
iterm() {
  if [[ -n "$ITERM_CMD" ]]; then "$ITERM_CMD" "$@"; return; fi
  if [[ "$1" == list ]]; then
    with_timeout 10 /usr/bin/osascript <<'EOF'
if application "iTerm2" is not running then return ""
tell application "iTerm2"
    set out to ""
    repeat with w in windows
        try
            if (count of tabs of w) is 0 then set out to out & (id of w) & " " & (name of w) & linefeed
        end try
    end repeat
    return out
end tell
EOF
  else
    with_timeout 10 /usr/bin/osascript - "$2" <<'EOF'
on run argv
    set wid to (item 1 of argv) as integer
    if application "iTerm2" is not running then return "gone"
    tell application "iTerm2"
        if not (exists window id wid) then return "gone"
        if (count of tabs of window id wid) is not 0 then return "has tabs"
        close window id wid
    end tell
    delay 1
    tell application "iTerm2"
        if exists window id wid then return "still there"
    end tell
    return "closed"
end run
EOF
  fi
}
screen_locked() {
  if [[ -n "${SECRETARY_SCREEN_LOCKED:-}" ]]; then [[ "$SECRETARY_SCREEN_LOCKED" == 1 ]]; return; fi
  /usr/sbin/ioreg -n Root -d1 -a 2>/dev/null | grep -q CGSSessionScreenIsLocked
}

if [[ "${1:-}" == "--list" ]]; then iterm list | grep -E '^[0-9]+ '; exit 0; fi
# Tests never close real windows: any runtime other than the live one is a test (as in render_speech).
[[ -z "$ITERM_CMD" && "$SECRETARY_RUNTIME" != "$ROOT_DIR/runtime/secretary" ]] && exit 0
[[ $(( $(date +%s) - $(stat -f %m "$STAMP" 2>/dev/null || echo 0) )) -ge "$SWEEP_EVERY_S" ]] || exit 0
if ! mkdir "$LOCK" 2>/dev/null; then
  # a pass takes a few seconds; a lock older than a minute belongs to a pass that died
  [[ $(( $(date +%s) - $(stat -f %m "$LOCK" 2>/dev/null || echo 0) )) -gt 60 ]] || exit 0
  rm -rf "$LOCK"; mkdir "$LOCK" 2>/dev/null || exit 0
fi
trap 'rm -rf "$LOCK"' EXIT
screen_locked && exit 0
dictation_active && exit 0
listing="$(iterm list)" || exit 0   # iTerm did not answer: decide nothing, forget nothing
touch "$STAMP"
now="$(date +%s)"
keep=""
while read -r wid title; do
  [[ "$wid" =~ ^[0-9]+$ ]] || continue
  read -r first failed <<<"$(awk -v id="$wid" '$1 == id { print $2, $3; exit }' "$SEEN" 2>/dev/null)"
  [[ "$first" =~ ^[0-9]+$ ]] || first="$now"
  if (( now - first < MIN_AGE_S )); then keep+="$wid $first"$'\n'; continue; fi
  result="$(iterm close "$wid" 2>&1)"
  case "$result" in
    closed) log "empty window sweep: closed iTerm window $wid, left on screen with no tab (empty for $(( now - first )) s): $title" ;;
    gone|"has tabs") ;;   # it went away, or it was a window coming to life: nothing to do
    *) [[ -n "$failed" ]] || log "empty window sweep: could not close empty iTerm window $wid ($result), will retry: $title"
       keep+="$wid $first failed"$'\n' ;;
  esac
done <<<"$listing"
printf '%s' "$keep" >"$SEEN.tmp" && mv "$SEEN.tmp" "$SEEN"
