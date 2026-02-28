#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
source "$VENV"
cd "$ROOT_DIR"

if python - <<'PY' >/dev/null 2>&1
import tkinter
PY
then
  python tools/selection_preview_gui.py --runtime-dir "$ROOT_DIR/runtime/always_on"
else
  HOST="127.0.0.1"
  PORT="${VOICE2CLIP_PREVIEW_PORT:-8765}"
  URL="http://${HOST}:${PORT}"
  echo "tkinter unavailable; using web preview at ${URL}"
  (sleep 0.5; open "$URL" >/dev/null 2>&1 || true) &
  exec python tools/selection_preview_web.py --runtime-dir "$ROOT_DIR/runtime/always_on" --host "$HOST" --port "$PORT"
fi
