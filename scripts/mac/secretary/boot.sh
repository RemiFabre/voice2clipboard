#!/bin/bash
# Runs at login (LaunchAgent com.voice2clipboard.secretary): warms the Kokoro voice, makes sure
# the earbud button app is up, and opens the secretary session in iTerm.
source "$(dirname "$0")/lib.sh"
log "boot: login start"
sleep "${SECRETARY_BOOT_DELAY_S:-20}"   # let the desktop, Bluetooth and iTerm settle
"$KOKORO_CTL" kokoro-daemon status >/dev/null 2>&1 || "$KOKORO_CTL" kokoro-daemon start >/dev/null 2>&1 || true
"$ROOT_DIR/scripts/mac/earbuds/ctl.sh" start >/dev/null 2>&1 || true
osascript -e 'tell application "iTerm2" to activate' >/dev/null 2>&1 || true
sleep 3
"$(dirname "$0")/start_secretary.sh" >>"$LOG_FILE" 2>&1
log "boot: done"
