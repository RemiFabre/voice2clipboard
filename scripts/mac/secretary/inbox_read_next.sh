#!/bin/bash
# Speak the oldest queued message (moves it to the spoken archive). Says so when the inbox is empty.
source "$(dirname "$0")/lib.sh"
next="$(ls "$INBOX_DIR"/*.txt 2>/dev/null | sort | head -n 1)"
if [[ -z "$next" ]]; then
  exec "$(dirname "$0")/say_now.sh" "No new messages."
fi
lang="$(sed -n 's/^lang=//p' "$next" | head -n 1)"; from="$(sed -n 's/^from=//p' "$next" | head -n 1)"
body="$(awk 'f{print} /^$/{f=1}' "$next")"
mv "$next" "$SPOKEN_DIR/"
remaining="$(ls "$INBOX_DIR"/*.txt 2>/dev/null | wc -l | tr -d ' ')"
intro="$from says:"
[[ "$remaining" -gt 0 ]] && intro="$from says, with $remaining more waiting:"
exec "$(dirname "$0")/say_now.sh" --lang "${lang:-en}" "$intro $body"
