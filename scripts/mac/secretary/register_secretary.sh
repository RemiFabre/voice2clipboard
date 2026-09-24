#!/bin/bash
# Registers the iTerm window that earbud dictations are typed into. Run from inside the secretary
# session (its Bash tool inherits ITERM_SESSION_ID), and by the hooks on the secretary's own turns,
# so a secretary that was resumed by hand in another window is found again without anyone noticing.
# Usage: register_secretary.sh [--claude-session <id>] [--pid <claude pid>] [--iterm <unique id>] [--quiet]
source "$(dirname "$0")/lib.sh"
claude_session=""; pid=""; iterm=""; quiet=0
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --claude-session) claude_session="$2"; shift 2 ;;
    --pid) pid="$2"; shift 2 ;;
    --iterm) iterm="$2"; shift 2 ;;
    --quiet) quiet=1; shift ;;
    *) shift ;;
  esac
done
[[ -n "$iterm" ]] || iterm="$(iterm_unique_id_from_env)"
if [[ -z "$iterm" ]]; then
  [[ "$quiet" == 1 ]] || echo "not registered: ITERM_SESSION_ID is not set (not running inside iTerm?)"
  exit 1
fi
# The claude process is one of our ancestors (hook -> shell -> claude, or Bash tool -> claude).
if [[ -z "$pid" ]]; then
  p=$$
  for _ in 1 2 3 4 5 6 7 8; do
    p="$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')"; [[ -n "$p" && "$p" != 1 ]] || break
    comm="$(ps -o comm= -p "$p" 2>/dev/null)"
    if [[ "$(basename "$comm")" == "claude" || "$comm" == */claude/versions/* ]]; then pid="$p"; break; fi
  done
fi
previous="$(cat "$SESSION_FILE" 2>/dev/null || true)"
printf '%s' "$iterm" >"$SESSION_FILE"
[[ -n "$pid" ]] && printf '%s' "$pid" >"$SECRETARY_CLAUDE_PID_FILE"
[[ -n "$claude_session" ]] && printf '%s' "$claude_session" >"$SECRETARY_CLAUDE_SESSION_FILE"
if [[ "$previous" != "$iterm" ]]; then
  log "secretary registered: iTerm $iterm (was ${previous:-none}) claude pid ${pid:-unknown}"
fi
[[ "$quiet" == 1 ]] || echo "secretary registered: dictations go to iTerm session $iterm"
