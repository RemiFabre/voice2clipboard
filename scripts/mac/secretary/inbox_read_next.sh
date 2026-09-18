#!/bin/bash
# Speak the latest queued message (newest first, per Remi; moves it to the spoken archive).
# Says so when the inbox is empty.
source "$(dirname "$0")/lib.sh"
if dictation_active; then log "inbox_read_next refused: dictation active"; exit 0; fi
next="$(ls "$INBOX_DIR"/*.txt 2>/dev/null | sort | tail -n 1)"
if [[ -z "$next" ]]; then
  SAY_NOW_INTERRUPT=1 exec "$(dirname "$0")/say_now.sh" "No new messages."
fi
lang="$(sed -n 's/^lang=//p' "$next" | head -n 1)"; from="$(sed -n 's/^from=//p' "$next" | head -n 1)"
body="$(awk 'f{print} /^$/{f=1}' "$next")"
mv "$next" "$SPOKEN_DIR/"
export SAY_NOW_ARCHIVE="$SPOKEN_DIR/$(basename "$next")"
archive_prune
remaining="$(ls "$INBOX_DIR"/*.txt 2>/dev/null | wc -l | tr -d ' ')"
# The secretary speaks in the first person with its own voice; agents introduce themselves in
# two words ("micro duck here.") and each keeps a consistent voice.
if is_secretary_name "$from"; then intro=""; else intro="$from here."; fi
[[ "$remaining" -gt 0 ]] && intro="$intro $remaining older waiting."
SAY_NOW_INTERRUPT=1 exec "$(dirname "$0")/say_now.sh" --lang "${lang:-en}" --voice "$(voice_for "$from" "${lang:-en}")" "$intro $body"
