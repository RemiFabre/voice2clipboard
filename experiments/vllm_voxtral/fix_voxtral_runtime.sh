#!/bin/bash
set -euo pipefail

METAL_VENV="$HOME/.venv-vllm-metal"
if [[ ! -d "$METAL_VENV" ]]; then
  echo "Missing $METAL_VENV. Run ./experiments/vllm_voxtral/setup_voxtral_runtime.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$METAL_VENV/bin/activate"

python -V
pip install -U pip wheel

# Keep core runtime pinned to vllm-compatible versions.
pip install -U --force-reinstall \
  "vllm==0.16.0" \
  "vllm-metal==0.1.0" \
  "torch==2.10.0" \
  "transformers<5" \
  "setuptools==77.0.3" \
  "mistral-common==1.9.1"

# Critical fix: mlx-vlm must support model_type=voxtral_realtime.
# Install latest release first.
pip install -U mlx-vlm

# Verify model module exists in installed package; otherwise move to GitHub main.
MODEL_DIR="$(python - <<'PY'
import site
import pathlib
for base in site.getsitepackages():
    p = pathlib.Path(base) / "mlx_vlm" / "models" / "voxtral_realtime"
    if p.exists():
        print(p)
        raise SystemExit(0)
print("")
PY
)"

if [[ -z "${MODEL_DIR}" ]]; then
  echo "mlx-vlm release does not include voxtral_realtime module. Installing from GitHub main..."
  pip install -U git+https://github.com/Blaizzy/mlx-vlm.git
fi

# Re-check after GitHub install.
MODEL_DIR="$(python - <<'PY'
import site
import pathlib
for base in site.getsitepackages():
    p = pathlib.Path(base) / "mlx_vlm" / "models" / "voxtral_realtime"
    if p.exists():
        print(p)
        raise SystemExit(0)
print("")
PY
)"

if [[ -z "${MODEL_DIR}" ]]; then
  echo "ERROR: mlx-vlm still lacks voxtral_realtime support after upgrade." >&2
  echo "This means current mlx-vlm upstream does not expose this architecture yet." >&2
  echo "Restoring vllm-compatible core pins..." >&2
  pip install -U --force-reinstall \
    "torch==2.10.0" \
    "transformers<5" \
    "setuptools==77.0.3" >/dev/null
  exit 2
fi
echo "Found voxtral_realtime module at: ${MODEL_DIR}"

# Probe support without importing heavy runtime modules if possible.
python - <<'PY'
import importlib.util
import pkg_resources
print('Installed versions:')
for p in ['vllm','vllm-metal','mlx-vlm','transformers','mistral-common']:
    try:
        print(' -', p, pkg_resources.get_distribution(p).version)
    except Exception:
        print(' -', p, 'not-installed')
print('Done.')
PY

echo
echo "Runtime upgrade complete."
echo "Next: ./experiments/vllm_voxtral/run_voxtral_realtime_server.sh"
