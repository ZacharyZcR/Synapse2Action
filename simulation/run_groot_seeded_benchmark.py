#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from synapse2action.groot_benchmark import summarize_groot_episodes


PROJECT = Path(__file__).resolve().parents[1]
EVIDENCE = PROJECT / "reports" / "simulation" / "g1-groot-closed-loop-evidence.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reproducible GR00T stage benchmarks")
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=PROJECT / "reports" / "simulation" / "groot-benchmark",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse validated evidence files already present in the output directory",
    )
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds):
        parser.error("--seeds must be unique")

    output = args.output_directory
    output.mkdir(parents=True, exist_ok=True)
    episodes: list[dict[str, object]] = []
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(PROJECT / "src"), env.get("PYTHONPATH")))
    )
    for seed in args.seeds:
        evidence_report = output / f"evidence-seed-{seed}.json"
        if args.resume and evidence_report.is_file():
            current = json.loads(evidence_report.read_text()).get("episodes", [])
            if len(current) != 1 or current[0].get("seed") != seed:
                raise RuntimeError(f"seed {seed} has invalid resumable evidence")
            episodes.append(current[0])
            (output / "summary.json").write_text(
                json.dumps(summarize_groot_episodes(episodes), indent=2) + "\n"
            )
            print(f"seed {seed}: resumed", flush=True)
            continue
        harness_report = output / f"harness-seed-{seed}.json"
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
                "--seed",
                str(seed),
                "--output",
                str(harness_report),
            ),
            cwd=PROJECT,
            env=env,
            check=False,
        )
        if not EVIDENCE.exists():
            raise RuntimeError(f"seed {seed} produced no evidence (exit {completed.returncode})")
        payload = json.loads(EVIDENCE.read_text())
        current = payload.get("episodes", [])
        if len(current) != 1 or current[0].get("seed") != seed:
            raise RuntimeError(f"seed {seed} produced invalid evidence")
        episodes.append(current[0])
        evidence_report.write_text(
            json.dumps({"episodes": current}, indent=2) + "\n"
        )
        (output / "summary.json").write_text(
            json.dumps(summarize_groot_episodes(episodes), indent=2) + "\n"
        )
        print(f"seed {seed}: completed (runner exit {completed.returncode})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
