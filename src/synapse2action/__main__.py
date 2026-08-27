from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .demo import DEFAULT_SCENARIO, acquire_demo_eeg, load_demo_scenario, run_demo
from .demo_suite import run_demo_suite
from .experiments import run_suite
from .eeg import load_recording, save_recording
from .embedded_planner import EmbeddedPlannerServer
from .monte_carlo import run_monte_carlo
from .llm_planner import OpenAICompatiblePlanner
from .navigation import run_navigation_demo
from .synthetic_intent import run_intent_suite
from .visualization import render_demo_html
from .vla import DeterministicVLABackend, VLAInferenceBackend, run_vla_navigation_demo
from .vla_episode import RecordingVLABackend, ReplayVLABackend, load_episode, save_episode
from .vla_http import EmbeddedVLAServer, HTTPVLABackend


def _run_vla(backend: VLAInferenceBackend, record_path: Path | None = None) -> dict[str, object]:
    if record_path is None:
        return run_vla_navigation_demo(backend)
    recorder = RecordingVLABackend(backend)
    report = run_vla_navigation_demo(recorder)
    episode = recorder.episode()
    save_episode(record_path, episode)
    report["recorded_episode"] = str(record_path)
    report["recorded_steps"] = len(episode.steps)
    report["recorded_backend"] = episode.backend
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic hardware-free experiments")
    parser.add_argument("directory", nargs="?", type=Path, default=Path("experiments/scenarios"))
    parser.add_argument("--intent-directory", type=Path)
    parser.add_argument("--monte-carlo-config", type=Path)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--navigation-demo", action="store_true")
    parser.add_argument("--vla-navigation-demo", action="store_true")
    parser.add_argument("--vla-base-url")
    parser.add_argument("--vla-api-key-env", default="VLA_API_KEY")
    parser.add_argument("--embedded-vla", action="store_true")
    parser.add_argument("--record-vla-episode", type=Path)
    parser.add_argument("--replay-vla-episode", type=Path)
    parser.add_argument("--demo-html", type=Path)
    parser.add_argument("--demo-scenario", type=Path)
    parser.add_argument("--demo-suite", type=Path)
    parser.add_argument("--artifact-directory", type=Path)
    parser.add_argument("--record-eeg", type=Path)
    parser.add_argument("--replay-eeg", type=Path)
    parser.add_argument("--planner-base-url")
    parser.add_argument("--planner-model")
    parser.add_argument("--planner-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--embedded-planner", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.embedded_vla and args.vla_base_url:
        parser.error("--embedded-vla cannot be combined with --vla-base-url")
    if args.record_vla_episode and args.replay_vla_episode:
        parser.error("--record-vla-episode cannot be combined with --replay-vla-episode")
    if args.replay_vla_episode and (args.embedded_vla or args.vla_base_url):
        parser.error("replay cannot be combined with a live VLA backend")
    if (args.embedded_vla or args.vla_base_url or args.record_vla_episode or args.replay_vla_episode) and not args.vla_navigation_demo:
        parser.error("VLA backend options require --vla-navigation-demo")

    if args.vla_navigation_demo:
        if args.embedded_vla:
            with EmbeddedVLAServer() as server:
                report = _run_vla(HTTPVLABackend(server.base_url), args.record_vla_episode)
                report["vla_http_requests"] = len(server.requests)
                report["vla_http_operations"] = [request.operation for request in server.requests]
        elif args.replay_vla_episode:
            replay = ReplayVLABackend(load_episode(args.replay_vla_episode))
            report = _run_vla(replay)
            replay.assert_complete()
            report["replayed_episode"] = str(args.replay_vla_episode)
            report["replayed_steps"] = replay.index
        elif args.vla_base_url:
            report = _run_vla(
                HTTPVLABackend(args.vla_base_url, api_key=os.getenv(args.vla_api_key_env)),
                args.record_vla_episode,
            )
        else:
            report = _run_vla(DeterministicVLABackend(), args.record_vla_episode)
    elif args.navigation_demo:
        report = run_navigation_demo()
    elif args.demo_suite:
        report = run_demo_suite(args.demo_suite, args.artifact_directory)
    elif args.demo or args.demo_html or args.demo_scenario or args.record_eeg or args.replay_eeg or args.embedded_planner:
        scenario = load_demo_scenario(args.demo_scenario) if args.demo_scenario else None
        active_scenario = scenario or DEFAULT_SCENARIO
        windows = load_recording(args.replay_eeg) if args.replay_eeg else acquire_demo_eeg(active_scenario)
        if args.record_eeg:
            save_recording(args.record_eeg, windows)
        planner = None
        if args.embedded_planner and (args.planner_base_url or args.planner_model):
            parser.error("--embedded-planner cannot be combined with external planner options")
        if args.planner_base_url or args.planner_model:
            if not args.planner_base_url or not args.planner_model:
                parser.error("--planner-base-url and --planner-model must be provided together")
            planner = OpenAICompatiblePlanner(
                args.planner_base_url,
                args.planner_model,
                destination=active_scenario["destination"]["name"],
                api_key=os.getenv(args.planner_api_key_env),
            )
        if args.embedded_planner:
            with EmbeddedPlannerServer(
                active_scenario["object"]["object_id"], active_scenario["destination"]["name"]
            ) as server:
                planner = OpenAICompatiblePlanner(server.base_url, "embedded-planner")
                report = run_demo(active_scenario, windows, planner)
                report["planner_http_requests"] = len(server.requests)
        else:
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
