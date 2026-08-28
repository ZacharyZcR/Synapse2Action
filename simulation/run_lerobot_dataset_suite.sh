#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
report_dir="${project_dir}/reports/simulation"
dataset_dir="${report_dir}/lerobot-g1-pick-place-suite"
image="synapse2action-smolvla:0.6.1"
scales=(0.85 0.90 0.95 1.00 1.05)
episodes=()

[[ ! -e "${dataset_dir}" ]] || { echo "dataset already exists: ${dataset_dir}" >&2; exit 2; }
for scale in "${scales[@]}"; do
  name="g1-pick-place-${scale}.npz"
  S2A_RECORD_EPISODE=1 \
  S2A_EPISODE_NAME="${name}" \
  S2A_MANIPULATION_TIME_SCALE="${scale}" \
    "${project_dir}/simulation/run_unitree_pick_place.sh"
  episodes+=("/workspace/reports/simulation/${name}")
done

docker run --rm \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${report_dir}:/workspace/reports/simulation" \
  "${image}" python simulation/convert_g1_episode_to_lerobot.py \
  "${episodes[@]}" \
  /workspace/reports/simulation/lerobot-g1-pick-place-suite \
  --repo-id synapse2action/g1-pick-place-sim-suite \
  --report /workspace/reports/simulation/lerobot-g1-pick-place-suite.json
