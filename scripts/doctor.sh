#!/usr/bin/env bash
# Phase 0 environment doctor — shell wrapper
# Delegates to doctor.py and passes all arguments through.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Prefer the venv Python if it exists
if [ -x "${REPO_ROOT}/.venv/bin/python" ]; then
    exec "${REPO_ROOT}/.venv/bin/python" "${SCRIPT_DIR}/doctor.py" "$@"
fi

exec python3 "${SCRIPT_DIR}/doctor.py" "$@"
