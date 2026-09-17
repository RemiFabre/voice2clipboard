#!/bin/bash
# voice_mode.sh on|off|status  — when on, Stop/Notification hooks queue spoken messages for the earbuds.
source "$(dirname "$0")/lib.sh"
case "${1:-status}" in
  on) touch "$VOICE_MODE_FLAG"; log "voice mode on"; echo on ;;
  off) rm -f "$VOICE_MODE_FLAG"; log "voice mode off"; echo off ;;
  *) [[ -f "$VOICE_MODE_FLAG" ]] && echo on || echo off ;;
esac
