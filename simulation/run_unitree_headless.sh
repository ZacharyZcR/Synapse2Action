#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
report_dir="${project_dir}/reports/simulation"
simulator_image="synapse2action-unitree:locked-v2"
controller_image="synapse2action-unitree-controller:locked-v17"
scenario="${1:-balance}"
if [[ "${scenario}" != "balance" && "${scenario}" != "locomotion" && "${scenario}" != "obstacle" && "${scenario}" != "dynamic-obstacle" ]]; then
  echo "usage: $0 [balance|locomotion|obstacle|dynamic-obstacle [target-x-m target-y-m target-yaw-rad]]" >&2
  exit 2
fi
target_x="0.0"
target_y="0.0"
target_yaw="0.0"
duration_seconds="14"
controller_obstacle_args=()
simulator_obstacle_args=()
if [[ "${scenario}" != "balance" ]]; then
  target_x="${2:-0.8}"
  target_y="${3:-0.0}"
  target_yaw="${4:-0.0}"
fi
if [[ "${scenario}" == "obstacle" || "${scenario}" == "dynamic-obstacle" ]]; then
  target_x="${2:-0.9}"
  duration_seconds="30"
  controller_obstacle_args=(
    --env S2A_OBSTACLE_X_M=0.45
    --env S2A_OBSTACLE_Y_M=0.0
    --env S2A_OBSTACLE_RADIUS_M=0.12
  )
  simulator_obstacle_args=(
    --obstacle-x 0.45
    --obstacle-y 0.0
    --obstacle-radius 0.12
  )
fi
if [[ "${scenario}" == "dynamic-obstacle" ]]; then
  duration_seconds="36"
  controller_obstacle_args=(--env S2A_DYNAMIC_OBSTACLE=1)
  simulator_obstacle_args+=(--dynamic-obstacle --obstacle-appear-seconds 0.05)
fi
run_id="$$"
network="synapse2action-unitree-${run_id}"
simulator="synapse2action-unitree-simulator-${run_id}"
controller="synapse2action-unitree-controller-${run_id}"

cleanup() {
  docker rm -f "${simulator}" "${controller}" >/dev/null 2>&1 || true
  docker network rm "${network}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

mkdir -p "${report_dir}"
if ! docker image inspect "${simulator_image}" >/dev/null 2>&1; then
  if docker image inspect synapse2action-unitree:locked >/dev/null 2>&1; then
    docker build \
      -f "${project_dir}/simulation/docker/Dockerfile.unitree-policy-layer" \
      -t "${simulator_image}" "${project_dir}"
  else
    docker build \
      -f "${project_dir}/simulation/docker/Dockerfile.unitree" \
      -t "${simulator_image}" "${project_dir}"
  fi
fi
if ! docker image inspect "${controller_image}" >/dev/null 2>&1; then
  docker build --platform linux/amd64 \
    -f "${project_dir}/simulation/docker/Dockerfile.unitree-controller-amd64" \
    -t "${controller_image}" "${project_dir}"
fi

docker network create "${network}" >/dev/null
docker run --detach \
  --name "${controller}" \
  --network "${network}" \
  --env S2A_TARGET_X_M="${target_x}" \
  --env S2A_TARGET_Y_M="${target_y}" \
  --env S2A_TARGET_YAW_RAD="${target_yaw}" \
  --env S2A_MAX_SPEED_MPS="0.3" \
  "${controller_obstacle_args[@]}" \
  "${controller_image}" \
  ./build/g1_ctrl -n eth0 >/dev/null
docker run --detach \
  --name "${simulator}" \
  --network "${network}" \
  --workdir /workspace/current \
  --env PYTHONPATH=/workspace/current/src \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${report_dir}:/workspace/reports/simulation" \
  "${simulator_image}" \
  python3 simulation/g1_mujoco_headless.py \
    --unitree-mujoco /opt/unitree/unitree_mujoco \
    --domain-id 1 \
    --interface eth0 \
    --container-network \
    --target-x "${target_x}" \
    --target-y "${target_y}" \
    --target-yaw "${target_yaw}" \
    "${simulator_obstacle_args[@]}" \
    --duration-seconds "${duration_seconds}" \
    --output /workspace/reports/simulation/g1-mujoco.json >/dev/null

simulator_exit="$(docker wait "${simulator}")"
docker logs "${controller}" >"${report_dir}/g1-controller.log" 2>&1
docker logs "${simulator}" >"${report_dir}/g1-simulator.log" 2>&1
if [[ "${simulator_exit}" != "0" ]]; then
  cat "${report_dir}/g1-simulator.log" >&2
  exit "${simulator_exit}"
fi

python3 "${project_dir}/simulation/validate_unitree_report.py" \
  "${report_dir}" --scenario "${scenario}"
