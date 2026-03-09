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
UNINSTALL_SH="$SCRIPTS_MAC_DIR/uninstall_always_on_launchagents.sh"
CLEAR_LOGS_SH="$SCRIPTS_MAC_DIR/clear_runtime_logs.sh"
VOXMLX_HOST="${VOXMLX_HOST:-127.0.0.1}"
VOXMLX_PORT="${VOXMLX_PORT:-8010}"
START_TIMEOUT_S="${VOICE2CLIP_START_TIMEOUT_S:-180}"
START_POLL_S="${VOICE2CLIP_START_POLL_S:-1}"

usage() {
  cat <<'EOF'
Usage: ./voice_control.sh <command>

Core:
  status            Show server/daemon/marker/runtime status
  start             Start background services (server + always-on daemon)
  stop              Stop background services
  restart           Restart background services
  enable-autostart  Install LaunchAgents and reload services
  disable-autostart Stop services and remove LaunchAgents

Capture markers:
  mark-start        Start capture selection window
  mark-stop         Stop selection window and copy selection to clipboard
  mark-status       Show marker + daemon runtime status
  mark-clear        Clear active marker

Logs and diagnostics:
  clear-logs        Stop services and erase logs/transcript history
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

read_daemon_runtime() {
  python3 - "$RUNTIME_DIR/state.json" "$RUNTIME_DIR/daemon.pid" <<'PY'
import json, os, signal, sys

state_path, pid_path = sys.argv[1], sys.argv[2]

connected = False
ts = ""
pid = ""
pid_running = False

if os.path.exists(state_path):
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        connected = bool(state.get("connected"))
        ts = str(state.get("ts", ""))
    except Exception:
        pass

if os.path.exists(pid_path):
    try:
        with open(pid_path, "r", encoding="utf-8") as f:
            pid = f.read().strip()
        if pid:
            os.kill(int(pid), 0)
            pid_running = True
    except Exception:
        pid_running = False

print(f"{int(connected)}|{int(pid_running)}|{pid}|{ts}")
PY
}

wait_for_stack_ready() {
  local timeout_s="$1"
  local poll_s="$2"
  local deadline shell_now tcp_state runtime_state connected pid_running pid ts

  echo "Starting background services..."
  echo "Waiting for realtime server at ${VOXMLX_HOST}:${VOXMLX_PORT} ..."
  deadline="$(python3 - "$timeout_s" <<'PY'
import sys, time
print(time.time() + float(sys.argv[1]))
PY
)"
  while true; do
    tcp_state="$(check_tcp "$VOXMLX_HOST" "$VOXMLX_PORT")"
    if [[ "$tcp_state" == "up" ]]; then
      echo "Realtime server reachable."
      break
    fi
    shell_now="$(python3 - <<'PY'
import time
print(time.time())
PY
)"
    if python3 - "$shell_now" "$deadline" <<'PY'
import sys
sys.exit(0 if float(sys.argv[1]) < float(sys.argv[2]) else 1)
PY
    then
      printf "."
      sleep "$poll_s"
    else
      echo
      echo "Timed out waiting for realtime server." >&2
      echo "Check /Users/remi/voice2clipboard/logs/voxmlx_server.log" >&2
      return 1
    fi
  done

  echo "Waiting for daemon connection ..."
  while true; do
    runtime_state="$(read_daemon_runtime)"
    IFS='|' read -r connected pid_running pid ts <<<"$runtime_state"
    if [[ "$connected" == "1" && "$pid_running" == "1" ]]; then
      echo "Daemon connected (pid=${pid:-unknown})."
      return 0
    fi
    shell_now="$(python3 - <<'PY'
import time
print(time.time())
PY
)"
    if python3 - "$shell_now" "$deadline" <<'PY'
import sys
sys.exit(0 if float(sys.argv[1]) < float(sys.argv[2]) else 1)
PY
    then
      printf "."
      sleep "$poll_s"
    else
      echo
      echo "Timed out waiting for daemon connection." >&2
      echo "State file: /Users/remi/voice2clipboard/runtime/always_on/state.json" >&2
      echo "Log file: /Users/remi/voice2clipboard/logs/always_on_voxtral_daemon.log" >&2
      return 1
    fi
  done
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
    wait_for_stack_ready "$START_TIMEOUT_S" "$START_POLL_S"
    ;;
  stop)
    "$SERVICE_SH" stop
    ;;
  restart)
    "$SERVICE_SH" reload
    wait_for_stack_ready "$START_TIMEOUT_S" "$START_POLL_S"
    ;;
  enable-autostart)
    "$INSTALL_SH"
    "$SERVICE_SH" reload
    wait_for_stack_ready "$START_TIMEOUT_S" "$START_POLL_S"
    ;;
  disable-autostart)
    "$UNINSTALL_SH"
    ;;
  clear-logs)
    "$CLEAR_LOGS_SH"
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
