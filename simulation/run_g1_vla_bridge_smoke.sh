#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "${project_dir}/reports/simulation"
docker run --rm \
  --env MUJOCO_GL=osmesa \
  --env PYTHONPATH=/workspace/current/src \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${project_dir}/reports/simulation:/workspace/reports/simulation" \
  --workdir /workspace/current \
  synapse2action-unitree-render:locked-v3 \
  python3 simulation/g1_vla_bridge_smoke.py \
  --unitree-mujoco /opt/unitree/unitree_mujoco \
  --task-spec /workspace/current/experiments/tasks/g1_pick_place.json \
  --output /workspace/reports/simulation/g1-vla-bridge-smoke.json
