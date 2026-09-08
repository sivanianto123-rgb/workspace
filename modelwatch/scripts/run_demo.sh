#!/usr/bin/env bash
# End-to-end ModelWatch demo. Thin wrapper around scripts/demo.py.
#
#   ./scripts/run_demo.sh                # default (port 5057)
#   ./scripts/run_demo.sh --port 5099 --delay 0.05
#
# Runs in well under 2 minutes and narrates every step to the console.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
cd "$ROOT"

# Prefer the project virtualenv if present.
if [[ -x ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
else
  PY="$(command -v python3 || command -v python)"
fi

echo "Using interpreter: $PY"
exec "$PY" scripts/demo.py "$@"
