from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .demo import DEFAULT_SCENARIO, acquire_demo_eeg, load_demo_scenario, run_demo
from .demo_suite import run_demo_suite
from .experiments import run_suite
from .eeg import load_recording, save_recording
from .monte_carlo import run_monte_carlo
from .llm_planner import OpenAICompatiblePlanner
from .synthetic_intent import run_intent_suite
from .visualization import render_demo_html


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic hardware-free experiments")
    parser.add_argument("directory", nargs="?", type=Path, default=Path("experiments/scenarios"))
    parser.add_argument("--intent-directory", type=Path)
    parser.add_argument("--monte-carlo-config", type=Path)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--demo-html", type=Path)
    parser.add_argument("--demo-scenario", type=Path)
    parser.add_argument("--demo-suite", type=Path)
    parser.add_argument("--artifact-directory", type=Path)
    parser.add_argument("--record-eeg", type=Path)
    parser.add_argument("--replay-eeg", type=Path)
    parser.add_argument("--planner-base-url")
    parser.add_argument("--planner-model")
    parser.add_argument("--planner-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.demo_suite:
        report = run_demo_suite(args.demo_suite, args.artifact_directory)
    elif args.demo or args.demo_html or args.demo_scenario or args.record_eeg or args.replay_eeg:
        scenario = load_demo_scenario(args.demo_scenario) if args.demo_scenario else None
        active_scenario = scenario or DEFAULT_SCENARIO
        windows = load_recording(args.replay_eeg) if args.replay_eeg else acquire_demo_eeg(active_scenario)
        if args.record_eeg:
            save_recording(args.record_eeg, windows)
        planner = None
        if args.planner_base_url or args.planner_model:
            if not args.planner_base_url or not args.planner_model:
                parser.error("--planner-base-url and --planner-model must be provided together")
            planner = OpenAICompatiblePlanner(
                args.planner_base_url,
                args.planner_model,
                destination=active_scenario["destination"]["name"],
                api_key=os.getenv(args.planner_api_key_env),
            )
        report = run_demo(active_scenario, windows, planner)
    elif args.monte_carlo_config:
        report = run_monte_carlo(args.monte_carlo_config)
    elif args.intent_directory:
        report = run_intent_suite(args.intent_directory)
    else:
        report = run_suite(args.directory)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.demo_html:
        args.demo_html.write_text(render_demo_html(report), encoding="utf-8")
    return int(report.get("failed", 0) > 0)


if __name__ == "__main__":
    raise SystemExit(main())
