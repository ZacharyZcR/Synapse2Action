#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="synapse2action-smolvla:0.6.1"
cache_dir="${project_dir}/simulation/vendor/huggingface"
report_dir="${project_dir}/reports/simulation"

mkdir -p "${cache_dir}" "${report_dir}"
if ! docker image inspect "${image}" >/dev/null 2>&1; then
  docker build -f "${project_dir}/simulation/docker/Dockerfile.smolvla" -t "${image}" "${project_dir}"
fi
docker run --rm \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${cache_dir}:/root/.cache/huggingface" \
  --volume "${report_dir}:/workspace/reports/simulation" \
  --env PYTHONPATH=/workspace/current/src \
  "${image}" python simulation/smolvla_inference_smoke.py \
  --task-spec /workspace/current/experiments/tasks/g1_pick_place.json \
  --output /workspace/reports/simulation/smolvla-smoke.json
