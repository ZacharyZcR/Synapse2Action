from __future__ import annotations

import argparse
import json
from math import hypot
from pathlib import Path
import struct
import sys
from threading import Event, Lock, Thread
from time import monotonic, sleep
from types import SimpleNamespace
import zlib

import mujoco
import numpy as np

from synapse2action.g1_vla import make_g1_vla_bridge
from synapse2action.task_spec import load_task_spec
from synapse2action.unitree_g1 import G1_FIX_STAND_POSITION_RAD
from synapse2action.vla_chunk import G1ChunkCoordinator, SmolVLAChunkClient
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_


def write_rgb_png(path: Path, image: np.ndarray, *, compression: int = 9) -> None:
    height, width, channels = image.shape
    if channels != 3 or image.dtype != np.uint8:
        raise ValueError("PNG image must be uint8 RGB")

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b"".join(b"\0" + image[row].tobytes() for row in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows, compression)) + chunk(b"IEND", b""))


def relative_pose(data: mujoco.MjData, parent: int, child: int) -> tuple[np.ndarray, np.ndarray]:
    parent_quat = data.xquat[parent]
    inverse = np.array((parent_quat[0], -parent_quat[1], -parent_quat[2], -parent_quat[3]))
    position = np.empty(3)
    mujoco.mju_rotVecQuat(position, data.xpos[child] - data.xpos[parent], inverse)
    quaternion = np.empty(4)
    mujoco.mju_mulQuat(quaternion, inverse, data.xquat[child])
    return position, quaternion


def main() -> None:
    parser = argparse.ArgumentParser(description="Official G1 MuJoCo SDK2 TaskSpec scene")
    parser.add_argument("--unitree-mujoco", type=Path, required=True)
    parser.add_argument("--domain-id", type=int, default=1)
    parser.add_argument("--interface", default="lo")
    parser.add_argument("--task-spec", type=Path, required=True)
    parser.add_argument("--plan-source", default="standalone")
    parser.add_argument("--duration-seconds", type=float, default=14.0)
    parser.add_argument("--vla-endpoint")
    parser.add_argument("--vla-block-on-refresh", action="store_true")
    parser.add_argument("--vla-typed-skill-passthrough", action="store_true")
    parser.add_argument("--vla-frequency-hz", type=float, default=10.0)
    parser.add_argument("--vla-stale-after-seconds", type=float, default=7.0)
    parser.add_argument("--vla-refresh-lookahead-actions", type=int, default=5)
    parser.add_argument("--release-timeout-seconds", type=float, default=20.0)
    parser.add_argument("--visualization-directory", type=Path)
    parser.add_argument("--episode-output", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    task = load_task_spec(args.task_spec)
    if args.vla_frequency_hz <= 0:
        parser.error("VLA frequency must be positive")
    source = args.unitree_mujoco / "unitree_robots" / "g1" / "scene.xml"
    target = task.target_entity
    destination = task.destination_entity
    vector = lambda values: " ".join(str(value) for value in values)
    additions = f"""
      <body name="task_target" pos="{vector(target.position)}">
        <freejoint/>
        <geom name="task_target_geom" type="box" size="{vector(target.size)}" mass="{target.mass}" rgba="{vector(target.rgba)}"/>
      </body>
      <body name="task_destination" pos="{vector(destination.position)}">
        <geom name="task_destination_geom" type="box" size="{vector(destination.size)}" rgba="{vector(destination.rgba)}"/>
      </body>
      {''.join(f'<camera name="{name}" mode="targetbody" target="torso_link" pos="{vector(position)}"/>' for name, position in task.cameras.items())}
    """
    equality = """
      <equality>
        <weld name="object_fixture" body1="task_target" active="true"/>
        <weld name="task_grasp" body1="left_wrist_yaw_link" body2="task_target" active="false"/>
      </equality>
    """
    text = source.read_text().replace("</worldbody>", additions + "</worldbody>", 1).replace("</mujoco>", equality + "</mujoco>", 1)
    scene = source.with_name("scene_s2a_task.xml")
    scene.write_text(text)

    simulator_dir = args.unitree_mujoco / "simulate_python"
    sys.path.insert(0, str(simulator_dir))
    sys.modules["config"] = SimpleNamespace(ROBOT="g1")
    from unitree_sdk2py_bridge import UnitreeSdk2Bridge

    model = mujoco.MjModel.from_xml_path(str(scene))
    model.opt.timestep = 0.002
    data = mujoco.MjData(model)
    if args.visualization_directory:
        args.visualization_directory.mkdir(parents=True, exist_ok=True)
    data.qpos[2] = 0.78
    data.qpos[7 : 7 + len(G1_FIX_STAND_POSITION_RAD)] = G1_FIX_STAND_POSITION_RAD
    mujoco.mj_forward(model, data)
    ChannelFactoryInitialize(args.domain_id, args.interface)
    bridge_class = (
        make_g1_vla_bridge(
            UnitreeSdk2Bridge,
            action_frequency_hz=args.vla_frequency_hz,
            stale_after_s=args.vla_stale_after_seconds,
            apply_vla_targets=not args.vla_typed_skill_passthrough,
            joint_indices=task.controller.joint_indices,
            joint_limits_rad=task.controller.joint_limits_rad,
            maximum_chunk_velocity_rad_s=task.controller.maximum_chunk_velocity_rad_s,
            maximum_chunk_acceleration_rad_s2=(
                task.controller.maximum_chunk_acceleration_rad_s2
            ),
            maximum_chunk_duration_s=task.controller.maximum_chunk_duration_s,
        )
        if args.vla_endpoint
        else UnitreeSdk2Bridge
    )
    bridge = bridge_class(model, data)
    bridge.low_state.mode_machine = 5
    coordinator = None
    online_renderers = None
    if args.vla_endpoint:
        vla_task = task.instruction
        coordinator = G1ChunkCoordinator(
            SmolVLAChunkClient(args.vla_endpoint),
            session_id=task.task_id,
            task=vla_task,
            frequency_hz=args.vla_frequency_hz,
        )
        online_renderers = {
            name: mujoco.Renderer(model, height=256, width=256)
            for name in ("camera1", "camera2", "camera3")
        }

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

    def render_observation() -> dict[str, bytes]:
        images = {}
        for name, renderer in online_renderers.items():
            renderer.update_scene(data, camera=name)
            images[name] = renderer.render().tobytes()
        return images

    def request_chunk() -> bool:
        started_rendering = monotonic()
        images = render_observation()
        overhead_ms = (monotonic() - started_rendering) * 1000
        return coordinator.request(
            data.qpos[7:36],
            images,
            request_overhead_ms=overhead_ms,
        )

    def adapt_chunk(chunk):
        return chunk

    def wait_for_chunk() -> None:
        inference_deadline = monotonic() + 30.0
        while monotonic() < inference_deadline:
            chunk = coordinator.poll()
            if chunk is not None:
                bridge.set_vla_chunk(adapt_chunk(chunk))
                return
            sleep(0.01)
        raise TimeoutError("no VLA action chunk received")

    if coordinator is not None:
        request_chunk()
        try:
            wait_for_chunk()
        except TimeoutError:
            coordinator.close()
            raise

    left = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "left_wrist_yaw_link")
    right = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "right_wrist_yaw_link")
    item = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "task_target")
    weld = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_EQUALITY, "task_grasp")
    fixture = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_EQUALITY, "object_fixture")
    initial_item = data.xpos[item].copy()
    visualization_qpos = {"ready": data.qpos.copy()}
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
    started_simulation_time = float(data.time)
    next_step = started
    steps = 0
    pending_chunk = None
    live_stop = Event()
    live_lock = Lock()
    live_qpos = data.qpos.copy()

    def render_live_frames() -> None:
        render_data = mujoco.MjData(model)
        renderer = mujoco.Renderer(model, height=180, width=320)
        while not live_stop.wait(1.0):
            with live_lock:
                render_data.qpos[:] = live_qpos
            mujoco.mj_forward(model, render_data)
            renderer.update_scene(render_data, camera="camera1")
            temporary = args.visualization_directory / ".live.png"
            write_rgb_png(temporary, renderer.render(), compression=1)
            temporary.replace(args.visualization_directory / "live.png")

    live_thread = None
    if args.visualization_directory:
        live_thread = Thread(target=render_live_frames, daemon=True)
        live_thread.start()
    while data.time - started_simulation_time < args.duration_seconds:
        mujoco.mj_step(model, data)
        steps += 1
        if live_thread is not None and steps % 25 == 0:
            with live_lock:
                live_qpos[:] = data.qpos
        if coordinator is not None:
            chunk = coordinator.poll()
            if chunk is not None:
                pending_chunk = adapt_chunk(chunk)
            if pending_chunk is not None and bridge.needs_vla_chunk(lookahead_actions=0):
                bridge.set_vla_chunk(pending_chunk)
                pending_chunk = None
            lookahead = 0 if args.vla_block_on_refresh else args.vla_refresh_lookahead_actions
            if (
                pending_chunk is None
                and bridge.needs_vla_chunk(lookahead_actions=lookahead)
                and not coordinator.in_flight
            ):
                request_chunk()
                next_step = monotonic()
                if args.vla_block_on_refresh:
                    wait_for_chunk()
                    next_step = monotonic()
        minimum_base_height = min(minimum_base_height, float(data.qpos[2]))
        maximum_item_height = max(maximum_item_height, float(data.xpos[item, 2]))
        maximum_left_hand_height = max(maximum_left_hand_height, float(data.xpos[left, 2]))
        left_distance = float(np.linalg.norm(data.xpos[left] - data.xpos[item]))
        right_distance = float(np.linalg.norm(data.xpos[right] - data.xpos[item]))
        minimum_left_distance = min(minimum_left_distance, left_distance)
        minimum_right_distance = min(minimum_right_distance, right_distance)
        if fell_at_seconds is None and data.qpos[2] < task.verification.minimum_base_height_m:
            fell_at_seconds = float(data.time)
        if (
            not grasped
            and data.time > task.verification.grasp_after_s
            and left_distance < task.verification.grasp_distance_m
            and right_distance < task.verification.grasp_distance_m
        ):
            position, quaternion = relative_pose(data, left, item)
            model.eq_data[weld, 3:6] = position
            model.eq_data[weld, 6:10] = quaternion
            data.eq_active[fixture] = 0
            data.eq_active[weld] = 1
            grasped = True
            grasped_at_seconds = float(data.time)
            visualization_qpos["grasp"] = data.qpos.copy()
        drop_zone_delta = data.xpos[item, :2] - np.asarray(destination.position[:2])
        object_lifted = maximum_item_height - initial_item[2] >= task.verification.minimum_lift_m
        if object_lifted and "lift" not in visualization_qpos:
            visualization_qpos["lift"] = data.qpos.copy()
        object_over_drop_zone = all(
            abs(delta) <= extent - target.size[index]
            for index, (delta, extent) in enumerate(zip(drop_zone_delta, destination.size[:2]))
        )
        object_lowered_for_release = data.xpos[item, 2] <= task.verification.release_height_m
        release_ready = (
            data.time > task.verification.release_after_s
            and object_lifted
            and object_over_drop_zone
            and object_lowered_for_release
        )
        if grasped and not released and (release_ready or data.time > args.release_timeout_seconds):
            data.eq_active[weld] = 0
            released = True
            released_at_seconds = float(data.time)
            object_position_at_release = data.xpos[item].tolist()
            visualization_qpos["release"] = data.qpos.copy()
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

    live_stop.set()
    if live_thread is not None:
        live_thread.join(timeout=2.0)

    if coordinator is not None:
        coordinator.close()
        final_chunk = coordinator.poll()
        if final_chunk is not None:
            bridge.set_vla_chunk(final_chunk)
        for _ in range(bridge.vla_stale_fallbacks):
            coordinator.metrics.record_stale_fallback()
    final_item = data.xpos[item].copy()
    visualization_qpos["final"] = data.qpos.copy()
    drop_zone_delta = final_item[:2] - np.asarray(destination.position[:2])
    report = {
        "simulator": "unitreerobotics/unitree_mujoco",
        "model": "g1_29dof",
        "sdk2_lowcmd_frames": command_count,
        "grasped": grasped,
        "released": released,
        "initial_object_position_xyz_m": initial_item.tolist(),
        "final_object_position_xyz_m": final_item.tolist(),
        "object_planar_displacement_m": hypot(float(final_item[0] - initial_item[0]), float(final_item[1] - initial_item[1])),
        "task_spec": str(args.task_spec),
        "task_id": task.task_id,
        "task": {"skill": task.skill, "arguments": task.arguments, "instruction": task.instruction},
        "verification": {
            "minimum_lift_m": task.verification.minimum_lift_m,
            "minimum_base_height_m": task.verification.minimum_base_height_m,
        },
        "drop_zone_center_xy_m": list(destination.position[:2]),
        "drop_zone_half_extents_xy_m": list(destination.size[:2]),
        "final_drop_zone_error_m": hypot(float(drop_zone_delta[0]), float(drop_zone_delta[1])),
        "final_object_center_in_drop_zone": bool(
            abs(drop_zone_delta[0]) <= destination.size[0]
            and abs(drop_zone_delta[1]) <= destination.size[1]
        ),
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
    if coordinator is not None:
        report["vla_overlay_frames"] = bridge.vla_overlay_frames
        report["maximum_vla_joint_delta_rad"] = bridge.maximum_vla_joint_delta_rad
        report["vla_authorized_frames"] = bridge.vla_authorized_frames
        report["vla_runtime"] = coordinator.metrics.report()
        report["vla_task"] = vla_task
        report["vla_task_binding"] = {
            "skill": task.skill,
            "arguments": task.arguments,
            "source": args.plan_source,
        }
        report["vla_first_chunk_latency_ms"] = report["vla_runtime"][
            "first_chunk_round_trip_ms"
        ]
    if args.visualization_directory:
        render_data = mujoco.MjData(model)
        renderer = mujoco.Renderer(model, height=360, width=640)
        visualization_frames = []
        for index, (stage, qpos) in enumerate(visualization_qpos.items()):
            render_data.qpos[:] = qpos
            mujoco.mj_forward(model, render_data)
            renderer.update_scene(render_data, camera="camera1")
            filename = f"{index:02d}-{stage}.png"
            write_rgb_png(args.visualization_directory / filename, renderer.render())
            visualization_frames.append({"stage": stage, "file": f"{args.visualization_directory.name}/{filename}"})
        report["visualization_frames"] = visualization_frames
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
            task=np.asarray(task.instruction),
        )


if __name__ == "__main__":
    main()
