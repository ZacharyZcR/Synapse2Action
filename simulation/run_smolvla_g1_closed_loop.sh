#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
report_dir="${project_dir}/reports/simulation"
cache="${project_dir}/simulation/vendor/huggingface"
model="${project_dir}/reports/training/smolvla-g1-suite/checkpoints/last/pretrained_model"
policy_image="synapse2action-smolvla:0.6.1"
simulator_image="synapse2action-unitree-render:locked-v3"
controller_image="synapse2action-unitree-controller:locked-v18"
[[ -f "${model}/config.json" ]] || { echo "missing trained SmolVLA checkpoint: ${model}" >&2; exit 2; }

run_id="$$"
network="synapse2action-vla-${run_id}"
policy="synapse2action-vla-policy-${run_id}"
controller="synapse2action-vla-controller-${run_id}"
simulator="synapse2action-vla-simulator-${run_id}"
cleanup() {
  docker rm -f "${simulator}" "${controller}" "${policy}" >/dev/null 2>&1 || true
  docker network rm "${network}" >/dev/null 2>&1 || true
}
trap cleanup EXIT
mkdir -p "${report_dir}"
docker network create "${network}" >/dev/null
docker run --detach --name "${policy}" --network "${network}" \
  --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${cache}:/root/.cache/huggingface" \
  --volume "${project_dir}/reports:/workspace/reports:ro" \
  "${policy_image}" python simulation/smolvla_g1_chunk_server.py \
  /workspace/reports/training/smolvla-g1-suite/checkpoints/last/pretrained_model >/dev/null
until docker exec "${policy}" python -c \
  'from urllib.request import urlopen; assert urlopen("http://127.0.0.1:8080/health", timeout=1).status == 200' \
  >/dev/null 2>&1; do
  [[ "$(docker inspect -f '{{.State.Running}}' "${policy}")" == "true" ]] || {
    docker logs "${policy}" >&2
    exit 1
  }
  sleep 1
done
docker run --detach --name "${controller}" --network "${network}" \
  --env S2A_TARGET_X_M=0.0 --env S2A_TARGET_Y_M=0.0 --env S2A_TARGET_YAW_RAD=0.0 \
  --env S2A_MAX_SPEED_MPS=0.3 \
  "${controller_image}" ./build/g1_ctrl -n eth0 >/dev/null
docker run --detach --name "${simulator}" --network "${network}" \
  --workdir /workspace/current --env PYTHONPATH=/workspace/current/src --env MUJOCO_GL=osmesa \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${report_dir}:/workspace/reports/simulation" \
  "${simulator_image}" python3 simulation/g1_mujoco_pick_place.py \
  --unitree-mujoco /opt/unitree/unitree_mujoco --interface eth0 \
  --duration-seconds 30 --vla-endpoint http://${policy}:8080 \
  --output /workspace/reports/simulation/g1-smolvla-closed-loop.json >/dev/null
simulator_exit="$(docker wait "${simulator}")"
docker logs "${policy}" >"${report_dir}/g1-smolvla-policy.log" 2>&1
docker logs "${controller}" >"${report_dir}/g1-smolvla-controller.log" 2>&1
docker logs "${simulator}" >"${report_dir}/g1-smolvla-simulator.log" 2>&1
[[ "${simulator_exit}" == "0" ]] || { cat "${report_dir}/g1-smolvla-simulator.log" >&2; exit 1; }
PYTHONPATH="${project_dir}/src" python3 "${project_dir}/simulation/validate_g1_vla_rollout.py" \
  "${report_dir}/g1-smolvla-closed-loop.json" \
  --output "${report_dir}/g1-smolvla-closed-loop-acceptance.json"
