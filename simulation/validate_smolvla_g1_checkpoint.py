from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from lerobot.policies import make_pre_post_processors
from lerobot.policies.smolvla import SmolVLAPolicy
from lerobot.policies.utils import prepare_observation_for_inference


def predict(model: Path, episode: np.lib.npyio.NpzFile, task: str) -> np.ndarray:
    torch.manual_seed(0)
    policy = SmolVLAPolicy.from_pretrained(model)
    policy.eval()
    preprocess, postprocess = make_pre_post_processors(
        policy.config,
        str(model),
        preprocessor_overrides={"device_processor": {"device": "cpu"}},
    )
    raw = {
        "observation.state": episode["observation_state"][0],
        **{f"observation.images.camera{i}": episode[f"images_camera{i}"][0] for i in (1, 2, 3)},
    }
    observation = prepare_observation_for_inference(raw, torch.device("cpu"), task, "unitree_g1")
    with torch.inference_mode():
        action = postprocess(policy.select_action(preprocess(observation)))
    return action.detach().cpu().numpy().reshape(-1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a trained 29-DOF G1 SmolVLA checkpoint")
    parser.add_argument("model", type=Path)
    parser.add_argument("episode", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    episode = np.load(args.episode)
    task = str(episode["task"].item())
    action = predict(args.model, episode, task)
    config = json.loads((args.model / "config.json").read_text())
    checks = {
        "state_dimension": config["input_features"]["observation.state"]["shape"] == [29],
        "action_dimension": config["output_features"]["action"]["shape"] == [29],
        "three_cameras": sum(key.startswith("observation.images.") for key in config["input_features"]) == 3,
        "finite_action": action.shape == (29,) and bool(np.isfinite(action).all()),
    }
    report = {
        "accepted": all(checks.values()),
        "checks": checks,
        "model": str(args.model),
        "action": action.tolist(),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(not report["accepted"])


if __name__ == "__main__":
    main()
