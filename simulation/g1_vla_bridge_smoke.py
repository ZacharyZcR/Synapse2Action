from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import mujoco

from synapse2action.g1_vla import make_g1_vla_bridge
from synapse2action.task_spec import load_task_spec
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_


def main() -> None:
    parser = argparse.ArgumentParser(description="Exercise the VLA overlay on Unitree's real MuJoCo bridge")
    parser.add_argument("--unitree-mujoco", type=Path, required=True)
    parser.add_argument("--task-spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    task = load_task_spec(args.task_spec)

    simulator_dir = args.unitree_mujoco / "simulate_python"
    sys.path.insert(0, str(simulator_dir))
    sys.modules["config"] = SimpleNamespace(ROBOT="g1")
    from unitree_sdk2py_bridge import UnitreeSdk2Bridge

    model = mujoco.MjModel.from_xml_path(str(args.unitree_mujoco / "unitree_robots/g1/scene.xml"))
    data = mujoco.MjData(model)
    data.qpos[2] = 0.78
    mujoco.mj_forward(model, data)
    ChannelFactoryInitialize(1, "lo")
    bridge = make_g1_vla_bridge(
        UnitreeSdk2Bridge,
        joint_indices=task.controller.joint_indices,
        joint_limits_rad=task.controller.joint_limits_rad,
    )(model, data)
    command = unitree_hg_msg_dds__LowCmd_()
    for motor in command.motor_cmd[:29]:
        motor.mode = 1
        motor.q = 0.0
        motor.dq = 0.0
        motor.tau = 0.0
        motor.kp = 1.0
        motor.kd = 0.0

    bridge.LowCmdHandler(command)
    baseline = data.ctrl.copy()
    bridge.set_vla_action((1.0,) * 29)
    bridge.LowCmdHandler(command)
    overlaid = data.ctrl.copy()
    manipulation = set(task.controller.joint_indices)
    checks = {
        "official_bridge_class": UnitreeSdk2Bridge.__module__ == "unitree_sdk2py_bridge",
        "all_values_finite": bool(all(float(value) == float(value) for value in overlaid)),
        "manipulation_changed": all(overlaid[index] != baseline[index] for index in manipulation),
        "rl_joints_preserved": all(overlaid[index] == baseline[index] for index in set(range(29)) - manipulation),
        "one_overlay_frame": bridge.vla_overlay_frames == 1,
    }
    report = {"accepted": all(checks.values()), "checks": checks}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(not report["accepted"])


if __name__ == "__main__":
    main()
