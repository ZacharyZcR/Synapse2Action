#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="synapse2action-eeg:locked-v1"
data_dir="${project_dir}/simulation/vendor/mamem"
report_dir="${project_dir}/reports/eeg"

if ! docker image inspect "${image}" >/dev/null 2>&1; then
  docker build -f "${project_dir}/simulation/docker/Dockerfile.eeg" -t "${image}" "${project_dir}"
fi
mkdir -p "${data_dir}" "${report_dir}"
docker run --rm \
  --env PYTHONPATH=/workspace/current/src \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${data_dir}:/workspace/data" \
  --volume "${report_dir}:/workspace/reports/eeg" \
  "${image}" python simulation/public_ssvep_benchmark.py \
  --data /workspace/data \
  --report /workspace/reports/eeg/public-ssvep.json
