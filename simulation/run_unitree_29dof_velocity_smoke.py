#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import deque
import json
import math
import os
from pathlib import Path
import subprocess
import sys


TERM_ORDER = (
    "base_ang_vel",
    "projected_gravity",
    "velocity_commands",
    "joint_pos_rel",
    "joint_vel_rel",
    "last_action",
)


def git_head(path: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def append_history(history: dict[str, deque], terms: dict[str, object]) -> None:
    for name in TERM_ORDER:
        history[name].append(terms[name])


def flatten_history(history: dict[str, deque]) -> list[float]:
    return [float(value) for name in TERM_ORDER for frame in history[name] for value in frame]


def evaluate(metrics: dict[str, object], minimum_height: float, minimum_distance: float) -> dict[str, object]:
    checks = {
        "finite": bool(metrics["finite"]),
        "minimum_height": float(metrics["minimum_height_m"]) >= minimum_height,
        "forward_distance": float(metrics["forward_distance_m"]) >= minimum_distance,
        "physics_steps": int(metrics["physics_steps"]) > 0,
    }
    return {"passed": all(checks.values()), "checks": checks}


def run(
    project: Path,
    duration: float,
    command_x: float,
    minimum_height: float,
    minimum_distance: float,
    video_path: Path | None,
) -> dict[str, object]:
    os.environ.setdefault("MUJOCO_GL", "egl")
    try:
        import mujoco
        import numpy as np
        import onnxruntime as ort
        import yaml
    except ImportError as error:
        raise RuntimeError(f"missing runtime dependency: {error.name}") from error

    lab = project / "simulation/vendor/unitree_rl_lab"
    simulator = project / "simulation/vendor/unitree_mujoco"
    policy_root = lab / "deploy/robots/g1_29dof/config/policy/velocity/v0"
    config_path = policy_root / "params/deploy.yaml"
    policy_path = policy_root / "exported/policy.onnx"
    model_path = simulator / "unitree_robots/g1/scene_29dof.xml"
    config = yaml.safe_load(config_path.read_text())

    joint_map = np.asarray(config["joint_ids_map"], dtype=np.int32)
    stiffness = np.asarray(config["stiffness"], dtype=np.float64)
    damping = np.asarray(config["damping"], dtype=np.float64)
    default = np.asarray(config["default_joint_pos"], dtype=np.float64)
    action_scale = np.asarray(config["actions"]["JointPositionAction"]["scale"], dtype=np.float64)
    step_dt = float(config["step_dt"])
    command = np.asarray([command_x, 0.0, 0.0], dtype=np.float32)

    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)
    model.opt.timestep = 0.002
    if model.nu != 29 or len(joint_map) != 29:
        raise RuntimeError("official 29-DoF model and policy mapping are required")

    # The official FixStand target is the policy default expressed in policy order.
    target_dds = np.zeros(29, dtype=np.float64)
    target_dds[joint_map] = default
    data.qpos[7:] = target_dds
    mujoco.mj_forward(model, data)

    session = ort.InferenceSession(str(policy_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    action = np.zeros(29, dtype=np.float32)
    history: dict[str, deque] = {name: deque(maxlen=5) for name in TERM_ORDER}

    renderer = mujoco.Renderer(model, height=192, width=320) if video_path else None
    camera = mujoco.MjvCamera() if video_path else None
    writer = None
    if video_path:
        try:
            import imageio.v2 as imageio
        except ImportError as error:
            raise RuntimeError("video capture requires imageio") from error
        writer = imageio.get_writer(video_path, fps=30, codec="libx264", quality=8)

    control_decimation = round(step_dt / model.opt.timestep)
    total_steps = round(duration / model.opt.timestep)
    minimum_z = math.inf
    video_frames = 0
    next_frame_time = 0.0

    def observations() -> dict[str, object]:
        inverse_quat = data.qpos[3:7].copy()
        inverse_quat[1:] *= -1
        gravity = np.empty(3, dtype=np.float64)
        mujoco.mju_rotVecQuat(gravity, np.asarray([0.0, 0.0, -1.0]), inverse_quat)
        joint_pos_policy = data.qpos[7:][joint_map]
        joint_vel_policy = data.qvel[6:][joint_map]
        return {
            "base_ang_vel": np.asarray(data.qvel[3:6] * 0.2, dtype=np.float32),
            "projected_gravity": np.asarray(gravity, dtype=np.float32),
            "velocity_commands": command,
            "joint_pos_rel": np.asarray(joint_pos_policy - default, dtype=np.float32),
            "joint_vel_rel": np.asarray(joint_vel_policy * 0.05, dtype=np.float32),
            "last_action": action,
        }

    initial_terms = observations()
    for _ in range(5):
        append_history(history, initial_terms)

    try:
        for step in range(total_steps):
            data.ctrl[:] = stiffness * (target_dds - data.qpos[7:]) - damping * data.qvel[6:]
            mujoco.mj_step(model, data)
            minimum_z = min(minimum_z, float(data.qpos[2]))
            simulation_time = (step + 1) * model.opt.timestep

            if writer and renderer and camera and simulation_time >= next_frame_time:
                camera.lookat[:] = [float(data.qpos[0]) + 0.3, float(data.qpos[1]), 0.75]
                camera.distance = 3.0
                camera.azimuth = 135
                camera.elevation = -16
                renderer.update_scene(data, camera=camera)
                writer.append_data(renderer.render())
                video_frames += 1
                next_frame_time += 1 / 30

            if (step + 1) % control_decimation:
                continue
            append_history(history, observations())
            obs = np.asarray(flatten_history(history), dtype=np.float32)[None, :]
            if obs.shape != (1, 480):
                raise RuntimeError(f"unexpected policy observation shape: {obs.shape}")
            action = session.run([output_name], {input_name: obs})[0].squeeze().astype(np.float32)
            target_dds[joint_map] = default + action_scale * action
    finally:
        if writer:
            writer.close()
        if renderer:
            renderer.close()

    values = [float(value) for value in data.qpos]
    metrics: dict[str, object] = {
        "duration_s": duration,
        "physics_steps": total_steps,
        "minimum_height_m": minimum_z,
        "final_height_m": float(data.qpos[2]),
        "forward_distance_m": float(data.qpos[0]),
        "lateral_distance_m": float(data.qpos[1]),
        "finite": all(math.isfinite(value) for value in values),
        "video_frames": video_frames,
        "model_dofs": int(model.nu),
        "observation_width": 480,
        "action_width": int(action.size),
    }
    verdict = evaluate(metrics, minimum_height, minimum_distance)
    lock = json.loads((project / "simulation/whole_body.lock.json").read_text())
    commits = {"unitree_rl_lab": git_head(lab), "unitree_mujoco": git_head(simulator)}
    for name, actual in commits.items():
        verdict["checks"][f"{name}_commit"] = actual == lock[name]["commit"]
    verdict["passed"] = all(verdict["checks"].values())
    return {
        "schema_version": 1,
        "profile": "unitree-official-g1-29dof-velocity-headless",
        "passed": verdict["passed"],
        "checks": verdict["checks"],
        "thresholds": {"minimum_height_m": minimum_height, "minimum_forward_distance_m": minimum_distance},
        "metrics": metrics,
        "video": str(video_path.relative_to(project)) if video_path else None,
        "provenance": {
            "policy": str(policy_path.relative_to(project)),
            "model": str(model_path.relative_to(project)),
            "config": str(config_path.relative_to(project)),
            "commits": commits,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Unitree's matching G1 29-DoF velocity policy in MuJoCo")
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--command-x", type=float, default=0.5)
    parser.add_argument("--minimum-height", type=float, default=0.65)
    parser.add_argument("--minimum-distance", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=Path("reports/simulation/unitree-29dof-velocity-smoke.json"))
    parser.add_argument("--video", type=Path)
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error("--duration must be positive")
    project = args.project.resolve()
    video = None if args.video is None else (args.video if args.video.is_absolute() else project / args.video)
    if video:
        video.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = run(project, args.duration, args.command_x, args.minimum_height, args.minimum_distance, video)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    output = args.output if args.output.is_absolute() else project / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
