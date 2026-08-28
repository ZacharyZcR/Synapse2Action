from __future__ import annotations

import argparse
import json
from math import hypot
from pathlib import Path
import sys
from threading import Event, Lock
from time import monotonic, sleep
from types import SimpleNamespace

import mujoco
import numpy as np

from synapse2action.unitree_g1 import G1_FIX_STAND_POSITION_RAD
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_


def relative_pose(data: mujoco.MjData, parent: int, child: int) -> tuple[np.ndarray, np.ndarray]:
    parent_quat = data.xquat[parent]
    inverse = np.array((parent_quat[0], -parent_quat[1], -parent_quat[2], -parent_quat[3]))
    position = np.empty(3)
    mujoco.mju_rotVecQuat(position, data.xpos[child] - data.xpos[parent], inverse)
    quaternion = np.empty(4)
    mujoco.mju_mulQuat(quaternion, inverse, data.xquat[child])
    return position, quaternion


def main() -> None:
    parser = argparse.ArgumentParser(description="Official G1 MuJoCo SDK2 pick-and-place scene")
    parser.add_argument("--unitree-mujoco", type=Path, required=True)
    parser.add_argument("--domain-id", type=int, default=1)
    parser.add_argument("--interface", default="lo")
    parser.add_argument("--duration-seconds", type=float, default=14.0)
    parser.add_argument("--episode-output", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = args.unitree_mujoco / "unitree_robots" / "g1" / "scene.xml"
    additions = """
      <body name="pick_object" pos="0.15 0 0.68">
        <freejoint/>
        <geom name="pick_object_geom" type="box" size="0.045 0.18 0.045" mass="0.12" rgba="0.9 0.15 0.1 1"/>
      </body>
      <body name="drop_tray" pos="0.32 0.12 0.60">
        <geom name="drop_zone" type="box" size="0.12 0.22 0.03" rgba="0.1 0.8 0.2 0.5"/>
      </body>
      <camera name="camera1" mode="targetbody" target="torso_link" pos="1.4 0 1.25"/>
      <camera name="camera2" mode="targetbody" target="torso_link" pos="0.8 1.1 1.15"/>
      <camera name="camera3" mode="targetbody" target="torso_link" pos="0.8 -1.1 1.15"/>
    """
    equality = """
      <equality>
        <weld name="object_fixture" body1="pick_object" active="true"/>
        <weld name="rubber_hand_grasp" body1="left_wrist_yaw_link" body2="pick_object" active="false"/>
      </equality>
    """
    text = source.read_text().replace("</worldbody>", additions + "</worldbody>", 1).replace("</mujoco>", equality + "</mujoco>", 1)
    scene = source.with_name("scene_s2a_pick_place.xml")
    scene.write_text(text)

    simulator_dir = args.unitree_mujoco / "simulate_python"
    sys.path.insert(0, str(simulator_dir))
    sys.modules["config"] = SimpleNamespace(ROBOT="g1")
    from unitree_sdk2py_bridge import UnitreeSdk2Bridge

    model = mujoco.MjModel.from_xml_path(str(scene))
    model.opt.timestep = 0.002
    data = mujoco.MjData(model)
    data.qpos[2] = 0.78
    data.qpos[7 : 7 + len(G1_FIX_STAND_POSITION_RAD)] = G1_FIX_STAND_POSITION_RAD
    mujoco.mj_forward(model, data)
    ChannelFactoryInitialize(args.domain_id, args.interface)
    bridge = UnitreeSdk2Bridge(model, data)
    bridge.low_state.mode_machine = 5

    first_command = Event()
    command_count = 0
    command_lock = Lock()
    latest_action: np.ndarray | None = None

    def record_command(message: LowCmd_) -> None:
        nonlocal command_count, latest_action
        with command_lock:
            command_count += 1
            latest_action = np.array([float(motor.q) for motor in message.motor_cmd[:29]], dtype=np.float32)
        first_command.set()

    subscriber = ChannelSubscriber("rt/lowcmd", LowCmd_)
    subscriber.Init(record_command, 10)
    deadline = monotonic() + 5.0
    while not first_command.is_set() and monotonic() < deadline:
        sleep(0.002)
    if not first_command.is_set():
        raise TimeoutError("no SDK2 LowCmd received")

    left = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "left_wrist_yaw_link")
    right = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "right_wrist_yaw_link")
    item = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "pick_object")
    weld = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_EQUALITY, "rubber_hand_grasp")
    fixture = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_EQUALITY, "object_fixture")
    initial_item = data.xpos[item].copy()
    grasped = False
    released = False
    maximum_item_height = float(data.xpos[item, 2])
    minimum_base_height = float(data.qpos[2])
    minimum_left_distance = float("inf")
    minimum_right_distance = float("inf")
    fell_at_seconds: float | None = None
    grasped_at_seconds: float | None = None
    released_at_seconds: float | None = None
    object_position_at_release: list[float] | None = None
    maximum_left_hand_height = float(data.xpos[left, 2])
    episode_time: list[float] = []
    episode_state: list[np.ndarray] = []
    episode_action: list[np.ndarray] = []
    episode_qpos: list[np.ndarray] = []
    started = monotonic()
    next_step = started
    steps = 0
    while monotonic() - started < args.duration_seconds:
        mujoco.mj_step(model, data)
        steps += 1
        minimum_base_height = min(minimum_base_height, float(data.qpos[2]))
        maximum_item_height = max(maximum_item_height, float(data.xpos[item, 2]))
        maximum_left_hand_height = max(maximum_left_hand_height, float(data.xpos[left, 2]))
        left_distance = float(np.linalg.norm(data.xpos[left] - data.xpos[item]))
        right_distance = float(np.linalg.norm(data.xpos[right] - data.xpos[item]))
        minimum_left_distance = min(minimum_left_distance, left_distance)
        minimum_right_distance = min(minimum_right_distance, right_distance)
        if fell_at_seconds is None and data.qpos[2] < 0.65:
            fell_at_seconds = float(data.time)
        if not grasped and data.time > 3.0 and left_distance < 0.25 and right_distance < 0.25:
            position, quaternion = relative_pose(data, left, item)
            model.eq_data[weld, 3:6] = position
            model.eq_data[weld, 6:10] = quaternion
            data.eq_active[fixture] = 0
            data.eq_active[weld] = 1
            grasped = True
            grasped_at_seconds = float(data.time)
        if grasped and not released and data.time > 13.0:
            data.eq_active[weld] = 0
            released = True
            released_at_seconds = float(data.time)
            object_position_at_release = data.xpos[item].tolist()
        if args.episode_output and steps % 50 == 0:
            with command_lock:
                action = None if latest_action is None else latest_action.copy()
            if action is not None:
                episode_time.append(float(data.time))
                episode_state.append(np.asarray(data.qpos[7:36], dtype=np.float32).copy())
                episode_action.append(action)
                episode_qpos.append(data.qpos.copy())
        next_step += model.opt.timestep
        remaining = next_step - monotonic()
        if remaining > 0:
            sleep(remaining)

    final_item = data.xpos[item].copy()
    report = {
        "simulator": "unitreerobotics/unitree_mujoco",
        "model": "g1_29dof",
        "sdk2_lowcmd_frames": command_count,
        "grasped": grasped,
        "released": released,
        "initial_object_position_xyz_m": initial_item.tolist(),
        "final_object_position_xyz_m": final_item.tolist(),
        "object_planar_displacement_m": hypot(float(final_item[0] - initial_item[0]), float(final_item[1] - initial_item[1])),
        "drop_zone_center_xy_m": [0.32, 0.12],
        "final_drop_zone_error_m": hypot(float(final_item[0] - 0.32), float(final_item[1] - 0.12)),
        "maximum_object_height_m": maximum_item_height,
        "minimum_base_height_m": minimum_base_height,
        "fell_at_seconds": fell_at_seconds,
        "grasped_at_seconds": grasped_at_seconds,
        "released_at_seconds": released_at_seconds,
        "object_position_at_release_xyz_m": object_position_at_release,
        "maximum_left_hand_height_m": maximum_left_hand_height,
        "minimum_left_hand_object_distance_m": minimum_left_distance,
        "minimum_right_hand_object_distance_m": minimum_right_distance,
        "final_base_height_m": float(data.qpos[2]),
        "final_left_hand_object_distance_m": float(np.linalg.norm(data.xpos[left] - final_item)),
        "external_support": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.episode_output:
        render_data = mujoco.MjData(model)
        renderers = {
            name: mujoco.Renderer(model, height=256, width=256)
            for name in ("camera1", "camera2", "camera3")
        }
        episode_images: dict[str, list[np.ndarray]] = {name: [] for name in renderers}
        for qpos in episode_qpos:
            render_data.qpos[:] = qpos
            mujoco.mj_forward(model, render_data)
            for name, renderer in renderers.items():
                renderer.update_scene(render_data, camera=name)
                episode_images[name].append(renderer.render().copy())
        args.episode_output.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            args.episode_output,
            timestamp=np.asarray(episode_time, dtype=np.float64),
            observation_state=np.stack(episode_state),
            action=np.stack(episode_action),
            images_camera1=np.stack(episode_images["camera1"]),
            images_camera2=np.stack(episode_images["camera2"]),
            images_camera3=np.stack(episode_images["camera3"]),
            task=np.asarray("pick the red block and place it in the green tray"),
        )


if __name__ == "__main__":
    main()
