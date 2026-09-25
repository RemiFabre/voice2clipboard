#!/bin/bash
# Triple earbud press: stop current speech and read the most recently spoken message again.
source "$(dirname "$0")/lib.sh"
if dictation_active; then refuse_cue "tts_repeat_last: a dictation is active"; exit 0; fi
tts_stop
last="$(ls "$SPOKEN_DIR"/*.txt 2>/dev/null | sort | tail -n 1)"
if [[ -z "$last" ]]; then SAY_NOW_INTERRUPT=1 exec "$(dirname "$0")/say_now.sh" "Nothing to repeat."; fi
lang="$(message_lang "$last")"; from="$(sed -n 's/^from=//p' "$last" | head -n 1)"
body="$(awk 'f{print} /^$/{f=1}' "$last")"
intro="$(intro_text_for "$from" "$lang" again)"   # "Again." / "session tower here, again." / "Un message de la tour de contrôle, encore une fois."
SAY_NOW_INTERRUPT=1 nohup "$(dirname "$0")/say_now.sh" --lang "$lang" --voice "$(voice_for "$from" "$lang")" "$intro $body" >/dev/null 2>&1 &
