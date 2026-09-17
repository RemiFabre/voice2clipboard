#!/bin/bash
# Unregisters the secretary session and turns voice mode off (the iTerm window is left open).
source "$(dirname "$0")/lib.sh"
rm -f "$SESSION_FILE"
"$(dirname "$0")/voice_mode.sh" off >/dev/null
tts_stop
log "secretary stopped"
echo "secretary unregistered; voice mode off"
