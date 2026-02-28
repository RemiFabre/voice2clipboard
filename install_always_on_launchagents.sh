#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
VOXMLX_LABEL="com.voice2clipboard.voxmlx"
DAEMON_LABEL="com.voice2clipboard.alwayson"
VOXMLX_PLIST="${LAUNCH_DIR}/${VOXMLX_LABEL}.plist"
DAEMON_PLIST="${LAUNCH_DIR}/${DAEMON_LABEL}.plist"

mkdir -p "$LAUNCH_DIR" "$ROOT_DIR/logs" "$ROOT_DIR/runtime/always_on"

cat > "$VOXMLX_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${VOXMLX_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd ${ROOT_DIR} && ./run_voxmlx_server.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${ROOT_DIR}/logs/launchd_voxmlx.out.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT_DIR}/logs/launchd_voxmlx.err.log</string>
  <key>ProcessType</key>
  <string>Interactive</string>
</dict>
</plist>
EOF

cat > "$DAEMON_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${DAEMON_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd ${ROOT_DIR} && ./run_always_on_voxtral_daemon.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${ROOT_DIR}/logs/launchd_alwayson.out.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT_DIR}/logs/launchd_alwayson.err.log</string>
  <key>ProcessType</key>
  <string>Interactive</string>
</dict>
</plist>
EOF

echo "Installed:"
echo " - $VOXMLX_PLIST"
echo " - $DAEMON_PLIST"
echo
echo "Next:"
echo "  ./service_always_on.sh reload"
