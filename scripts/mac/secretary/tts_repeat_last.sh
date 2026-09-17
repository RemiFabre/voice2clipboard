#!/bin/bash
# Triple earbud press: stop current speech and read the most recently spoken message again.
source "$(dirname "$0")/lib.sh"
tts_stop
last="$(ls "$SPOKEN_DIR"/*.txt 2>/dev/null | sort | tail -n 1)"
if [[ -z "$last" ]]; then exec "$(dirname "$0")/say_now.sh" "Nothing to repeat."; fi
lang="$(sed -n 's/^lang=//p' "$last" | head -n 1)"; from="$(sed -n 's/^from=//p' "$last" | head -n 1)"
body="$(awk 'f{print} /^$/{f=1}' "$last")"
nohup "$(dirname "$0")/say_now.sh" --lang "${lang:-en}" "Again, $from said: $body" >/dev/null 2>&1 &
