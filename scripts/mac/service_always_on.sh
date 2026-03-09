#!/bin/bash
set -euo pipefail

VOXMLX_LABEL="com.voice2clipboard.voxmlx"
DAEMON_LABEL="com.voice2clipboard.alwayson"
RUNTIME_DIR="/Users/remi/voice2clipboard/runtime/always_on"
ROOT_DIR="/Users/remi/voice2clipboard"
RUNTIME_LAUNCH_DIR="${ROOT_DIR}/runtime/launchagents"
VOXMLX_PLIST="${RUNTIME_LAUNCH_DIR}/${VOXMLX_LABEL}.plist"
DAEMON_PLIST="${RUNTIME_LAUNCH_DIR}/${DAEMON_LABEL}.plist"
WRITE_PLISTS_SH="${ROOT_DIR}/scripts/mac/write_launchagent_plists.sh"

cmd="${1:-status}"
uid="$(id -u)"

bootout() {
  local label="$1"
  launchctl bootout "gui/${uid}/${label}" >/dev/null 2>&1 || true
}

bootstrap() {
  local label="$1"
  local plist="$2"
  if [[ ! -f "$plist" ]]; then
    "$WRITE_PLISTS_SH" "$RUNTIME_LAUNCH_DIR" >/dev/null
  fi
  if [[ ! -f "$plist" ]]; then
    echo "Missing LaunchAgent plist: $plist" >&2
    return 1
  fi
  launchctl bootstrap "gui/${uid}" "$plist" >/dev/null 2>&1
}

is_loaded() {
  local label="$1"
  launchctl print "gui/${uid}/${label}" >/dev/null 2>&1
}

kickstart() {
  local label="$1"
  launchctl kickstart -k "gui/${uid}/${label}" >/dev/null 2>&1 || true
}

kill_stray_daemon() {
  pkill -f "tools/always_on_voxtral_daemon.py" >/dev/null 2>&1 || true
  rm -f "${RUNTIME_DIR}/daemon.pid" >/dev/null 2>&1 || true
}

status_one() {
  local label="$1"
  echo "== $label =="
  launchctl print "gui/${uid}/${label}" 2>/dev/null | sed -n '1,30p' || echo "not loaded"
  echo
}

case "$cmd" in
  start)
    kill_stray_daemon
    if ! is_loaded "$VOXMLX_LABEL"; then
      bootstrap "$VOXMLX_LABEL" "$VOXMLX_PLIST"
    fi
    if ! is_loaded "$DAEMON_LABEL"; then
      bootstrap "$DAEMON_LABEL" "$DAEMON_PLIST"
    fi
    kickstart "$VOXMLX_LABEL"
    kickstart "$DAEMON_LABEL"
    ;;
  stop)
    bootout "$DAEMON_LABEL"
    bootout "$VOXMLX_LABEL"
    kill_stray_daemon
    ;;
  reload)
    bootout "$DAEMON_LABEL"
    bootout "$VOXMLX_LABEL"
    kill_stray_daemon
    bootstrap "$VOXMLX_LABEL" "$VOXMLX_PLIST"
    bootstrap "$DAEMON_LABEL" "$DAEMON_PLIST"
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
