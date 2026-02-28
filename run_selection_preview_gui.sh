#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
source "$VENV"
cd "$ROOT_DIR"
python tools/selection_preview_gui.py --runtime-dir "$ROOT_DIR/runtime/always_on"
