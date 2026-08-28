#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"${project_dir}/simulation/run_public_ssvep.sh"
PYTHONPATH="${project_dir}/src" python3 "${project_dir}/simulation/run_harness_unitree.py" \
  --task pick-place \
  --task-spec "${project_dir}/experiments/tasks/g1_pick_place.json" \
  --decoded-intents "${project_dir}/reports/eeg/public-ssvep.json" \
  --output "${project_dir}/reports/eeg/public-ssvep-unitree.json"
