#!/bin/bash
# Triple earbud press: stop current speech and read the most recently spoken message again.
source "$(dirname "$0")/lib.sh"
if dictation_active; then log "tts_repeat_last refused: dictation active"; exit 0; fi
tts_stop
last="$(ls "$SPOKEN_DIR"/*.txt 2>/dev/null | sort | tail -n 1)"
if [[ -z "$last" ]]; then SAY_NOW_INTERRUPT=1 exec "$(dirname "$0")/say_now.sh" "Nothing to repeat."; fi
lang="$(sed -n 's/^lang=//p' "$last" | head -n 1)"; from="$(sed -n 's/^from=//p' "$last" | head -n 1)"
body="$(awk 'f{print} /^$/{f=1}' "$last")"
if is_secretary_name "$from"; then intro="Again."; else intro="$from here, again."; fi
SAY_NOW_INTERRUPT=1 nohup "$(dirname "$0")/say_now.sh" --lang "${lang:-en}" --voice "$(voice_for "$from" "${lang:-en}")" "$intro $body" >/dev/null 2>&1 &
