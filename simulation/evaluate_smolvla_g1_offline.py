from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from lerobot.policies import make_pre_post_processors
from lerobot.policies.smolvla import SmolVLAPolicy
from lerobot.policies.utils import prepare_observation_for_inference


ARM_WAIST_JOINTS = np.asarray((12, 15, 16, 17, 18, 22, 23, 24, 25))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate G1 SmolVLA chunks on a recorded episode")
    parser.add_argument("model", type=Path)
    parser.add_argument("episode", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--predictions-output", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    torch.manual_seed(args.seed)
    episode = np.load(args.episode)
    policy = SmolVLAPolicy.from_pretrained(args.model)
    policy.eval()
    preprocess, postprocess = make_pre_post_processors(
        policy.config,
        str(args.model),
        preprocessor_overrides={"device_processor": {"device": "cpu"}},
    )
    task = str(episode["task"].item())
    predictions, targets = [], []
    segments = []
    for start in range(0, len(episode["action"]), policy.config.chunk_size):
        raw = {
            "observation.state": episode["observation_state"][start],
            **{f"observation.images.camera{i}": episode[f"images_camera{i}"][start] for i in (1, 2, 3)},
        }
        observation = prepare_observation_for_inference(raw, torch.device("cpu"), task, "unitree_g1")
        policy.reset()
        count = min(policy.config.chunk_size, len(episode["action"]) - start)
        chunk = []
        with torch.inference_mode():
            for _ in range(count):
                action = postprocess(policy.select_action(preprocess(observation)))
                chunk.append(action.detach().cpu().numpy().reshape(-1))
        predicted = np.stack(chunk)
        target = episode["action"][start : start + count]
        predictions.append(predicted)
        targets.append(target)
        segments.append({
            "start_frame": start,
            "frames": count,
            "mse": float(np.mean((predicted - target) ** 2)),
            "arm_waist_mse": float(np.mean((predicted[:, ARM_WAIST_JOINTS] - target[:, ARM_WAIST_JOINTS]) ** 2)),
        })
    predicted = np.concatenate(predictions)
    target = np.concatenate(targets)
    report = {
        "model": str(args.model),
        "frames": len(target),
        "segments": segments,
        "mse": float(np.mean((predicted - target) ** 2)),
        "mae": float(np.mean(np.abs(predicted - target))),
        "arm_waist_mse": float(np.mean((predicted[:, ARM_WAIST_JOINTS] - target[:, ARM_WAIST_JOINTS]) ** 2)),
        "finite": bool(np.isfinite(predicted).all()),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.predictions_output:
        args.predictions_output.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(args.predictions_output, predicted=predicted, target=target)
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(not report["finite"])


if __name__ == "__main__":
    main()
