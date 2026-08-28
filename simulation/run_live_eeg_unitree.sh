#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="synapse2action-live-eeg:locked-v1-amd64"
report_dir="${project_dir}/reports/eeg"

if ! docker image inspect "${image}" >/dev/null 2>&1; then
  docker build --platform linux/amd64 \
    -f "${project_dir}/simulation/docker/Dockerfile.live-eeg" -t "${image}" "${project_dir}"
fi
mkdir -p "${report_dir}"
docker run --rm \
  --platform linux/amd64 \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${report_dir}:/workspace/reports/eeg" \
  "${image}" python simulation/live_eeg_lsl.py \
  --report /workspace/reports/eeg/live-eeg-lsl.json
PYTHONPATH="${project_dir}/src" python3 "${project_dir}/simulation/run_harness_unitree.py" \
  --task pick-place \
  --destination red_cube \
  --decoded-intents "${report_dir}/live-eeg-lsl.json" \
  --output "${report_dir}/live-eeg-unitree.json"
