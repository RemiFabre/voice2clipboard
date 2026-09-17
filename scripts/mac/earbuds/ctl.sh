#!/bin/bash
# ctl.sh install|start|stop|restart|status|logs|reassert  — manages the EarbudButtons launch agent.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.voice2clipboard.earbuds"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
APP_BIN="/Users/remi/voice2clipboard/runtime/earbuds/EarbudButtons.app/Contents/MacOS/EarbudButtons"
LOG="/Users/remi/voice2clipboard/runtime/secretary/earbuds.log"
mkdir -p "$(dirname "$LOG")"

write_plist() {
  cat >"$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$APP_BIN</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOG.launchd.out</string>
  <key>StandardErrorPath</key><string>$LOG.launchd.err</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
</dict></plist>
PL
}
pid() { pgrep -f "EarbudButtons.app/Contents/MacOS/EarbudButtons" || true; }
case "${1:-status}" in
  install) "$HERE/build.sh"; write_plist; launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
           launchctl bootstrap "gui/$(id -u)" "$PLIST"; sleep 1; echo "installed, pid=$(pid)" ;;
  start)   launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl kickstart "gui/$(id -u)/$LABEL"; sleep 1; echo "pid=$(pid)" ;;
  stop)    launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true; echo stopped ;;
  restart) "$0" stop; "$0" start ;;
  status)  p="$(pid)"; if [[ -n "$p" ]]; then echo "running pid=$p"; else echo "not running"; fi ;;
  logs)    tail -n "${2:-30}" "$LOG" ;;
  reassert) p="$(pid)"; [[ -n "$p" ]] && kill -USR1 "$p" && echo "re-asserted Now Playing" ;;
  *) echo "usage: $0 install|start|stop|restart|status|logs|reassert"; exit 1 ;;
esac
