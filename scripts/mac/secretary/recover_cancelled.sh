#!/bin/bash
# A dictation cancelled by mistake (double press, or its recorder window closed) is never erased.
# recover_cancelled.sh          prints the text of the latest cancelled dictation not yet
#                               recovered, then its folder, and marks it recovered; run it again
#                               to go back one more. Exit 1 when there is none.
# recover_cancelled.sh --list   lists cancelled dictations, newest first, without consuming them.
# The secretary treats the printed text as if it had just been dictated.
source "$(dirname "$0")/lib.sh"
RECORDINGS="${VOICE2CLIPBOARD_RECORDINGS_DIR:-$ROOT_DIR/recordings}"
cancelled_dirs() { find "$RECORDINGS" -mindepth 3 -maxdepth 3 -name cancelled -type f 2>/dev/null | sed 's:/cancelled$::' | sort -r; }

if [[ "${1:-}" == "--list" ]]; then
  while read -r d; do
    [[ -n "$d" ]] || continue
    state="waiting"; [[ -f "$d/recovered" ]] && state="recovered"
    words="$(wc -w <"$d/transcript.txt" 2>/dev/null | tr -d ' ')"
    printf '%s  %s  %s words\n' "${d#"$RECORDINGS"/}" "$state" "${words:-not transcribed,}"
  done < <(cancelled_dirs)
  exit 0
fi

while read -r d; do
  [[ -n "$d" && ! -f "$d/recovered" ]] || continue
  if [[ ! -s "$d/transcript.txt" && -f "$d/audio.wav" ]]; then
    # cancelled before any text existed (recorder window closed): transcribe now, quietly
    out="$("$ROOT_DIR/scripts/mac/recover_orphaned_recording.sh" "$d/audio.wav" --quick --copy-only 2>&1)"
    saved="$(printf '%s\n' "$out" | sed -n 's/.*Saved to *: *//p' | tail -n 1)"
    [[ -n "$saved" && -s "$ROOT_DIR/$saved" ]] && cp "$ROOT_DIR/$saved" "$d/transcript.txt"
  fi
  if [[ ! -s "$d/transcript.txt" ]] || grep -q '^\[no speech detected\]' "$d/transcript.txt"; then
    date >"$d/recovered"; continue      # nothing was said in that one: look further back
  fi
  cat "$d/transcript.txt"; echo
  echo "(cancelled dictation recovered from $d)"
  date >"$d/recovered"
  log "recover_cancelled: handed over $d"
  exit 0
done < <(cancelled_dirs)
echo "No cancelled dictation left to recover."
exit 1
