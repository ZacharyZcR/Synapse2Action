#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
task_spec="${1:-${project_dir}/experiments/tasks/g1_pick_place.json}"
task_spec_relative="${task_spec#${project_dir}/}"
[[ "${task_spec_relative}" != "${task_spec}" && -f "${task_spec}" ]] || { echo "task spec must be a file inside ${project_dir}" >&2; exit 2; }
container_task_spec="/workspace/current/${task_spec_relative}"
report_dir="${project_dir}/reports/simulation"
controller_env="${report_dir}/task-controller-$$.env"
simulator_image="synapse2action-unitree-render:locked-v3"
controller_image="synapse2action-unitree-controller:locked-v20"
record_episode="${S2A_RECORD_EPISODE:-0}"
episode_name="${S2A_EPISODE_NAME:-g1-pick-place-episode.npz}"
time_scale="${S2A_MANIPULATION_TIME_SCALE:-1.0}"
[[ "${episode_name}" != */* ]] || { echo "S2A_EPISODE_NAME must be a filename" >&2; exit 2; }
episode_args=()
if [[ "${record_episode}" == "1" ]]; then
  episode_args=(--episode-output "/workspace/reports/simulation/${episode_name}")
fi
run_id="$$"
network="synapse2action-pick-place-${run_id}"
simulator="synapse2action-pick-place-simulator-${run_id}"
controller="synapse2action-pick-place-controller-${run_id}"

cleanup() {
  docker rm -f "${simulator}" "${controller}" >/dev/null 2>&1 || true
  docker network rm "${network}" >/dev/null 2>&1 || true
  rm -f "${controller_env}"
}
trap cleanup EXIT
mkdir -p "${report_dir}"
PYTHONPATH="${project_dir}/src" python3 "${project_dir}/simulation/export_task_controller_env.py" "${task_spec}" "${controller_env}"
if ! docker image inspect "${simulator_image}" >/dev/null 2>&1; then
  docker build -f "${project_dir}/simulation/docker/Dockerfile.unitree-render" \
    -t "${simulator_image}" "${project_dir}"
fi
if ! docker image inspect "${controller_image}" >/dev/null 2>&1; then
  docker build --platform linux/amd64 \
    -f "${project_dir}/simulation/docker/Dockerfile.unitree-controller-amd64" \
    -t "${controller_image}" "${project_dir}"
fi
docker network create "${network}" >/dev/null
docker run --detach --name "${controller}" --network "${network}" \
  --env-file "${controller_env}" \
  --env S2A_TARGET_X_M=0.0 --env S2A_TARGET_Y_M=0.0 --env S2A_TARGET_YAW_RAD=0.0 \
  --env S2A_MAX_SPEED_MPS=0.3 --env S2A_TASK_TRAJECTORY=1 \
  --env "S2A_MANIPULATION_TIME_SCALE=${time_scale}" \
  "${controller_image}" ./build/g1_ctrl -n eth0 >/dev/null
docker run --detach --name "${simulator}" --network "${network}" \
  --workdir /workspace/current --env PYTHONPATH=/workspace/current/src --env MUJOCO_GL=osmesa \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${report_dir}:/workspace/reports/simulation" \
  "${simulator_image}" python3 simulation/g1_mujoco_pick_place.py \
  --unitree-mujoco /opt/unitree/unitree_mujoco --interface eth0 \
  --task-spec "${container_task_spec}" \
  "${episode_args[@]}" \
  --output /workspace/reports/simulation/g1-pick-place.json >/dev/null
simulator_exit="$(docker wait "${simulator}")"
docker logs "${controller}" >"${report_dir}/g1-pick-place-controller.log" 2>&1
docker logs "${simulator}" >"${report_dir}/g1-pick-place-simulator.log" 2>&1
if [[ "${simulator_exit}" != "0" ]]; then
  cat "${report_dir}/g1-pick-place-controller.log" >&2
  cat "${report_dir}/g1-pick-place-simulator.log" >&2
  exit 1
fi
PYTHONPATH="${project_dir}/src" python3 - "${report_dir}" "${task_spec}" <<'PY'
import json
from pathlib import Path
import sys
from synapse2action.task_spec import load_task_spec

directory = Path(sys.argv[1])
task = load_task_spec(Path(sys.argv[2]))
simulator = json.loads((directory / "g1-pick-place.json").read_text())
controller_log = (directory / "g1-pick-place-controller.log").read_text()
checks = {
    "official_sdk2_commands": simulator["sdk2_lowcmd_frames"] >= 1000,
    "official_balance_policy": "FSM: Start Velocity" in controller_log,
    "object_grasped": simulator["grasped"],
    "object_released": simulator["released"],
    "object_lifted": simulator["maximum_object_height_m"] - simulator["initial_object_position_xyz_m"][2] >= task.verification.minimum_lift_m,
    "object_transported": simulator["object_planar_displacement_m"] >= 0.05,
    "object_in_drop_zone": simulator["final_object_center_in_drop_zone"],
    "g1_remained_standing": simulator["minimum_base_height_m"] >= task.verification.minimum_base_height_m and simulator["final_base_height_m"] >= task.verification.minimum_base_height_m,
    "no_external_support": simulator["external_support"] is False,
}
report = {"accepted": all(checks.values()), "checks": checks}
(directory / "g1-pick-place-acceptance.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
print(json.dumps(report, sort_keys=True))
raise SystemExit(not report["accepted"])
PY
