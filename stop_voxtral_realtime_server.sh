#!/bin/bash
set -euo pipefail

pkill -f "vllm serve mistralai/Voxtral-Mini-4B-Realtime-2602" || true
pkill -f "vllm serve .*Voxtral-Mini-4B-Realtime-2602" || true

echo "Requested stop for Voxtral realtime vLLM server processes."
