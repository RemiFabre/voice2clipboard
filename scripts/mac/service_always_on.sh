#!/bin/bash
set -euo pipefail

VOXMLX_LABEL="com.voice2clipboard.voxmlx"
DAEMON_LABEL="com.voice2clipboard.alwayson"

cmd="${1:-status}"
uid="$(id -u)"

bootout() {
  local label="$1"
  launchctl bootout "gui/${uid}/${label}" >/dev/null 2>&1 || true
}

bootstrap() {
  local label="$1"
  launchctl bootstrap "gui/${uid}" "$HOME/Library/LaunchAgents/${label}.plist" >/dev/null 2>&1 || true
}

is_loaded() {
  local label="$1"
  launchctl print "gui/${uid}/${label}" >/dev/null 2>&1
}

kickstart() {
  local label="$1"
  launchctl kickstart -k "gui/${uid}/${label}" >/dev/null 2>&1 || true
}

status_one() {
  local label="$1"
  echo "== $label =="
  launchctl print "gui/${uid}/${label}" 2>/dev/null | sed -n '1,30p' || echo "not loaded"
  echo
}

case "$cmd" in
  start)
    if ! is_loaded "$VOXMLX_LABEL"; then
      bootstrap "$VOXMLX_LABEL"
    fi
    if ! is_loaded "$DAEMON_LABEL"; then
      bootstrap "$DAEMON_LABEL"
    fi
    kickstart "$VOXMLX_LABEL"
    kickstart "$DAEMON_LABEL"
    ;;
  stop)
    bootout "$DAEMON_LABEL"
    bootout "$VOXMLX_LABEL"
    ;;
  reload)
    bootout "$DAEMON_LABEL"
    bootout "$VOXMLX_LABEL"
    bootstrap "$VOXMLX_LABEL"
    bootstrap "$DAEMON_LABEL"
    kickstart "$VOXMLX_LABEL"
    kickstart "$DAEMON_LABEL"
    ;;
  status)
    status_one "$VOXMLX_LABEL"
    status_one "$DAEMON_LABEL"
    ;;
  *)
    echo "Usage: $0 {start|stop|reload|status}"
    exit 1
    ;;
esac
