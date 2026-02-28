#!/bin/bash
set -euo pipefail

ROOT_DIR="/Users/remi/voice2clipboard"
VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
OUT_DIR="${ROOT_DIR}/benchmarks"
TS="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="${OUT_DIR}/realtime_backends_${TS}.json"

source "$VENV"
cd "$ROOT_DIR"

python tools/benchmark_realtime_backends.py \
  --output "$OUT_FILE" \
  "$@"

echo "Saved benchmark report: $OUT_FILE"
