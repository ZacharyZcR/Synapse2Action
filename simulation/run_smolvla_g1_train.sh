#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="synapse2action-smolvla:0.6.1"
dataset="${project_dir}/reports/simulation/lerobot-g1-pick-place"
episode="${project_dir}/reports/simulation/g1-pick-place-episode.npz"
output="${project_dir}/reports/training/smolvla-g1"
cache="${project_dir}/simulation/vendor/huggingface"
steps="${S2A_TRAIN_STEPS:-1}"

[[ -f "${dataset}/meta/info.json" ]] || { echo "missing LeRobot dataset: ${dataset}" >&2; exit 2; }
[[ -f "${episode}" ]] || { echo "missing recorded episode: ${episode}" >&2; exit 2; }
mkdir -p "${project_dir}/reports/training"

docker run --rm \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${cache}:/root/.cache/huggingface:ro" \
  --volume "${project_dir}/reports/simulation:/workspace/reports/simulation:ro" \
  --volume "${project_dir}/reports/training:/workspace/reports/training" \
  --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
  "${image}" lerobot-train \
  --dataset.repo_id=synapse2action/g1-pick-place-sim \
  --dataset.root=/workspace/reports/simulation/lerobot-g1-pick-place \
  --policy.path=lerobot/smolvla_base \
  --policy.input_features=null \
  --policy.output_features=null \
  --policy.repo_id=synapse2action/smolvla-g1-sim \
  --policy.push_to_hub=false \
  --output_dir=/workspace/reports/training/smolvla-g1 \
  --job_name=smolvla-g1 \
  --steps="${steps}" \
  --batch_size=1 \
  --num_workers=0 \
  --log_freq=1 \
  --save_freq="${steps}" \
  --wandb.enable=false \
  --policy.device=cpu

docker run --rm \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${cache}:/root/.cache/huggingface:ro" \
  --volume "${project_dir}/reports:/workspace/reports" \
  --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
  "${image}" python simulation/validate_smolvla_g1_checkpoint.py \
  /workspace/reports/training/smolvla-g1/checkpoints/last/pretrained_model \
  /workspace/reports/simulation/g1-pick-place-episode.npz \
  --report /workspace/reports/training/smolvla-g1.json
