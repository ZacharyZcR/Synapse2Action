from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from lerobot.datasets.lerobot_dataset import LeRobotDataset


def wait_for_local_metadata(root: Path, timeout: float = 10.0) -> None:
    required = (
        root / "meta/info.json",
        root / "meta/tasks.parquet",
        root / "meta/episodes/chunk-000/file-000.parquet",
        root / "data/chunk-000/file-000.parquet",
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if all(path.is_file() for path in required):
            return
        time.sleep(0.05)
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    raise FileNotFoundError(f"dataset metadata did not become visible: {missing}")


def validate_dataset(root: Path, repo_id: str, frame_count: int, task: str) -> dict[str, object]:
    wait_for_local_metadata(root)
    reopened = LeRobotDataset(repo_id, root=root)
    first = reopened[0]
    last = reopened[len(reopened) - 1]
    checks = {
        "frame_count": len(reopened) == frame_count == 140,
        "one_episode": reopened.meta.total_episodes == 1,
        "fps": reopened.fps == 10,
        "state_shape": tuple(first["observation.state"].shape) == (29,),
        "action_shape": tuple(last["action"].shape) == (29,),
        "three_cameras": all(
            tuple(first[f"observation.images.camera{index}"].shape) == (3, 256, 256)
            for index in (1, 2, 3)
        ),
        "task": first["task"] == task,
    }
    return {
        "accepted": all(checks.values()),
        "checks": checks,
        "dataset_format": "LeRobotDataset v3",
        "repo_id": repo_id,
        "root": str(root),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a recorded SDK2 G1 episode to LeRobotDataset v3")
    parser.add_argument("episode", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--repo-id", default="synapse2action/g1-pick-place-sim")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.validate_only:
        raise FileExistsError(f"dataset output already exists: {args.output}")

    episode = np.load(args.episode)
    frame_count = len(episode["timestamp"])
    expected = {
        "observation_state": (frame_count, 29),
        "action": (frame_count, 29),
        "images_camera1": (frame_count, 256, 256, 3),
        "images_camera2": (frame_count, 256, 256, 3),
        "images_camera3": (frame_count, 256, 256, 3),
    }
    for key, shape in expected.items():
        if episode[key].shape != shape:
            raise ValueError(f"{key} has shape {episode[key].shape}, expected {shape}")
    task = str(episode["task"].item())
    if args.validate_only:
        report = validate_dataset(args.output, args.repo_id, frame_count, task)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps(report, sort_keys=True))
        raise SystemExit(not report["accepted"])

    features = {
        "observation.state": {"dtype": "float32", "shape": (29,), "names": None},
        "observation.images.camera1": {"dtype": "image", "shape": (3, 256, 256), "names": ["channels", "height", "width"]},
        "observation.images.camera2": {"dtype": "image", "shape": (3, 256, 256), "names": ["channels", "height", "width"]},
        "observation.images.camera3": {"dtype": "image", "shape": (3, 256, 256), "names": ["channels", "height", "width"]},
        "action": {"dtype": "float32", "shape": (29,), "names": None},
    }
    dataset = LeRobotDataset.create(
        args.repo_id,
        fps=10,
        root=args.output,
        robot_type="unitree_g1",
        features=features,
        use_videos=False,
        image_writer_threads=4,
    )
    for index in range(frame_count):
        dataset.add_frame({
            "observation.state": episode["observation_state"][index],
            "observation.images.camera1": episode["images_camera1"][index],
            "observation.images.camera2": episode["images_camera2"][index],
            "observation.images.camera3": episode["images_camera3"][index],
            "action": episode["action"][index],
            "task": task,
        })
    dataset.save_episode()
    report = validate_dataset(args.output, args.repo_id, frame_count, task)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(not report["accepted"])


if __name__ == "__main__":
    main()
