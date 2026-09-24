#!/bin/bash
# Notification ding: may sound during speech (Remi's choice, 2026-09-18) but no longer into a
# running dictation (Remi, 2026-09-23, after a dictation was disturbed while he spoke): it waits
# for the recording to end. Not more often than every DING_COOLDOWN_S seconds; the next playback
# says how many are waiting.
source "$(dirname "$0")/lib.sh"
if dictation_active && [[ "${DING_DEFERRED:-0}" != "1" ]]; then
  log "ding held: a dictation is running"
  DING_DEFERRED=1 nohup bash -c 'source "$1/lib.sh"; wait_for_dictation_end; exec "$1/ding.sh"' _ "$(cd "$(dirname "$0")" && pwd)" >/dev/null 2>&1 &
  exit 0
fi
now="$(date +%s)"; last="$(cat "$DING_STAMP" 2>/dev/null || echo 0)"
# He was told "Not ready yet." and is waiting for exactly this ding: the cooldown does not apply.
owed=0; [[ -f "$DING_OWED" ]] && { owed=1; rm -f "$DING_OWED"; }
if (( owed == 0 && now - last < DING_COOLDOWN_S )); then log "ding skipped (cooldown)"; exit 0; fi
echo "$now" >"$DING_STAMP"
log "ding"
ensure_audible --report   # a ding into a muted headset is flagged, not forced: the zero may be deliberate
play_cue "$DING_SOUND"
