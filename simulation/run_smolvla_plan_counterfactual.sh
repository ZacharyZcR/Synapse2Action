#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="synapse2action-smolvla:0.6.1"
cache="${project_dir}/simulation/vendor/huggingface"
model=/workspace/reports/training/smolvla-g1-suite/checkpoints/last/pretrained_model
episode=/workspace/reports/simulation/g1-pick-place-1.05.npz
report=/workspace/reports/simulation/g1-smolvla-plan-counterfactual.json

docker run --rm \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${cache}:/root/.cache/huggingface" \
  --volume "${project_dir}/reports:/workspace/reports" \
  --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
  "${image}" python simulation/evaluate_smolvla_plan_counterfactual.py \
  "${model}" "${episode}" --report "${report}"
