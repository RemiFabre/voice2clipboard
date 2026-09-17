#!/bin/bash
# Speak the latest queued message (newest first, per Remi; moves it to the spoken archive).
# Says so when the inbox is empty.
source "$(dirname "$0")/lib.sh"
next="$(ls "$INBOX_DIR"/*.txt 2>/dev/null | sort | tail -n 1)"
if [[ -z "$next" ]]; then
  exec "$(dirname "$0")/say_now.sh" "No new messages."
fi
lang="$(sed -n 's/^lang=//p' "$next" | head -n 1)"; from="$(sed -n 's/^from=//p' "$next" | head -n 1)"
body="$(awk 'f{print} /^$/{f=1}' "$next")"
mv "$next" "$SPOKEN_DIR/"
remaining="$(ls "$INBOX_DIR"/*.txt 2>/dev/null | wc -l | tr -d ' ')"
intro="$from says:"
[[ "$remaining" -gt 0 ]] && intro="$from says, with $remaining older waiting:"
exec "$(dirname "$0")/say_now.sh" --lang "${lang:-en}" "$intro $body"
