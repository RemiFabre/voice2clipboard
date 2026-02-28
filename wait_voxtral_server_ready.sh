#!/bin/bash
set -euo pipefail

HOST="${VOXTRAL_HOST:-127.0.0.1}"
PORT="${VOXTRAL_PORT:-8000}"
TIMEOUT_S="${1:-600}"

URL="http://${HOST}:${PORT}/v1/models"
START=$(date +%s)

echo "Waiting for Voxtral server at ${URL} (timeout ${TIMEOUT_S}s)..."
while true; do
  if curl -fsS "$URL" >/dev/null 2>&1; then
    echo "Server is ready."
    exit 0
  fi
  NOW=$(date +%s)
  if (( NOW - START > TIMEOUT_S )); then
    echo "Timed out waiting for server readiness." >&2
    exit 1
  fi
  sleep 2
done
