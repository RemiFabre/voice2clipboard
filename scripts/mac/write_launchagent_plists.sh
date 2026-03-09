#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
TARGET_DIR="${1:-$ROOT_DIR/runtime/launchagents}"
VOXMLX_LABEL="com.voice2clipboard.voxmlx"
DAEMON_LABEL="com.voice2clipboard.alwayson"
VOXMLX_PLIST="${TARGET_DIR}/${VOXMLX_LABEL}.plist"
DAEMON_PLIST="${TARGET_DIR}/${DAEMON_LABEL}.plist"

mkdir -p "$TARGET_DIR" "$ROOT_DIR/logs" "$ROOT_DIR/runtime/always_on"

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
    <string>cd ${ROOT_DIR} &amp;&amp; ./scripts/mac/run_voxmlx_server.sh</string>
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
    <string>cd ${ROOT_DIR} &amp;&amp; ./scripts/mac/run_always_on_voxtral_daemon.sh</string>
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

echo "Wrote:"
echo " - $VOXMLX_PLIST"
echo " - $DAEMON_PLIST"
