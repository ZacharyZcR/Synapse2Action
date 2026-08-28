#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
report_dir="${project_dir}/reports/simulation"
simulator_image="synapse2action-unitree:locked-v2"
controller_image="synapse2action-unitree-controller:locked-v17"
run_id="$$"
network="synapse2action-pick-place-${run_id}"
simulator="synapse2action-pick-place-simulator-${run_id}"
controller="synapse2action-pick-place-controller-${run_id}"

cleanup() {
  docker rm -f "${simulator}" "${controller}" >/dev/null 2>&1 || true
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
docker run --detach --name "${controller}" --network "${network}" \
  --env S2A_TARGET_X_M=0.0 --env S2A_TARGET_Y_M=0.0 --env S2A_TARGET_YAW_RAD=0.0 \
  --env S2A_MAX_SPEED_MPS=0.3 --env S2A_PICK_PLACE=1 \
  "${controller_image}" ./build/g1_ctrl -n eth0 >/dev/null
docker run --detach --name "${simulator}" --network "${network}" \
  --workdir /workspace/current --env PYTHONPATH=/workspace/current/src \
  --volume "${project_dir}:/workspace/current:ro" \
  --volume "${report_dir}:/workspace/reports/simulation" \
  "${simulator_image}" python3 simulation/g1_mujoco_pick_place.py \
  --unitree-mujoco /opt/unitree/unitree_mujoco --interface eth0 \
  --output /workspace/reports/simulation/g1-pick-place.json >/dev/null
simulator_exit="$(docker wait "${simulator}")"
docker logs "${controller}" >"${report_dir}/g1-pick-place-controller.log" 2>&1
docker logs "${simulator}" >"${report_dir}/g1-pick-place-simulator.log" 2>&1
if [[ "${simulator_exit}" != "0" ]]; then
  cat "${report_dir}/g1-pick-place-controller.log" >&2
  cat "${report_dir}/g1-pick-place-simulator.log" >&2
  exit 1
fi
python3 - "${report_dir}" <<'PY'
import json
from pathlib import Path
import sys

directory = Path(sys.argv[1])
simulator = json.loads((directory / "g1-pick-place.json").read_text())
controller_log = (directory / "g1-pick-place-controller.log").read_text()
checks = {
    "official_sdk2_commands": simulator["sdk2_lowcmd_frames"] >= 1000,
    "official_balance_policy": "FSM: Start Velocity" in controller_log,
    "object_grasped": simulator["grasped"],
    "object_released": simulator["released"],
    "object_lifted": simulator["maximum_object_height_m"] - simulator["initial_object_position_xyz_m"][2] >= 0.10,
    "object_transported": simulator["object_planar_displacement_m"] >= 0.05,
    "object_in_drop_zone": simulator["final_drop_zone_error_m"] <= 0.15,
    "g1_remained_standing": simulator["minimum_base_height_m"] >= 0.65 and simulator["final_base_height_m"] >= 0.65,
    "no_external_support": simulator["external_support"] is False,
}
report = {"accepted": all(checks.values()), "checks": checks}
(directory / "g1-pick-place-acceptance.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
print(json.dumps(report, sort_keys=True))
raise SystemExit(not report["accepted"])
PY
