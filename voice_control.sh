#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
RUNTIME_DIR="$ROOT_DIR/runtime/always_on"
SCRIPTS_MAC_DIR="$ROOT_DIR/scripts/mac"
SERVICE_SH="$SCRIPTS_MAC_DIR/service_always_on.sh"
START_SH="$SCRIPTS_MAC_DIR/always_on_mark_start.sh"
STOP_SH="$SCRIPTS_MAC_DIR/always_on_mark_stop.sh"
STATUS_SH="$SCRIPTS_MAC_DIR/always_on_status.sh"
INSTALL_SH="$SCRIPTS_MAC_DIR/install_always_on_launchagents.sh"
VOXMLX_HOST="${VOXMLX_HOST:-127.0.0.1}"
VOXMLX_PORT="${VOXMLX_PORT:-8010}"

usage() {
  cat <<'EOF'
Usage: ./voice_control.sh <command>

Core:
  status            Show server/daemon/marker/runtime status
  start             Start background services (server + always-on daemon)
  stop              Stop background services
  restart           Restart background services
  enable-autostart  Install LaunchAgents and reload services

Capture markers:
  mark-start        Start capture selection window
  mark-stop         Stop selection window and copy selection to clipboard
  mark-status       Show marker + daemon runtime status
  mark-clear        Clear active marker

Logs and diagnostics:
  logs              Tail key logs
  files             Show key runtime files
  live              Open live transcript files in VS Code
  live-ts           Open timestamped daily timeline in VS Code
  live-tail         Tail live transcript in terminal
  preview           Open temporary selection preview GUI
  hotkey-last       Show latest hotkey toggle events
EOF
}

check_tcp() {
  python3 - "$1" "$2" <<'PY'
import socket, sys
host = sys.argv[1]
port = int(sys.argv[2])
ok = False
for _ in range(3):
    s = socket.socket()
    s.settimeout(0.7)
    try:
        s.connect((host, port))
        ok = True
        break
    except Exception:
        pass
    finally:
        s.close()
print("up" if ok else "unreachable")
PY
}

show_files() {
  echo "Key runtime files:"
  ls -lh \
    "$RUNTIME_DIR/state.json" \
    "$RUNTIME_DIR/live_text.txt" \
    "$RUNTIME_DIR/segments.jsonl" \
    "$RUNTIME_DIR/last_selection.txt" \
    "$RUNTIME_DIR/selection_marker.json" \
    "$RUNTIME_DIR/feedback_latency.jsonl" 2>/dev/null || true
  echo
  echo "Daily timeline files:"
  ls -lh "$RUNTIME_DIR/timeline"/*.txt 2>/dev/null || echo "none yet"
}

cmd="${1:-status}"

case "$cmd" in
  status)
    echo "== LaunchAgents =="
    "$SERVICE_SH" status || true
    echo "== Runtime status =="
    "$STATUS_SH" || true
    echo
    echo "== TCP check =="
    echo "voxmlx ${VOXMLX_HOST}:${VOXMLX_PORT} (best-effort): $(check_tcp "$VOXMLX_HOST" "$VOXMLX_PORT")"
    ;;
  start)
    "$SERVICE_SH" start
    ;;
  stop)
    "$SERVICE_SH" stop
    ;;
  restart)
    "$SERVICE_SH" reload
    ;;
  enable-autostart)
    "$INSTALL_SH"
    "$SERVICE_SH" reload
    ;;
  mark-start)
    "$START_SH"
    ;;
  mark-stop)
    "$STOP_SH"
    ;;
  mark-status)
    "$STATUS_SH"
    ;;
  mark-clear)
    cd "$ROOT_DIR"
    python3 tools/always_on_capture.py clear --runtime-dir "$RUNTIME_DIR"
    ;;
  logs)
    echo "Tailing logs (Ctrl+C to stop)..."
    tail -n 80 -f \
      "$ROOT_DIR/logs/voxmlx_server.log" \
      "$ROOT_DIR/logs/always_on_voxtral_daemon.log" \
      "$ROOT_DIR/logs/launchd_voxmlx.err.log" \
      "$ROOT_DIR/logs/launchd_alwayson.err.log"
    ;;
  live)
    day="$(date +%Y-%m-%d)"
    timeline="$RUNTIME_DIR/timeline/${day}.txt"
    mkdir -p "$RUNTIME_DIR/timeline"
    touch "$RUNTIME_DIR/live_text.txt" "$timeline"
    echo "Opening live transcript files..."
    echo "(timestamped view = timeline file)"
    echo "- $RUNTIME_DIR/live_text.txt"
    echo "- $timeline"
    if command -v code >/dev/null 2>&1; then
      code -r "$timeline" "$RUNTIME_DIR/live_text.txt" >/dev/null 2>&1 || true
    else
      open -a "Visual Studio Code" "$timeline" "$RUNTIME_DIR/live_text.txt" >/dev/null 2>&1 || true
    fi
    ;;
  live-ts)
    day="$(date +%Y-%m-%d)"
    timeline="$RUNTIME_DIR/timeline/${day}.txt"
    mkdir -p "$RUNTIME_DIR/timeline"
    touch "$timeline"
    echo "Opening timestamped timeline..."
    echo "- $timeline"
    if command -v code >/dev/null 2>&1; then
      code -r "$timeline" >/dev/null 2>&1 || true
    else
      open -a "Visual Studio Code" "$timeline" >/dev/null 2>&1 || true
    fi
    ;;
  live-tail)
    day="$(date +%Y-%m-%d)"
    timeline="$RUNTIME_DIR/timeline/${day}.txt"
    mkdir -p "$RUNTIME_DIR/timeline"
    touch "$RUNTIME_DIR/live_text.txt" "$timeline"
    echo "Tailing live transcript files (Ctrl+C to stop)..."
    echo "- $RUNTIME_DIR/live_text.txt"
    echo "- $timeline"
    tail -n 80 -f "$RUNTIME_DIR/live_text.txt" "$timeline"
    ;;
  preview)
    "$SCRIPTS_MAC_DIR/run_selection_preview_gui.sh"
    ;;
  files)
    show_files
    ;;
  hotkey-last)
    log="$RUNTIME_DIR/toggle.log"
    if [[ -f "$log" ]]; then
      echo "Latest hotkey events:"
      tail -n 20 "$log"
    else
      echo "No toggle log yet: $log"
    fi
    ;;
  *)
    usage
    exit 1
    ;;
esac
