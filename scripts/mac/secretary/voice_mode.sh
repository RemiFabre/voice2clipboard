#!/bin/bash
# voice_mode.sh on|off|status  — when on, Stop/Notification hooks queue spoken messages for the earbuds.
source "$(dirname "$0")/lib.sh"
case "${1:-status}" in
  on) [[ -f "$VOICE_MODE_FLAG" ]] || { touch "$VOICE_MODE_FLAG"; log "voice mode on (headset: notifications enabled)"; }; echo on ;;
  off) [[ -f "$VOICE_MODE_FLAG" ]] && { rm -f "$VOICE_MODE_FLAG"; log "voice mode off (manual: quiet)"; }; echo off ;;
  *) [[ -f "$VOICE_MODE_FLAG" ]] && echo on || echo off ;;
esac
