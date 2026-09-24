#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export MOCK_SECTORS="${MOCK_SECTORS:-1}"
source .venv/bin/activate 2>/dev/null || true
exec python -m uvicorn alpha_bias_agent.app:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
