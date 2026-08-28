#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="synapse2action-eeg:locked-v1"
data_dir="${project_dir}/simulation/vendor/mamem-256"
report_dir="${project_dir}/reports/eeg"

if ! docker image inspect "${image}" >/dev/null 2>&1; then
  docker build -f "${project_dir}/simulation/docker/Dockerfile.eeg" -t "${image}" "${project_dir}"
fi
mkdir -p "${data_dir}" "${report_dir}"
mkdir -p "${data_dir}/dataset2"
download_subject() {
  local subject="$1"
  for suffix in dat hea win; do
    file="T${subject}a.${suffix}"
    destination="${data_dir}/dataset2/${file}"
    if [[ ! -s "${destination}" ]]; then
      curl --fail --location --continue-at - --silent --show-error \
        --output "${destination}.part" \
        "https://physionet.org/files/mssvepdb/1.0.0/dataset2/${file}"
      mv "${destination}.part" "${destination}"
    fi
  done
}

pids=()
for subject in 001 002 003 004; do
  download_subject "${subject}" &
  pids+=("$!")
done
for pid in "${pids[@]}"; do
  wait "${pid}"
done
docker run --rm \
  --env PYTHONPATH=/workspace/current/src \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${data_dir}:/workspace/data" \
  --volume "${report_dir}:/workspace/reports/eeg" \
  "${image}" python simulation/public_ssvep_256_benchmark.py \
  --data /workspace/data \
  --report /workspace/reports/eeg/public-ssvep-256.json
