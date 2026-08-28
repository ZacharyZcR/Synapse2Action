from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import monotonic

import numpy as np
import torch

from lerobot.policies import make_pre_post_processors
from lerobot.policies.smolvla import SmolVLAPolicy
from lerobot.policies.utils import prepare_observation_for_inference


def camera_views() -> dict[str, np.ndarray]:
    overhead = np.zeros((256, 256, 3), dtype=np.uint8)
    overhead[92:164, 55:115] = (220, 30, 25)
    overhead[82:174, 175:235] = (25, 180, 45)
    left = np.roll(overhead, 18, axis=1)
    right = np.roll(overhead, -18, axis=1)
    return {
        "observation.images.camera1": overhead,
        "observation.images.camera2": left,
        "observation.images.camera3": right,
    }


def infer(
    policy: SmolVLAPolicy,
    preprocess,
    postprocess,
    task: str,
) -> tuple[list[float], float]:
    raw = {
        "observation.state": np.zeros(6, dtype=np.float32),
        **camera_views(),
    }
    observation = prepare_observation_for_inference(raw, torch.device("cpu"), task, "unitree_g1")
    policy.reset()
    started = monotonic()
    with torch.inference_mode():
        action = postprocess(policy.select_action(preprocess(observation)))
    latency = monotonic() - started
    values = action.detach().cpu().reshape(-1).tolist()
    if len(values) != 6 or not all(np.isfinite(values)):
        raise RuntimeError("SmolVLA returned an invalid action")
    return values, latency


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real SmolVLA language-conditioned CPU inference")
    parser.add_argument("--model", default="lerobot/smolvla_base")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = SmolVLAPolicy.from_pretrained(args.model)
    policy.eval()
    preprocess, postprocess = make_pre_post_processors(
        policy.config,
        args.model,
        preprocessor_overrides={"device_processor": {"device": "cpu"}},
    )
    tasks = (
        "pick the red block and place it in the green tray",
        "leave the red block where it is and move away",
    )
    predictions = []
    for task in tasks:
        action, latency = infer(policy, preprocess, postprocess, task)
        predictions.append({"task": task, "action": action, "latency_seconds": latency})
    action_distance = float(np.linalg.norm(np.array(predictions[0]["action"]) - predictions[1]["action"]))
    report = {
        "accepted": action_distance > 1e-6,
        "model": args.model,
        "policy_class": type(policy).__name__,
        "parameter_count": sum(parameter.numel() for parameter in policy.parameters()),
        "device": "cpu",
        "input_features": {name: list(feature.shape) for name, feature in policy.config.input_features.items()},
        "output_features": {name: list(feature.shape) for name, feature in policy.config.output_features.items()},
        "predictions": predictions,
        "language_conditioned_action_distance": action_distance,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(not report["accepted"])


if __name__ == "__main__":
    main()
