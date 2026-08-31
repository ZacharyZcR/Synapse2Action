#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from synapse2action.groot_benchmark import compare_groot_counterfactuals


PROJECT = Path(__file__).resolve().parents[1]
LIVE_EVIDENCE = PROJECT / "reports" / "simulation" / "g1-groot-closed-loop-evidence.json"
VARIANTS = {
    "baseline": {"n_action_steps": 20, "max_episode_steps": 1440},
    "short_horizon": {"n_action_steps": 10, "max_episode_steps": 1440},
    "extended_budget": {"n_action_steps": 20, "max_episode_steps": 1800},
}


def load_episode(
    path: Path,
    seed: int,
    intervention: dict[str, int] | None = None,
) -> dict[str, object]:
    episodes = json.loads(path.read_text()).get("episodes", [])
    if len(episodes) != 1 or episodes[0].get("seed") != seed:
        raise RuntimeError(f"seed {seed} produced invalid evidence: {path}")
    if intervention is not None and episodes[0].get("intervention") != intervention:
        raise RuntimeError(f"seed {seed} has mismatched intervention: {path}")
    return episodes[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run paired GR00T lift counterfactuals")
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=PROJECT / "reports" / "simulation" / "groot-lift-counterfactual",
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds):
        parser.error("--seeds must be unique")

    args.output_directory.mkdir(parents=True, exist_ok=True)
    collected: dict[str, list[dict[str, object]]] = {}
    for name, intervention in VARIANTS.items():
        variant_directory = args.output_directory / name
        variant_directory.mkdir(exist_ok=True)
        collected[name] = []
        for seed in args.seeds:
            evidence_path = variant_directory / f"evidence-seed-{seed}.json"
            if args.resume and evidence_path.is_file():
                collected[name].append(load_episode(evidence_path, seed, intervention))
                continue
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join(
                filter(None, (str(PROJECT / "src"), env.get("PYTHONPATH")))
            )
            env["S2A_GROOT_N_ACTION_STEPS"] = str(intervention["n_action_steps"])
            env["S2A_GROOT_MAX_EPISODE_STEPS"] = str(intervention["max_episode_steps"])
            LIVE_EVIDENCE.unlink(missing_ok=True)
            completed = subprocess.run(
                (
                    sys.executable,
                    str(PROJECT / "simulation" / "run_harness_unitree.py"),
                    "--task",
                    "pick-place",
                    "--policy",
                    "groot",
                    "--planner",
                    "mock",
                    "--allow-test-doubles",
                    "--task-spec",
                    "experiments/tasks/g1_groot_apple_to_plate.json",
                    "--seed",
                    str(seed),
                    "--output",
                    str(variant_directory / f"harness-seed-{seed}.json"),
                ),
                cwd=PROJECT,
                env=env,
                check=False,
            )
            if not LIVE_EVIDENCE.is_file():
                raise RuntimeError(f"{name} seed {seed} produced no evidence")
            episode = load_episode(LIVE_EVIDENCE, seed)
            episode["intervention"] = intervention
            evidence_path.write_text(json.dumps({"episodes": [episode]}, indent=2) + "\n")
            collected[name].append(episode)
            print(f"{name} seed {seed}: runner exit {completed.returncode}", flush=True)
    report = compare_groot_counterfactuals(collected)
    report["interventions"] = VARIANTS
    (args.output_directory / "summary.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
