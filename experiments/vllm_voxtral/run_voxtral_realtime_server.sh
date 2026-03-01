#!/bin/bash
set -euo pipefail

MODEL="${VOXTRAL_MODEL:-mistralai/Voxtral-Mini-4B-Realtime-2602}"
PORT="${VOXTRAL_PORT:-8000}"
HOST="${VOXTRAL_HOST:-127.0.0.1}"
LOG_FILE="${VOXTRAL_SERVER_LOG:-/Users/remi/voice2clipboard/logs/voxtral_vllm_server.log}"
ALLOW_UNSUPPORTED="${VOXTRAL_ALLOW_UNSUPPORTED:-0}"

# Prefer dedicated vllm-metal environment if present.
if [[ -d "$HOME/.venv-vllm-metal" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.venv-vllm-metal/bin/activate"
fi

if ! command -v vllm >/dev/null 2>&1; then
  echo "vllm CLI not found. Install vllm/vllm-metal first." >&2
  echo "See /Users/remi/voice2clipboard/docs/research/VOXTRAL_REALTIME_DEEP_DIVE.md" >&2
  exit 1
fi

mkdir -p "$(dirname "$LOG_FILE")"

echo "Starting Voxtral Realtime server on ${HOST}:${PORT}" | tee -a "$LOG_FILE"
echo "Model: ${MODEL}" | tee -a "$LOG_FILE"
echo "Logs: ${LOG_FILE}" | tee -a "$LOG_FILE"
echo "First run can take a while (model download + compile/init)." | tee -a "$LOG_FILE"
echo "Server is ready when /v1/models responds." | tee -a "$LOG_FILE"
echo "Runtime versions:" | tee -a "$LOG_FILE"
python - <<'PYVERS' 2>/dev/null | tee -a "$LOG_FILE" || true
import pkg_resources
for p in ["vllm", "vllm-metal", "mlx-vlm", "transformers", "mistral-common"]:
    try:
        print(f" - {p}: {pkg_resources.get_distribution(p).version}")
    except Exception:
        print(f" - {p}: n/a")
PYVERS

# Preflight: mlx-vlm must provide voxtral_realtime model adapter for metal path.
if [[ "${ALLOW_UNSUPPORTED}" != "1" ]]; then
  if ! python - <<'PYCHK' >/dev/null 2>&1
import pathlib
import site
ok = False
for base in site.getsitepackages():
    p = pathlib.Path(base) / "mlx_vlm" / "models" / "voxtral_realtime"
    if p.exists():
        ok = True
        break
raise SystemExit(0 if ok else 1)
PYCHK
  then
    echo "ERROR: mlx-vlm runtime does not provide voxtral_realtime support." | tee -a "$LOG_FILE" >&2
    echo "Try: ./fix_voxtral_runtime.sh" | tee -a "$LOG_FILE" >&2
    echo "If this still fails, upstream support is missing for this runtime stack." | tee -a "$LOG_FILE" >&2
    echo "Set VOXTRAL_ALLOW_UNSUPPORTED=1 to bypass this check (not recommended)." | tee -a "$LOG_FILE" >&2
    exit 2
  fi
fi

EXTRA_SERVER_ARGS=""
if [[ "${VOXTRAL_DISABLE_METAL:-0}" == "1" ]]; then
  echo "VOXTRAL_DISABLE_METAL=1 -> forcing CPU fallback (no metal plugin)." | tee -a "$LOG_FILE"
  export VLLM_PLUGINS=""
fi

# Model-card aligned defaults:
# - temperature=0.0 will be sent from client session.update
# - 480ms transcription delay comes from model tokenizer config (tekken.json)
# - keep default max-model-len unless user overrides via VOXTRAL_EXTRA_ARGS
VLLM_DISABLE_COMPILE_CACHE=1 \
  vllm serve "$MODEL" \
    --host "$HOST" \
    --port "$PORT" \
    --enforce-eager \
    ${EXTRA_SERVER_ARGS} \
    ${VOXTRAL_EXTRA_ARGS:-} \
    2>&1 | tee -a "$LOG_FILE"
