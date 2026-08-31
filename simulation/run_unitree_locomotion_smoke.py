#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path


def git_head(path: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


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
    minimum_height: float,
    minimum_distance: float,
    video_path: Path | None = None,
) -> dict[str, object]:
    os.environ.setdefault("MUJOCO_GL", "egl")
    try:
        import imageio.v2 as imageio
        import mujoco
        import numpy as np
        import torch
        import yaml
    except ImportError as error:
        raise RuntimeError(f"missing runtime dependency: {error.name}") from error

    vendor = project / "simulation/vendor/unitree_rl_gym"
    config_path = vendor / "deploy/deploy_mujoco/configs/g1.yaml"
    config = yaml.safe_load(config_path.read_text())
    expand = lambda value: Path(value.replace("{LEGGED_GYM_ROOT_DIR}", str(vendor)))
    policy_path = expand(config["policy_path"])
    model_path = expand(config["xml_path"])

    dt = float(config["simulation_dt"])
    decimation = int(config["control_decimation"])
    kp = np.asarray(config["kps"], dtype=np.float32)
    kd = np.asarray(config["kds"], dtype=np.float32)
    default = np.asarray(config["default_angles"], dtype=np.float32)
    command = np.asarray(config["cmd_init"], dtype=np.float32)
    command_scale = np.asarray(config["cmd_scale"], dtype=np.float32)
    action_scale = float(config["action_scale"])
    num_actions = int(config["num_actions"])
    obs = np.zeros(int(config["num_obs"]), dtype=np.float32)
    action = np.zeros(num_actions, dtype=np.float32)
    target = default.copy()

    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)
    model.opt.timestep = dt
    policy = torch.jit.load(str(policy_path), map_location="cpu")
    total_steps = round(duration / dt)
    minimum_z = math.inf
    renderer = mujoco.Renderer(model, height=368, width=640) if video_path else None
    camera = mujoco.MjvCamera() if video_path else None
    writer = imageio.get_writer(video_path, fps=30, codec="libx264", quality=8) if video_path else None
    video_frames = 0
    next_frame_time = 0.0

    try:
        for step in range(1, total_steps + 1):
            data.ctrl[:] = (target - data.qpos[7:]) * kp - data.qvel[6:] * kd
            mujoco.mj_step(model, data)
            minimum_z = min(minimum_z, float(data.qpos[2]))
            simulation_time = step * dt
            if writer and renderer and camera and simulation_time >= next_frame_time:
                camera.lookat[:] = [float(data.qpos[0]) + 0.35, float(data.qpos[1]), 0.65]
                camera.distance = 3.0
                camera.azimuth = 135
                camera.elevation = -16
                renderer.update_scene(data, camera=camera)
                writer.append_data(renderer.render())
                video_frames += 1
                next_frame_time += 1 / 30
            if step % decimation:
                continue

            q = (data.qpos[7:] - default) * float(config["dof_pos_scale"])
            dq = data.qvel[6:] * float(config["dof_vel_scale"])
            qw, qx, qy, qz = data.qpos[3:7]
            gravity = np.asarray(
                [2 * (-qz * qx + qw * qy), -2 * (qz * qy + qw * qx), 1 - 2 * (qw * qw + qz * qz)],
                dtype=np.float32,
            )
            phase = (step * dt % 0.8) / 0.8
            obs[:3] = data.qvel[3:6] * float(config["ang_vel_scale"])
            obs[3:6] = gravity
            obs[6:9] = command * command_scale
            obs[9:21] = q
            obs[21:33] = dq
            obs[33:45] = action
            obs[45:47] = [math.sin(2 * math.pi * phase), math.cos(2 * math.pi * phase)]
            with torch.inference_mode():
                action = policy(torch.from_numpy(obs).unsqueeze(0)).numpy().squeeze()
            target = action * action_scale + default
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
    }
    verdict = evaluate(metrics, minimum_height, minimum_distance)
    lock = json.loads((project / "simulation/whole_body.lock.json").read_text())
    expected_commit = lock["unitree_rl_gym"]["commit"]
    actual_commit = git_head(vendor)
    verdict["checks"]["pinned_commit"] = actual_commit == expected_commit
    verdict["passed"] = all(verdict["checks"].values())
    return {
        "schema_version": 1,
        "profile": "unitree-official-g1-locomotion-headless",
        "passed": verdict["passed"],
        "checks": verdict["checks"],
        "thresholds": {
            "minimum_height_m": minimum_height,
            "minimum_forward_distance_m": minimum_distance,
        },
        "metrics": metrics,
        "video": str(video_path.relative_to(project)) if video_path else None,
        "provenance": {
            "repository": lock["unitree_rl_gym"]["repository"],
            "expected_commit": expected_commit,
            "actual_commit": actual_commit,
            "policy": str(policy_path.relative_to(project)),
            "model": str(model_path.relative_to(project)),
            "config": str(config_path.relative_to(project)),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the pinned Unitree G1 locomotion policy in headless MuJoCo")
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--minimum-height", type=float, default=0.65)
    parser.add_argument("--minimum-distance", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=Path("reports/simulation/unitree-locomotion-smoke.json"))
    parser.add_argument("--video", type=Path, help="record the same rollout as a 640x368 H.264 MP4")
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error("--duration must be positive")
    try:
        project = args.project.resolve()
        video = None if args.video is None else (args.video if args.video.is_absolute() else project / args.video)
        if video:
            video.parent.mkdir(parents=True, exist_ok=True)
        report = run(project, args.duration, args.minimum_height, args.minimum_distance, video)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    output = args.output if args.output.is_absolute() else args.project.resolve() / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
