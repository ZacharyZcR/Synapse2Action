#!/usr/bin/env bash
set -euo pipefail

project="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
isaac="${project}/simulation/vendor/Isaac-GR00T"
wbc="${project}/simulation/vendor/GR00T-WholeBodyControl"
export PYTHONPATH="${wbc}:${PYTHONPATH:-}"

exec "${isaac}/.venv/bin/python" \
  "${wbc}/gear_sonic/scripts/run_vla_inference.py" "$@"
