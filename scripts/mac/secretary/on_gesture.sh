#!/bin/bash
# Entry point called by the earbud button app. Gestures: single | double | triple
# single = pause/resume speech, or read the next queued message
# double = start/stop a dictation to the secretary
# triple = repeat the last spoken message
source "$(dirname "$0")/lib.sh"
log "gesture: ${1:-?}"
case "${1:-}" in
  single) exec "$(dirname "$0")/tts_toggle.sh" ;;
  double) exec "$(dirname "$0")/dictate_toggle.sh" ;;
  triple) exec "$(dirname "$0")/tts_repeat_last.sh" ;;
  *) log "unknown gesture: ${1:-}"; exit 1 ;;
esac
