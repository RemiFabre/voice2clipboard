#!/bin/bash
# Lazy rotation of the secretary (Remi, 2026-09-20): decided at the moment he presses to dictate,
# never on a schedule. dictate_toggle.sh starts this in the background with the current
# secretary's iTerm id; the recording that follows gives the time to boot a successor.
#   lazy_rotate.sh <iTerm unique id of the current secretary>
# 1. Ask the Session Tower, which owns the cost maths: `tower rotate-advice` prints
#    "rotate <reason>" or "keep <reason>". Warm and worth keeping means keep: he values one agent
#    with a long memory. No answer within 1.5 s, or anything else, means keep.
# 2. rotate: open a fresh secretary in its own window (spawn-session: workspace 3, tiled, danger
#    mode) and wait until its prompt is ready.
# 3. Hand over through files in runtime/secretary/lazy_rotation/ (the recorder's side is
#    rotation_redirect in voice_transcriber.py): `pending` while booting, `ready` once usable.
#    Whoever renames `pending` first wins: the recorder when the transcript cannot wait any
#    longer (then the dictation goes to the old secretary as always and the new window is
#    closed), this script when the new session is ready in time (then the transcript is typed
#    there, the registration is switched, and the old window is closed once the dictation is over).
# A lost dictation is worse than a costly wake: every failure path ends with the old secretary
# still registered and untouched. The 700k end-of-turn rotation in stop_hook.sh stays as it is.
source "$(dirname "$0")/lib.sh"
old="${1:-}"
[[ -n "$old" && "${SECRETARY_LAZY_ROTATION:-1}" == "1" ]] || exit 0
TOWER="${SECRETARY_TOWER:-/Users/remi/claude_control_center/bin/tower}"
SPAWN="${SECRETARY_SPAWN:-/Users/remi/claude_control_center/bin/spawn-session}"
READY_WAIT_S="${SECRETARY_ROTATE_READY_WAIT_S:-45}"
CLOSE_DELAY_S="${SECRETARY_ROTATE_CLOSE_DELAY_S:-20}"
ROT_DIR="$SECRETARY_RUNTIME/lazy_rotation"
# iTerm access, replaceable by a stand-in for tests: <probe> ready|close <session id>
session_ready() {
  if [[ -n "${SECRETARY_ITERM_PROBE:-}" ]]; then "$SECRETARY_ITERM_PROBE" ready "$1"; return; fi
  # the input box of a started Claude Code session in danger mode
  osascript -e "tell application \"iTerm2\"
    repeat with w in windows
      repeat with t in tabs of w
        repeat with s in sessions of t
          if (unique id of s as text) is \"$1\" then return contents of s
        end repeat
      end repeat
    end repeat
  end tell" 2>/dev/null | grep -q 'bypass permissions on'
}
session_close() {
  if [[ -n "${SECRETARY_ITERM_PROBE:-}" ]]; then "$SECRETARY_ITERM_PROBE" close "$1"; return; fi
  iterm_session_action "$1" "close" >/dev/null 2>&1
}

# 1.5 s at most, whatever the Tower does (a pipe would wait for its grandchildren): the answer
# only counts when the command finished by itself.
advice=""; advice_file="$(mktemp)"
( "$TOWER" rotate-advice >"$advice_file" 2>/dev/null ) & asker=$!
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do kill -0 "$asker" 2>/dev/null || break; /bin/sleep 0.1; done
if kill -0 "$asker" 2>/dev/null; then kill "$asker" 2>/dev/null; wait "$asker" 2>/dev/null; else advice="$(head -n 1 "$advice_file")"; fi
rm -f "$advice_file"
case "$advice" in
  rotate*) ;;
  keep*) log "lazy rotation: $advice"; exit 0 ;;
  *) log "lazy rotation: keep (no usable advice from the Tower: '${advice:0:60}')"; exit 0 ;;
esac

mkdir -p "$ROT_DIR"
# one rotation at a time; a claim older than 3 minutes belongs to a rotator that died
if ! mkdir "$ROT_DIR/claim" 2>/dev/null; then
  age=$(( $(date +%s) - $(stat -f %m "$ROT_DIR/claim" 2>/dev/null || echo 0) ))
  if [[ "$age" -lt 180 ]]; then log "lazy rotation: another one is in progress, skipped"; exit 0; fi
  rmdir "$ROT_DIR/claim" 2>/dev/null; mkdir "$ROT_DIR/claim" 2>/dev/null || exit 0
fi
new=""
finish() { rmdir "$ROT_DIR/claim" 2>/dev/null; }
give_up() {   # give_up <reason>: the old secretary stays; the new window, if any, is closed
  log "lazy rotation given up: $1; the current secretary stays"
  rm -f "$ROT_DIR/pending" "$ROT_DIR/ready.tmp" "$ROT_DIR/publishing"
  [[ -n "$new" ]] && session_close "$new"
  finish; exit 0
}
rm -f "$ROT_DIR"/pending "$ROT_DIR"/ready "$ROT_DIR"/ready.tmp "$ROT_DIR"/publishing "$ROT_DIR"/aborted "$ROT_DIR"/delivered
printf '%s\n' "$old" >"$ROT_DIR/pending"
log "lazy rotation: $advice -> starting a fresh secretary while he dictates"

# The model is named: since 2026-09-24 spawn-session gives every new session Opus 5.5 by default,
# and the secretary stays on Fable 5.1 by Remi's rule (he likes the way this one talks).
cmd="cd '$ROOT_DIR/secretary' && claude --model ${SECRETARY_MODEL:-claude-opus-5-5} --effort xhigh --dangerously-skip-permissions"
out="$("$SPAWN" --title "secretary" "$cmd" 2>&1)" || out="spawn failed: $out"
new="$(printf '%s' "$out" | sed -n 's/.*iterm=\([^ ]*\).*/\1/p' | head -n 1)"
[[ -n "$new" ]] || give_up "no new window (${out:0:120})"

waited=0
until session_ready "$new"; do
  [[ -f "$ROT_DIR/pending" ]] || give_up "the transcript could not wait (the recorder took the old secretary)"
  waited=$((waited + 1)); [[ "$waited" -gt $(( READY_WAIT_S * 2 )) ]] && give_up "the new session was not ready after ${READY_WAIT_S} s"
  /bin/sleep 0.5
done
/bin/sleep "${SECRETARY_ROTATE_SETTLE_S:-3}"   # the prompt is drawn a moment before input is accepted

# publish: only if the recorder has not taken the old secretary in the meantime
printf '%s %s\n' "$old" "$new" >"$ROT_DIR/ready.tmp"
mv "$ROT_DIR/pending" "$ROT_DIR/publishing" 2>/dev/null || give_up "the transcript could not wait (the recorder took the old secretary)"
mv "$ROT_DIR/ready.tmp" "$ROT_DIR/ready"
printf '%s' "$new" >"$SESSION_FILE.tmp" && mv "$SESSION_FILE.tmp" "$SESSION_FILE"
rm -f "$ROT_DIR/publishing"
log "lazy rotation: fresh secretary $new is ready and registered (was $old), after $((waited / 2)) s"

# the old window goes once this dictation is over (delivered to the new one, or cancelled)
while dictation_active; do /bin/sleep 1; done
/bin/sleep "$CLOSE_DELAY_S"
if [[ "$(cat "$SESSION_FILE" 2>/dev/null)" == "$new" ]]; then
  session_close "$old"; log "lazy rotation: old secretary window $old closed"
else
  log "lazy rotation: registration changed again ($(cat "$SESSION_FILE" 2>/dev/null)), old window $old left open"
fi
finish
