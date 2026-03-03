#!/bin/bash
set -euo pipefail

# Runs local voxmlx realtime server compatible with OpenAI Realtime API.
# Default model follows localvoxtral's recommended quantized Voxtral model.

MODEL="${VOXMLX_MODEL:-T0mSIlver/Voxtral-Mini-4B-Realtime-2602-MLX-4bit}"
SPEC="${VOXMLX_SPEC:-git+https://github.com/T0mSIlver/voxmlx.git@48bfdec9bc4f4f01390b25b0e098deae6dd3ae6c[server]}"
HOST="${VOXMLX_HOST:-127.0.0.1}"
PORT="${VOXMLX_PORT:-8010}"
LOG_FILE="${VOXMLX_SERVER_LOG:-/Users/remi/voice2clipboard/logs/voxmlx_server.log}"
AUTO_INSTALL="${VOXMLX_AUTO_INSTALL:-1}"
PY="${PYTHON_BIN:-python3}"

# Ensure uv/uvx installed by the official installer are discoverable.
export PATH="$HOME/.local/bin:$PATH"

mkdir -p "$(dirname "$LOG_FILE")"

if ! command -v uvx >/dev/null 2>&1; then
  cat >&2 <<'EOF'
uvx is not installed.
Install uv first, then retry:
  curl -LsSf https://astral.sh/uv/install.sh | sh
EOF
  exit 1
fi

echo "Starting voxmlx server on ${HOST}:${PORT}" | tee -a "$LOG_FILE"
echo "Model: ${MODEL}" | tee -a "$LOG_FILE"
echo "Logs: ${LOG_FILE}" | tee -a "$LOG_FILE"
echo "Endpoint should be: ws://${HOST}:${PORT}/v1/realtime" | tee -a "$LOG_FILE"
echo "First run may download model weights." | tee -a "$LOG_FILE"

if ! command -v voxmlx-serve >/dev/null 2>&1; then
  if [[ "$AUTO_INSTALL" == "1" ]] && command -v uv >/dev/null 2>&1; then
    echo "voxmlx-serve not found; installing pinned tool runtime..." | tee -a "$LOG_FILE"
    uv tool install --from "$SPEC" voxmlx-serve >>"$LOG_FILE" 2>&1 || true
  fi
fi

if command -v voxmlx-serve >/dev/null 2>&1; then
  voxmlx-serve \
    --model "$MODEL" \
    --host "$HOST" \
    --port "$PORT" \
    2>&1 | tee -a "$LOG_FILE"
else
  echo "Falling back to uvx ephemeral runtime (${SPEC})." | tee -a "$LOG_FILE"
  uvx --from "$SPEC" \
    voxmlx-serve \
    --model "$MODEL" \
    --host "$HOST" \
    --port "$PORT" \
    2>&1 | tee -a "$LOG_FILE"
fi
