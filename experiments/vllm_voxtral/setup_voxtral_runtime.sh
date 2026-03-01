#!/bin/bash
set -euo pipefail

# Installs vllm-metal (which provides vllm CLI) into ~/.venv-vllm-metal
# and installs client deps in the existing voice2clipboard venv.

ROOT_DIR="/Users/remi/voice2clipboard"
VOICE_VENV="/Users/remi/.virtualenvs/voice2clipboard/bin/activate"
METAL_VENV="$HOME/.venv-vllm-metal"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required" >&2
  exit 1
fi

echo "Installing or updating vllm-metal runtime at: $METAL_VENV"
curl -fsSL https://raw.githubusercontent.com/vllm-project/vllm-metal/main/install.sh | bash

if [[ ! -x "$METAL_VENV/bin/vllm" ]]; then
  echo "vllm binary not found in $METAL_VENV/bin after install." >&2
  exit 1
fi

echo "Installing Voxtral realtime client deps in voice2clipboard venv"
# shellcheck disable=SC1090
source "$VOICE_VENV"
pip install -r "$ROOT_DIR/requirements_voxtral.txt"

echo
echo "Setup complete."
echo "Next:"
echo "  1) cd $ROOT_DIR && ./run_voxtral_realtime_server.sh"
echo "  2) cd $ROOT_DIR && ./run_voxtral_realtime_client.sh"
