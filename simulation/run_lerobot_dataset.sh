#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="synapse2action-smolvla:0.6.1"
report_dir="${project_dir}/reports/simulation"
dataset_dir="${report_dir}/lerobot-g1-pick-place"

if [[ -e "${dataset_dir}" ]]; then
  echo "dataset already exists: ${dataset_dir}" >&2
  exit 2
fi
S2A_RECORD_EPISODE=1 "${project_dir}/simulation/run_unitree_pick_place.sh"
docker run --rm \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${report_dir}:/workspace/reports/simulation" \
  "${image}" python simulation/convert_g1_episode_to_lerobot.py \
  /workspace/reports/simulation/g1-pick-place-episode.npz \
  /workspace/reports/simulation/lerobot-g1-pick-place \
  --report /workspace/reports/simulation/lerobot-g1-pick-place.json
