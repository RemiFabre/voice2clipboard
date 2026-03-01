#!/bin/bash
set -euo pipefail

source /Users/remi/.virtualenvs/voice2clipboard/bin/activate
cd /Users/remi/voice2clipboard

# Usage:
#   ./run_benchmark_full_mac.sh [audio_file]
#   ./run_benchmark_full_mac.sh recordings/2026-02-27/17-09-26/audio.wav
python benchmark_full_mac.py "$@"

