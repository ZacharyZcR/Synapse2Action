from __future__ import annotations

import argparse
import json
from math import atan2, cos, hypot, sin
from pathlib import Path
import sys
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace

import mujoco

from synapse2action.unitree_g1 import G1_FIX_STAND_POSITION_RAD
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.default import unitree_go_msg_dds__SportModeState_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_


def main() -> None:
    parser = argparse.ArgumentParser(description="Headless official Unitree MuJoCo SDK2 bridge")
    parser.add_argument("--unitree-mujoco", type=Path, required=True)
    parser.add_argument("--domain-id", type=int, default=1)
    parser.add_argument("--interface", default="lo")
    parser.add_argument("--container-network", action="store_true")
    parser.add_argument("--duration-seconds", type=float, default=8.0)
    parser.add_argument("--command-preroll-seconds", type=float, default=0.5)
    parser.add_argument("--target-x", type=float, default=0.0)
    parser.add_argument("--target-y", type=float, default=0.0)
    parser.add_argument("--target-yaw", type=float, default=0.0)
    parser.add_argument("--obstacle-x", type=float, default=0.0)
    parser.add_argument("--obstacle-y", type=float, default=0.0)
    parser.add_argument("--obstacle-radius", type=float, default=0.0)
    parser.add_argument("--dynamic-obstacle", action="store_true")
    parser.add_argument("--obstacle-appear-seconds", type=float, default=1.0)
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
    if args.obstacle_radius > 0:
        initial_x = 5.0 if args.dynamic_obstacle else args.obstacle_x
        obstacle_geom = (
            f'<body name="s2a_obstacle_body" mocap="true" pos="{initial_x} {args.obstacle_y} 0.25">'
            f'<geom name="s2a_obstacle" type="box" '
            f'size="{args.obstacle_radius} {args.obstacle_radius} 0.25" '
            'rgba="0.8 0.15 0.1 1"/></body>\n'
        )
        scene_text = scene.read_text().replace("</worldbody>", obstacle_geom + "</worldbody>", 1)
        scene = scene.with_name("scene_s2a_obstacle.xml")
        scene.write_text(scene_text)
    sys.path.insert(0, str(simulator_dir))
    sys.modules["config"] = SimpleNamespace(ROBOT="g1")
    from unitree_sdk2py_bridge import UnitreeSdk2Bridge

    model = mujoco.MjModel.from_xml_path(str(scene))
    model.opt.timestep = 0.002
    data = mujoco.MjData(model)
    obstacle_mocap_id = -1
    if args.obstacle_radius > 0:
        obstacle_body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "s2a_obstacle_body")
        obstacle_mocap_id = int(model.body_mocapid[obstacle_body_id])
    obstacle_active = args.obstacle_radius > 0 and not args.dynamic_obstacle
    data.qpos[2] = 0.78
    data.qpos[7 : 7 + len(G1_FIX_STAND_POSITION_RAD)] = G1_FIX_STAND_POSITION_RAD
    mujoco.mj_forward(model, data)
    initial_base_position = [float(value) for value in data.qpos[:3]]
    ChannelFactoryInitialize(args.domain_id, args.interface)
    bridge = UnitreeSdk2Bridge(model, data)
    bridge.low_state.mode_machine = 5
    odometry = unitree_go_msg_dds__SportModeState_()
    odometry_publisher = ChannelPublisher("rt/sportmodestate", SportModeState_)
    odometry_publisher.Init()
    odometry_frames = 0

    def base_yaw() -> float:
        w, x, y, z = (float(value) for value in data.qpos[3:7])
        return atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))

    def publish_odometry() -> None:
        nonlocal odometry_frames
        odometry.position = [float(value) for value in data.qpos[:3]]
        odometry.velocity = [float(value) for value in data.qvel[:3]]
        odometry.body_height = float(data.qpos[2])
        odometry.imu_state.rpy = [0.0, 0.0, base_yaw()]
        obstacle_range = 10.0
        if obstacle_active:
            dx = args.obstacle_x - float(data.qpos[0])
            dy = args.obstacle_y - float(data.qpos[1])
            yaw = base_yaw()
            forward = cos(yaw) * dx + sin(yaw) * dy
            lateral = -sin(yaw) * dx + cos(yaw) * dy
            if forward > 0 and abs(lateral) < 0.5:
                obstacle_range = max(0.0, hypot(dx, dy) - args.obstacle_radius)
        odometry.range_obstacle[:] = [obstacle_range, 10.0, 10.0, 10.0]
        odometry_publisher.Write(odometry)
        odometry_frames += 1

    first_command = Event()
    command_count = 0

    def record_command(_: LowCmd_) -> None:
        nonlocal command_count
        command_count += 1
        first_command.set()

    command_probe = ChannelSubscriber("rt/lowcmd", LowCmd_)
    command_probe.Init(record_command, 10)
    command_deadline = monotonic() + 5.0
    while not first_command.is_set() and monotonic() < command_deadline:
        publish_odometry()
        sleep(0.002)
    if not first_command.is_set():
        raise TimeoutError("no SDK2 LowCmd received before physics start")
    preroll_deadline = monotonic() + args.command_preroll_seconds
    while monotonic() < preroll_deadline:
        publish_odometry()
        sleep(0.002)

    started = monotonic()
    next_step = started
    steps = 0
    minimum_base_height = float(data.qpos[2])
    maximum_base_height = float(data.qpos[2])
    minimum_obstacle_center_distance = float("inf")
    maximum_abs_lateral_position = abs(float(data.qpos[1]))
    while monotonic() - started < args.duration_seconds:
        if args.dynamic_obstacle and not obstacle_active and data.time >= args.obstacle_appear_seconds:
            data.mocap_pos[obstacle_mocap_id] = [args.obstacle_x, args.obstacle_y, 0.25]
            obstacle_active = True
        mujoco.mj_step(model, data)
        publish_odometry()
        steps += 1
        minimum_base_height = min(minimum_base_height, float(data.qpos[2]))
        maximum_base_height = max(maximum_base_height, float(data.qpos[2]))
        maximum_abs_lateral_position = max(maximum_abs_lateral_position, abs(float(data.qpos[1])))
        if obstacle_active:
            minimum_obstacle_center_distance = min(
                minimum_obstacle_center_distance,
                hypot(float(data.qpos[0]) - args.obstacle_x, float(data.qpos[1]) - args.obstacle_y),
            )
        next_step += model.opt.timestep
        remaining = next_step - monotonic()
        if remaining > 0:
            sleep(remaining)

    final_yaw = base_yaw()
    position_error = hypot(args.target_x - float(data.qpos[0]), args.target_y - float(data.qpos[1]))
    yaw_error = atan2(sin(args.target_yaw - final_yaw), cos(args.target_yaw - final_yaw))
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
        "target_position_x_m": args.target_x,
        "target_position_y_m": args.target_y,
        "target_yaw_rad": args.target_yaw,
        "final_position_error_m": position_error,
        "final_yaw_rad": final_yaw,
        "final_yaw_error_rad": yaw_error,
        "final_base_linear_velocity_xyz_mps": [float(value) for value in data.qvel[:3]],
        "final_yaw_rate_rad_s": float(data.qvel[5]),
        "obstacle_position_xy_m": [args.obstacle_x, args.obstacle_y],
        "obstacle_radius_m": args.obstacle_radius,
        "dynamic_obstacle": args.dynamic_obstacle,
        "obstacle_appear_seconds": args.obstacle_appear_seconds,
        "minimum_obstacle_center_distance_m": (
            minimum_obstacle_center_distance if args.obstacle_radius > 0 else None
        ),
        "maximum_abs_lateral_position_m": maximum_abs_lateral_position,
        "minimum_base_height_m": minimum_base_height,
        "maximum_base_height_m": maximum_base_height,
        "physics_started_after_lowcmd": first_command.is_set(),
        "lowcmd_frames_before_physics": command_count,
        "command_preroll_seconds": args.command_preroll_seconds,
        "odometry_frames_published": odometry_frames,
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
