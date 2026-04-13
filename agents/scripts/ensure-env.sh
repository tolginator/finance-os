#!/usr/bin/env bash
# Ensure the finance-os Python environment is ready.
# Source this script: source agents/scripts/ensure-env.sh
set -euo pipefail

AGENTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -d "$AGENTS_DIR/.venv" ]; then
    python3 -m venv "$AGENTS_DIR/.venv"
    source "$AGENTS_DIR/.venv/bin/activate"
    pip install -e "$AGENTS_DIR[dev]"
else
    source "$AGENTS_DIR/.venv/bin/activate"
fi
