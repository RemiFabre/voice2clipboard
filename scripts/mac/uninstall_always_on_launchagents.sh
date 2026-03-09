#!/bin/bash
set -euo pipefail

LAUNCH_DIR="$HOME/Library/LaunchAgents"
VOXMLX_LABEL="com.voice2clipboard.voxmlx"
DAEMON_LABEL="com.voice2clipboard.alwayson"
VOXMLX_PLIST="${LAUNCH_DIR}/${VOXMLX_LABEL}.plist"
DAEMON_PLIST="${LAUNCH_DIR}/${DAEMON_LABEL}.plist"
uid="$(id -u)"

bootout() {
  local label="$1"
  launchctl bootout "gui/${uid}/${label}" >/dev/null 2>&1 || true
}

bootout "$DAEMON_LABEL"
bootout "$VOXMLX_LABEL"

rm -f "$DAEMON_PLIST" "$VOXMLX_PLIST"

echo "Removed:"
echo " - $VOXMLX_PLIST"
echo " - $DAEMON_PLIST"
echo
echo "Autostart disabled."
