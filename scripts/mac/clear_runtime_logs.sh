#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
LOG_DIR="$ROOT_DIR/logs"
RUNTIME_DIR="$ROOT_DIR/runtime/always_on"
TIMELINE_DIR="$RUNTIME_DIR/timeline"
SERVICE_SH="$ROOT_DIR/scripts/mac/service_always_on.sh"

"$SERVICE_SH" stop >/dev/null 2>&1 || true

rm -f \
  "$LOG_DIR"/*.log \
  "$RUNTIME_DIR"/daemon.pid \
  "$RUNTIME_DIR"/state.json \
  "$RUNTIME_DIR"/selection_marker.json \
  "$RUNTIME_DIR"/events.jsonl \
  "$RUNTIME_DIR"/segments.jsonl \
  "$RUNTIME_DIR"/deltas.jsonl \
  "$RUNTIME_DIR"/selections.jsonl \
  "$RUNTIME_DIR"/feedback_latency.jsonl \
  "$RUNTIME_DIR"/toggle.log \
  "$RUNTIME_DIR"/toggle.last \
  "$RUNTIME_DIR"/live_text.txt \
  "$RUNTIME_DIR"/last_selection.txt

rm -f "$TIMELINE_DIR"/*.txt

mkdir -p "$LOG_DIR" "$RUNTIME_DIR" "$TIMELINE_DIR"

echo "Cleared repo-managed logs and transcript history:"
echo " - $LOG_DIR/*.log"
echo " - $RUNTIME_DIR/{state,events,segments,deltas,selections,feedback_latency,toggle,live_text,last_selection,selection_marker,daemon.pid}"
echo " - $TIMELINE_DIR/*.txt"
echo
echo "Services were stopped first. Use ./voice_control.sh start when you want to resume."
