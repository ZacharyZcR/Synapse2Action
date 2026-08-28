#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
report_dir="${project_dir}/reports/simulation"
cache="${project_dir}/simulation/vendor/huggingface"
model="${project_dir}/reports/training/smolvla-g1-suite/checkpoints/last/pretrained_model"
policy_image="synapse2action-smolvla:0.6.1"
simulator_image="synapse2action-unitree-render:locked-v3"
controller_image="synapse2action-unitree-controller:locked-v19"
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
if ! docker image inspect "${controller_image}" >/dev/null 2>&1; then
  docker build --platform linux/amd64 \
    -f "${project_dir}/simulation/docker/Dockerfile.unitree-controller-amd64" \
    -t "${controller_image}" "${project_dir}"
fi
docker network create "${network}" >/dev/null
docker run --detach --name "${policy}" --network "${network}" --cpu-shares 256 \
  --env OMP_NUM_THREADS=8 --env MKL_NUM_THREADS=8 \
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
docker run --detach --name "${controller}" --network "${network}" --cpu-shares 4096 \
  --env S2A_TARGET_X_M=0.0 --env S2A_TARGET_Y_M=0.0 --env S2A_TARGET_YAW_RAD=0.0 \
  --env S2A_MAX_SPEED_MPS=0.3 --env S2A_PICK_PLACE=1 \
  --env S2A_MANIPULATION_START_DELAY_SECONDS=12 \
  "${controller_image}" ./build/g1_ctrl -n eth0 >/dev/null
docker run --detach --name "${simulator}" --network "${network}" --cpu-shares 2048 \
  --workdir /workspace/current --env PYTHONPATH=/workspace/current/src --env MUJOCO_GL=osmesa \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${report_dir}:/workspace/reports/simulation" \
  "${simulator_image}" python3 simulation/g1_mujoco_pick_place.py \
  --unitree-mujoco /opt/unitree/unitree_mujoco --interface eth0 \
  --duration-seconds 20 --vla-endpoint http://${policy}:8080 \
  --vla-frequency-hz 3 --vla-stale-after-seconds 20 \
  --vla-refresh-lookahead-actions 50 --release-timeout-seconds 19.8 \
  --vla-typed-skill-passthrough \
  --output /workspace/reports/simulation/g1-smolvla-closed-loop.json >/dev/null
simulator_exit="$(docker wait "${simulator}")"
docker logs "${policy}" >"${report_dir}/g1-smolvla-policy.log" 2>&1
docker logs "${controller}" >"${report_dir}/g1-smolvla-controller.log" 2>&1
docker logs "${simulator}" >"${report_dir}/g1-smolvla-simulator.log" 2>&1
[[ "${simulator_exit}" == "0" ]] || { cat "${report_dir}/g1-smolvla-simulator.log" >&2; exit 1; }
PYTHONPATH="${project_dir}/src" python3 "${project_dir}/simulation/validate_g1_vla_rollout.py" \
  "${report_dir}/g1-smolvla-closed-loop.json" \
  --output "${report_dir}/g1-smolvla-closed-loop-acceptance.json"
