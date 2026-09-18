#!/bin/bash
# Notification ding: may sound at any time, even during a dictation or speech (Remi's choice), but
# not more often than every DING_COOLDOWN_S seconds; the next playback says how many are waiting.
source "$(dirname "$0")/lib.sh"
now="$(date +%s)"; last="$(cat "$DING_STAMP" 2>/dev/null || echo 0)"
if (( now - last < DING_COOLDOWN_S )); then log "ding skipped (cooldown)"; exit 0; fi
echo "$now" >"$DING_STAMP"
afplay "$DING_SOUND" >/dev/null 2>&1 &
