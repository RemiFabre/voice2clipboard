#!/bin/bash
# Plays a cue and checks afterwards that it really reached the headset; replays it when it did not.
# Usage: play_cue_verified.sh <sound file> [label]        (returns at once; works detached)
#        play_cue_verified.sh --analyze <afplay pid> <log file>   -> prints played|stalled|unknown
#
# Why: when the microphone of a dictation opens, macOS's Bluetooth audio layer sometimes takes a
# "StartIO bypass" path and then miscounts the streams open on the headset (7 of about 17
# recordings on 2026-09-19, short and long alike). For those recordings the stop cue's stream is
# accepted but never runs: coreaudiod stops it "after 320 frames", one buffer, and nothing is
# heard. Remi then has no confirmation that his dictation was taken. The audio daemon's log tells
# us exactly that, so: play, read the log for our afplay, replay if its stream never ran.
source "$(dirname "$0")/lib.sh"
STALL_MAX_FRAMES="${CUE_STALL_MAX_FRAMES:-1600}"   # a played cue runs for 10 000+ frames; a stalled one for 320

analyze() {   # $1 = afplay pid, stdin = coreaudiod log lines
  awk -v pid="$1" -v max="$STALL_MAX_FRAMES" '
    index($0, "(PID=" pid ",") && match($0, /clientID=[0-9]+/) { clients[substr($0, RSTART + 9, RLENGTH - 9)] = 1; next }
    match($0, /IO Stopped Context [0-9]+ after [0-9]+ frames/) {
      split(substr($0, RSTART, RLENGTH), w, " "); ctx[NR] = w[4]; fr[NR] = w[6] + 0 }
    END {
      best = -1
      for (i in ctx) if (ctx[i] in clients && fr[i] > best) best = fr[i]
      if (best < 0) print "unknown"; else if (best <= max) print "stalled"; else print "played"
    }'
}
if [[ "${1:-}" == "--analyze" ]]; then analyze "$2" <"$3"; exit 0; fi

sound="${1:?sound file}"; label="${2:-$(basename "$sound" .aiff)}"
[[ "${SECRETARY_CUES_MUTED:-0}" == "1" ]] && exit 0
(
  attempt=0
  while :; do
    started="$(date '+%Y-%m-%d %H:%M:%S')"
    afplay "$sound" >/dev/null 2>&1 & pid=$!
    wait "$pid"
    sleep 0.3   # let coreaudiod write its "IO Stopped" line
    verdict="$(/usr/bin/log show --style compact --info --debug --start "$started" \
      --predicate 'process == "coreaudiod" AND (eventMessage CONTAINS "BluetoothHALPlugIn_" OR eventMessage CONTAINS "IO Stopped Context")' 2>/dev/null | analyze "$pid")"
    if [[ "$verdict" != "stalled" ]]; then
      [[ "$attempt" -gt 0 ]] && log "cue $label: replay $attempt $verdict"
      break
    fi
    attempt=$((attempt + 1))
    if [[ "$attempt" -gt 2 ]]; then log "cue $label: still not played after 2 replays, giving up"; break; fi
    log "cue $label: its audio stream never ran (headset route stalled), replaying ($attempt)"
    sleep 0.5
  done
) >/dev/null 2>&1 &
disown 2>/dev/null || true
