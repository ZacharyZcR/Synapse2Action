#!/usr/bin/env bash
set -euo pipefail

project="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python="${project}/simulation/vendor/Isaac-GR00T/.venv/bin/python"
server="${project}/simulation/vendor/Isaac-GR00T/gr00t/eval/run_gr00t_server.py"
model="${S2A_GROOT_N17_MODEL_DIR:-${project}/simulation/vendor/models/GR00T-N1.7-3B}"

python3 "${project}/simulation/check_groot_n17_readiness.py" --check-access
exec "${python}" "${server}" \
  --model-path "${model}" \
  --embodiment-tag UNITREE_G1_SONIC \
  --device "${S2A_GROOT_N17_DEVICE:-cuda:0}" \
  --host "${S2A_GROOT_N17_HOST:-127.0.0.1}" \
  --port "${S2A_GROOT_N17_PORT:-5550}"
