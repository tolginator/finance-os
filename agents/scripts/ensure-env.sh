#!/usr/bin/env bash
# Ensure the finance-os Python environment is ready.
# Source this script: source agents/scripts/ensure-env.sh

__ensure_env_saved_opts="$(set +o)"

__ensure_env_main() {
    set -euo pipefail

    local agents_dir
    agents_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

    if [ ! -d "$agents_dir/.venv" ]; then
        python3 -m venv "$agents_dir/.venv"
    fi

    source "$agents_dir/.venv/bin/activate"
    python -m pip install --quiet -e "$agents_dir[dev]"
}

__ensure_env_main
__ensure_env_rc=$?
eval "$__ensure_env_saved_opts"
unset __ensure_env_saved_opts __ensure_env_rc
return 0 2>/dev/null || exit 0
