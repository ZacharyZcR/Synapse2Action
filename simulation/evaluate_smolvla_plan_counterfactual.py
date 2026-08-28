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


TASK_B = "leave the red block where it is and move away"


def infer_chunk(policy, preprocess, postprocess, raw, task: str, seed: int) -> tuple[np.ndarray, float]:
    torch.manual_seed(seed)
    policy.reset()
    observation = prepare_observation_for_inference(
        {name: value.copy() for name, value in raw.items()},
        torch.device("cpu"),
        task,
        "unitree_g1",
    )
    started = monotonic()
    actions = []
    with torch.inference_mode():
        for _ in range(policy.config.chunk_size):
            action = postprocess(policy.select_action(preprocess(observation)))
            actions.append(action.detach().cpu().numpy().reshape(-1))
    return np.stack(actions), monotonic() - started


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure real G1 SmolVLA plan responsiveness")
    parser.add_argument("model", type=Path)
    parser.add_argument("episode", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--minimum-rms-delta", type=float, default=1e-4)
    args = parser.parse_args()

    episode = np.load(args.episode)
    policy = SmolVLAPolicy.from_pretrained(args.model)
    policy.eval()
    preprocess, postprocess = make_pre_post_processors(
        policy.config,
        str(args.model),
        preprocessor_overrides={"device_processor": {"device": "cpu"}},
    )
    raw = {
        "observation.state": episode["observation_state"][0],
        **{f"observation.images.camera{i}": episode[f"images_camera{i}"][0] for i in (1, 2, 3)},
    }
    tasks = (str(episode["task"].item()), TASK_B)
    predictions = [infer_chunk(policy, preprocess, postprocess, raw, task, args.seed) for task in tasks]
    delta = predictions[0][0] - predictions[1][0]
    rms_delta = float(np.sqrt(np.mean(delta**2)))
    report = {
        "benchmark": "smolvla_plan_counterfactual",
        "changed": rms_delta >= args.minimum_rms_delta,
        "same_observation": True,
        "same_seed": True,
        "seed": args.seed,
        "model": str(args.model),
        "episode": str(args.episode),
        "tasks": list(tasks),
        "chunk_frames": int(delta.shape[0]),
        "action_dimensions": int(delta.shape[1]),
        "action_rms_delta": rms_delta,
        "action_l2_distance": float(np.linalg.norm(delta)),
        "action_max_abs_delta": float(np.max(np.abs(delta))),
        "minimum_rms_delta": args.minimum_rms_delta,
        "latency_seconds": [latency for _, latency in predictions],
        "finite": bool(all(np.isfinite(actions).all() for actions, _ in predictions)),
    }
    report["changed"] = bool(report["changed"] and report["finite"])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(not report["changed"])


if __name__ == "__main__":
    main()
