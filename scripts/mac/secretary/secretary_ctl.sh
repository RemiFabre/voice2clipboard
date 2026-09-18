#!/bin/bash
# secretary_ctl.sh install-boot | uninstall-boot | boot-status | status
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.voice2clipboard.secretary"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="/Users/remi/voice2clipboard/runtime/secretary/boot.log"
case "${1:-status}" in
  install-boot)
    mkdir -p "$(dirname "$LOG")"
    cat >"$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$HERE/boot.sh</string></array>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/remi/.local/bin</string><key>HOME</key><string>/Users/remi</string></dict>
</dict></plist>
PL
    launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
    # bootstrap registers it for future logins; RunAtLoad would also run it right now, so load it
    # with the run suppressed: enable only, it runs at the next login.
    launchctl bootstrap "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
    echo "installed: the secretary, the earbud app and the voice will start at the next login" ;;
  uninstall-boot) launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true; rm -f "$PLIST"; echo "removed" ;;
  boot-status) launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 && echo "boot agent loaded" || echo "boot agent not loaded" ;;
  status) source "$HERE/lib.sh"; s="$(cat "$SESSION_FILE" 2>/dev/null || true)"; if [[ -n "$s" ]] && iterm_session_exists "$s"; then echo "secretary running in iTerm session $s"; else echo "secretary not running"; fi; echo "voice mode: $("$HERE/voice_mode.sh" status)"; "$HERE/../earbuds/ctl.sh" status ;;
  *) echo "usage: $0 install-boot|uninstall-boot|boot-status|status"; exit 1 ;;
esac
