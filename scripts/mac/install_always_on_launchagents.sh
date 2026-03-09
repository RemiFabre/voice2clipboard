#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
RUNTIME_LAUNCH_DIR="$ROOT_DIR/runtime/launchagents"
VOXMLX_LABEL="com.voice2clipboard.voxmlx"
DAEMON_LABEL="com.voice2clipboard.alwayson"
VOXMLX_PLIST="${LAUNCH_DIR}/${VOXMLX_LABEL}.plist"
DAEMON_PLIST="${LAUNCH_DIR}/${DAEMON_LABEL}.plist"
SOURCE_VOXMLX_PLIST="${RUNTIME_LAUNCH_DIR}/${VOXMLX_LABEL}.plist"
SOURCE_DAEMON_PLIST="${RUNTIME_LAUNCH_DIR}/${DAEMON_LABEL}.plist"
WRITE_PLISTS_SH="$ROOT_DIR/scripts/mac/write_launchagent_plists.sh"

mkdir -p "$LAUNCH_DIR" "$ROOT_DIR/logs" "$ROOT_DIR/runtime/always_on"
"$WRITE_PLISTS_SH" "$RUNTIME_LAUNCH_DIR" >/dev/null

cp "$SOURCE_VOXMLX_PLIST" "$VOXMLX_PLIST"
cp "$SOURCE_DAEMON_PLIST" "$DAEMON_PLIST"

echo "Installed:"
echo " - $VOXMLX_PLIST"
echo " - $DAEMON_PLIST"
echo
echo "Next:"
echo "  ./scripts/mac/service_always_on.sh reload"
