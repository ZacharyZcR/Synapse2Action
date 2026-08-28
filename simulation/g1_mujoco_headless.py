from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace

import mujoco

from synapse2action.unitree_g1 import G1_FIX_STAND_POSITION_RAD
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_


def main() -> None:
    parser = argparse.ArgumentParser(description="Headless official Unitree MuJoCo SDK2 bridge")
    parser.add_argument("--unitree-mujoco", type=Path, required=True)
    parser.add_argument("--domain-id", type=int, default=1)
    parser.add_argument("--interface", default="lo")
    parser.add_argument("--container-network", action="store_true")
    parser.add_argument("--duration-seconds", type=float, default=8.0)
    parser.add_argument("--command-preroll-seconds", type=float, default=0.5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.interface != "lo" and not args.container_network:
        raise ValueError("headless simulation requires loopback interface 'lo'")
    if args.duration_seconds <= 0:
        raise ValueError("simulation duration must be positive")
    if args.command_preroll_seconds < 0:
        raise ValueError("command pre-roll duration cannot be negative")

    simulator_dir = args.unitree_mujoco / "simulate_python"
    scene = args.unitree_mujoco / "unitree_robots" / "g1" / "scene.xml"
    sys.path.insert(0, str(simulator_dir))
    sys.modules["config"] = SimpleNamespace(ROBOT="g1")
    from unitree_sdk2py_bridge import UnitreeSdk2Bridge

    model = mujoco.MjModel.from_xml_path(str(scene))
    model.opt.timestep = 0.002
    data = mujoco.MjData(model)
    data.qpos[2] = 0.78
    data.qpos[7 : 7 + len(G1_FIX_STAND_POSITION_RAD)] = G1_FIX_STAND_POSITION_RAD
    mujoco.mj_forward(model, data)
    initial_base_position = [float(value) for value in data.qpos[:3]]
    ChannelFactoryInitialize(args.domain_id, args.interface)
    bridge = UnitreeSdk2Bridge(model, data)
    bridge.low_state.mode_machine = 5
    first_command = Event()
    command_count = 0

    def record_command(_: LowCmd_) -> None:
        nonlocal command_count
        command_count += 1
        first_command.set()

    command_probe = ChannelSubscriber("rt/lowcmd", LowCmd_)
    command_probe.Init(record_command, 10)
    if not first_command.wait(5.0):
        raise TimeoutError("no SDK2 LowCmd received before physics start")
    sleep(args.command_preroll_seconds)

    started = monotonic()
    next_step = started
    steps = 0
    minimum_base_height = float(data.qpos[2])
    maximum_base_height = float(data.qpos[2])
    while monotonic() - started < args.duration_seconds:
        mujoco.mj_step(model, data)
        steps += 1
        minimum_base_height = min(minimum_base_height, float(data.qpos[2]))
        maximum_base_height = max(maximum_base_height, float(data.qpos[2]))
        next_step += model.opt.timestep
        remaining = next_step - monotonic()
        if remaining > 0:
            sleep(remaining)

    report = {
        "simulator": "unitreerobotics/unitree_mujoco",
        "model": "g1_29dof",
        "motor_count": model.nu,
        "steps": steps,
        "simulated_seconds": float(data.time),
        "control_timestep_seconds": float(model.opt.timestep),
        "base_height_m": float(data.qpos[2]),
        "initial_base_position_xyz_m": initial_base_position,
        "final_base_position_xyz_m": [float(value) for value in data.qpos[:3]],
        "forward_displacement_m": float(data.qpos[0]) - initial_base_position[0],
        "final_base_linear_velocity_xyz_mps": [float(value) for value in data.qvel[:3]],
        "minimum_base_height_m": minimum_base_height,
        "maximum_base_height_m": maximum_base_height,
        "physics_started_after_lowcmd": first_command.is_set(),
        "lowcmd_frames_before_physics": command_count,
        "command_preroll_seconds": args.command_preroll_seconds,
        "external_support": False,
        "unsupported_seconds": float(data.time),
        "base_quaternion_wxyz": [float(value) for value in data.qpos[3:7]],
        "joint_position_rad": [float(value) for value in data.qpos[7 : 7 + model.nu]],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
