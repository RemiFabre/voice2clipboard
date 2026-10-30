#!/bin/bash
# Mark inbox messages read without hearing them (2026-10-30, Remi: a list on the Session Tower
# where he reads pending messages and marks one, some or all read). Each message leaves the
# earbud queue, so a double press never plays it, and goes to the archive like a discarded one,
# so messages_search.sh still finds it. Silent: no cue, no ding, no speech.
#   inbox_mark_read.sh [--by <who>] <stem> [<stem>...]     stem: "<ms>-<from>", the file name without .txt
# Prints "read <stem>" for each message taken out, "gone <stem>" for one no longer in the inbox
# (already played or marked). Exit 0 then; 2 for bad usage (nothing is touched).
# Under the inbox lock shared with inbox_read_next.sh. A message still being rendered: its render
# sees the text gone, removes its voice and does not ding (inbox_post.sh).
source "$(dirname "$0")/lib.sh"
by="hand"
[[ "${1:-}" == "--by" ]] && { by="${2:-}"; shift 2 2>/dev/null || set --; }
usage() { echo "usage: inbox_mark_read.sh [--by <who>] <stem> [<stem>...]  ($1)" >&2; exit 2; }
[[ "$by" =~ ^[A-Za-z0-9_-]+$ ]] || usage "--by takes a plain word"
[[ $# -gt 0 ]] || usage "no stem"
for stem in "$@"; do [[ "$stem" =~ ^[0-9]+-[A-Za-z0-9_-]+$ ]] || usage "not a message stem: $stem"; done
locked=0; inbox_lock && locked=1
for stem in "$@"; do
  f="$INBOX_DIR/$stem.txt"
  if [[ ! -f "$f" ]]; then echo "gone $stem"; continue; fi
  printf 'status=marked read via %s %s\n' "$by" "$(date '+%Y-%m-%d %H:%M:%S')" >>"$f"
  mv "$f" "$SPOKEN_DIR/"
  rm -f "$INBOX_DIR/$stem.wav"
  log "inbox: marked read via $by, not played: $stem"
  echo "read $stem"
done
# "Not ready yet." promised a ding for a message still rendering; if none is left, nothing is owed
[[ "$(inbox_rendering_count)" -gt 0 ]] || rm -f "$DING_OWED"
[[ "$locked" == 1 ]] && inbox_unlock
archive_prune
exit 0
