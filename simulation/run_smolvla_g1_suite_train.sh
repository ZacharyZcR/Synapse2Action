#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="synapse2action-smolvla:0.6.1"
dataset="${project_dir}/reports/simulation/lerobot-g1-pick-place-suite"
output="${project_dir}/reports/training/smolvla-g1-suite"
cache="${project_dir}/simulation/vendor/huggingface"
steps="${S2A_TRAIN_STEPS:-560}"

[[ -f "${dataset}/meta/info.json" ]] || { echo "missing LeRobot suite: ${dataset}" >&2; exit 2; }
mkdir -p "${project_dir}/reports/training"

docker run --rm \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${cache}:/root/.cache/huggingface" \
  --volume "${project_dir}/reports/simulation:/workspace/reports/simulation:ro" \
  --volume "${project_dir}/reports/training:/workspace/reports/training" \
  --env PYTHONPATH=/workspace/current/src --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
  "${image}" lerobot-train \
  --dataset.repo_id=synapse2action/g1-pick-place-sim-suite \
  --dataset.root=/workspace/reports/simulation/lerobot-g1-pick-place-suite \
  --dataset.eval_split=0.2 \
  --policy.path=lerobot/smolvla_base \
  --policy.input_features=null \
  --policy.output_features=null \
  --policy.repo_id=synapse2action/smolvla-g1-sim-suite \
  --policy.push_to_hub=false \
  --output_dir=/workspace/reports/training/smolvla-g1-suite \
  --job_name=smolvla-g1-suite \
  --steps="${steps}" \
  --batch_size=1 \
  --num_workers=0 \
  --log_freq=10 \
  --eval_steps="${steps}" \
  --save_freq="${steps}" \
  --wandb.enable=false \
  --policy.device=cpu

model=/workspace/reports/training/smolvla-g1-suite/checkpoints/last/pretrained_model
docker run --rm \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${cache}:/root/.cache/huggingface" \
  --volume "${project_dir}/reports:/workspace/reports" \
  --env PYTHONPATH=/workspace/current/src --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
  "${image}" python simulation/validate_smolvla_g1_checkpoint.py \
  "${model}" \
  /workspace/reports/simulation/g1-pick-place-1.05.npz \
  --report /workspace/reports/training/smolvla-g1-suite.json
docker run --rm \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${cache}:/root/.cache/huggingface" \
  --volume "${project_dir}/reports:/workspace/reports" \
  --env PYTHONPATH=/workspace/current/src --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
  "${image}" python simulation/evaluate_smolvla_g1_offline.py \
  "${model}" \
  /workspace/reports/simulation/g1-pick-place-1.05.npz \
  --task-spec /workspace/current/experiments/tasks/g1_pick_place.json \
  --report /workspace/reports/training/smolvla-g1-suite-heldout.json
