#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"

# shellcheck disable=SC1090
source "$VENV"
cd "$ROOT_DIR"

python voxtral_realtime_client.py "$@"
