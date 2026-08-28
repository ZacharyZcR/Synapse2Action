from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .demo import DEFAULT_SCENARIO, acquire_demo_eeg, load_demo_scenario, run_demo
from .demo_suite import run_demo_suite
from .components import FakeRobot, MockPlanner, RuleBasedVerifier
from .experiments import run_suite
from .eeg import load_recording, save_recording
from .embedded_planner import EmbeddedPlannerServer
from .eeg_planner_benchmark import run_eeg_planner_benchmark
from .live_planner_benchmark import run_live_planner_benchmark
from .monte_carlo import run_monte_carlo
from .planner_benchmark import run_planner_benchmark
from .planner_provider_summary import summarize_planner_providers
from .llm_planner import OpenAICompatiblePlanner
from .llm_vla_benchmark import run_llm_vla_benchmark
from .harness import Harness
from .intent_sources import KeyboardIntentSource, run_intent_source
from .navigation import (
    DEFAULT_NAVIGATION_SCENARIO,
    NavigationScenario,
    load_navigation_scenario,
    run_navigation_demo,
)
from .robot_http import EmbeddedRobotServer, HTTPRobotTransport
from .schemas import contract_catalog
from .robot_transport import LoopbackRobotTransport, RobotTransport
from .ros2_bridge import LoopbackROS2Runtime, ROS2RobotTransport
from .navigation_suite import run_navigation_suite
from .synthetic_intent import run_intent_suite
from .visualization import render_demo_html
from .vla import DeterministicVLABackend, VLAInferenceBackend, run_vla_navigation_demo
from .vla_episode import RecordingVLABackend, ReplayVLABackend, load_episode, save_episode
from .vla_dataset import export_dataset
from .vla_baseline import KNNVLABackend, load_knn_checkpoint, train_knn_baseline
from .vla_benchmark import benchmark_vla_baseline
from .vla_crossval import run_leave_one_scenario_out
from .vla_ridge import (
    RidgeVLABackend,
    load_ridge_checkpoint,
    train_chunked_temporal_ridge_baseline,
    train_ridge_baseline,
    train_temporal_ridge_baseline,
)
from .vla_http import EmbeddedVLAServer, HTTPVLABackend


def _run_vla(
    backend: VLAInferenceBackend,
    record_path: Path | None = None,
    scenario: NavigationScenario | None = None,
    execution_horizon: int | None = None,
    temporal_ensemble_decay: float | None = None,
    transport: RobotTransport | None = None,
) -> dict[str, object]:
    if record_path is None:
        return run_vla_navigation_demo(
            backend,
            scenario,
            execution_horizon,
            temporal_ensemble_decay,
            transport,
        )
    recorder = RecordingVLABackend(backend)
    report = run_vla_navigation_demo(
        recorder,
        scenario,
        execution_horizon,
        temporal_ensemble_decay,
        transport,
    )
    episode = recorder.episode()
    save_episode(record_path, episode)
    report["recorded_episode"] = str(record_path)
    report["recorded_steps"] = len(episode.steps)
    report["recorded_backend"] = episode.backend
    return report


def _checkpoint_backend(path: Path) -> VLAInferenceBackend:
    payload = json.loads(path.read_text(encoding="utf-8"))
    checkpoint_format = payload.get("format") if isinstance(payload, dict) else None
    if checkpoint_format == "synapse2action.knn_vla":
        return KNNVLABackend(load_knn_checkpoint(path))
    if checkpoint_format == "synapse2action.ridge_vla":
        return RidgeVLABackend(load_ridge_checkpoint(path))
    raise ValueError("unsupported VLA baseline checkpoint")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic hardware-free experiments")
    parser.add_argument("directory", nargs="?", type=Path, default=Path("experiments/scenarios"))
    parser.add_argument("--intent-directory", type=Path)
    parser.add_argument("--keyboard-intents", action="store_true")
    parser.add_argument("--contract-catalog", action="store_true")
    parser.add_argument("--monte-carlo-config", type=Path)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--navigation-demo", action="store_true")
    parser.add_argument("--navigation-scenario", type=Path)
    parser.add_argument("--navigation-suite", type=Path)
    parser.add_argument("--navigation-episode-directory", type=Path)
    parser.add_argument(
        "--robot-transport",
        choices=("loopback", "embedded-http", "embedded-ros2-http", "http"),
    )
    parser.add_argument("--robot-base-url")
    parser.add_argument("--robot-api-key-env", default="ROBOT_API_KEY")
    parser.add_argument("--robot-sensor-latency-ms", type=int, default=0)
    parser.add_argument("--robot-command-latency-ms", type=int, default=0)
    parser.add_argument("--vla-navigation-demo", action="store_true")
    parser.add_argument("--vla-base-url")
    parser.add_argument("--vla-api-key-env", default="VLA_API_KEY")
    parser.add_argument("--embedded-vla", action="store_true")
    parser.add_argument("--record-vla-episode", type=Path)
    parser.add_argument("--replay-vla-episode", type=Path)
    parser.add_argument("--export-vla-dataset", type=Path, nargs="+")
    parser.add_argument("--vla-dataset-output", type=Path)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--train-vla-baseline", type=Path)
    parser.add_argument(
        "--vla-baseline-algorithm",
        choices=("knn", "ridge", "temporal-ridge", "chunked-ridge"),
        default="knn",
    )
    parser.add_argument("--vla-checkpoint", type=Path)
    parser.add_argument("--benchmark-vla-baseline", type=Path)
    parser.add_argument("--benchmark-navigation-scenarios", type=Path)
    parser.add_argument("--cross-validate-vla-baseline", type=Path, nargs="+")
    parser.add_argument("--cross-validation-output", type=Path)
    parser.add_argument("--vla-execution-horizon", type=int)
    parser.add_argument("--vla-temporal-ensemble-decay", type=float)
    parser.add_argument("--demo-html", type=Path)
    parser.add_argument("--demo-scenario", type=Path)
    parser.add_argument("--demo-suite", type=Path)
    parser.add_argument("--artifact-directory", type=Path)
    parser.add_argument("--record-eeg", type=Path)
    parser.add_argument("--replay-eeg", type=Path)
    parser.add_argument("--planner-base-url")
    parser.add_argument("--planner-model")
    parser.add_argument("--planner-provider-name")
    parser.add_argument(
        "--planner-output-mode",
        choices=("json-schema", "prompt-json"),
        default="json-schema",
    )
    parser.add_argument("--planner-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--planner-benchmark", type=Path)
    parser.add_argument("--eeg-planner-benchmark", type=Path)
    parser.add_argument("--llm-vla-benchmark", type=Path)
    parser.add_argument("--llm-vla-counterfactual", type=Path)
    parser.add_argument("--planner-live-benchmark", type=Path)
    parser.add_argument("--planner-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--summarize-planner-providers", type=Path, nargs="+")
    parser.add_argument("--required-planner-model", action="append", default=[])
    parser.add_argument("--embedded-planner", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.planner_timeout_seconds <= 0:
        parser.error("--planner-timeout-seconds must be positive")
    if args.planner_live_benchmark and (
        not args.planner_base_url
        or not args.planner_model
        or not args.planner_provider_name
    ):
        parser.error(
            "--planner-live-benchmark requires --planner-base-url, "
            "--planner-model, and --planner-provider-name"
        )
    if args.required_planner_model and not args.summarize_planner_providers:
        parser.error("--required-planner-model requires --summarize-planner-providers")
    if args.navigation_scenario and not (args.navigation_demo or args.vla_navigation_demo):
        parser.error("--navigation-scenario requires a navigation demo")
    if args.navigation_episode_directory and not args.navigation_suite:
        parser.error("--navigation-episode-directory requires --navigation-suite")
    if args.robot_transport and not (args.navigation_demo or args.vla_navigation_demo):
        parser.error("--robot-transport requires a navigation demo")
    if args.robot_transport == "http" and not args.robot_base_url:
        parser.error("HTTP robot transport requires --robot-base-url")
    if args.robot_base_url and args.robot_transport != "http":
        parser.error("--robot-base-url requires --robot-transport http")
    if args.robot_sensor_latency_ms < 0 or args.robot_command_latency_ms < 0:
        parser.error("robot transport latency must be non-negative")
    if (args.robot_sensor_latency_ms or args.robot_command_latency_ms) and not args.robot_transport:
        parser.error("robot transport latency requires --robot-transport")
    if (args.robot_sensor_latency_ms or args.robot_command_latency_ms) and args.robot_transport == "http":
        parser.error("latency simulation requires loopback or embedded HTTP robot transport")
    if bool(args.export_vla_dataset) != bool(args.vla_dataset_output):
        parser.error("--export-vla-dataset and --vla-dataset-output must be provided together")
    if args.train_vla_baseline and not args.vla_checkpoint:
        parser.error("--train-vla-baseline requires --vla-checkpoint")
    if args.benchmark_vla_baseline and not args.benchmark_navigation_scenarios:
        parser.error("benchmark dataset requires navigation scenarios")
    if args.benchmark_navigation_scenarios and not (
        args.benchmark_vla_baseline or args.cross_validate_vla_baseline
    ):
        parser.error("navigation benchmark scenarios require benchmark or cross-validation episodes")
    if args.benchmark_vla_baseline and not args.vla_checkpoint:
        parser.error("--benchmark-vla-baseline requires --vla-checkpoint")
    if bool(args.cross_validate_vla_baseline) != bool(args.cross_validation_output):
        parser.error("cross-validation episodes and output directory must be provided together")
    if args.cross_validate_vla_baseline and not args.benchmark_navigation_scenarios:
        parser.error("VLA cross-validation requires --benchmark-navigation-scenarios")
    if args.cross_validate_vla_baseline and (
        args.benchmark_vla_baseline or args.train_vla_baseline or args.export_vla_dataset
    ):
        parser.error("VLA cross-validation cannot be combined with export, training, or benchmark")
    if args.vla_execution_horizon is not None and args.vla_execution_horizon <= 0:
        parser.error("--vla-execution-horizon must be positive")
    if args.vla_execution_horizon is not None and not (
        args.vla_navigation_demo or args.benchmark_vla_baseline or args.cross_validate_vla_baseline
    ):
        parser.error("--vla-execution-horizon requires VLA demo, benchmark, or cross-validation")
    if args.vla_temporal_ensemble_decay is not None and not (
        0 < args.vla_temporal_ensemble_decay <= 1
    ):
        parser.error("--vla-temporal-ensemble-decay must be in (0, 1]")
    if args.vla_temporal_ensemble_decay is not None and args.vla_execution_horizon not in (None, 1):
        parser.error("temporal ensembling requires execution horizon one")
    if args.vla_temporal_ensemble_decay is not None and not (
        args.vla_navigation_demo or args.benchmark_vla_baseline or args.cross_validate_vla_baseline
    ):
        parser.error("temporal ensembling requires VLA demo, benchmark, or cross-validation")
    if args.vla_checkpoint and not (
        args.train_vla_baseline or args.vla_navigation_demo or args.benchmark_vla_baseline
    ):
        parser.error("--vla-checkpoint requires training, benchmark, or --vla-navigation-demo")
    if args.train_vla_baseline and args.vla_navigation_demo:
        parser.error("training cannot be combined with --vla-navigation-demo")
    if args.train_vla_baseline and args.export_vla_dataset:
        parser.error("training cannot be combined with dataset export")
    if args.vla_checkpoint and args.vla_navigation_demo and (
        args.embedded_vla or args.vla_base_url or args.replay_vla_episode
    ):
        parser.error("checkpoint navigation cannot be combined with another VLA backend")
    if args.embedded_vla and args.vla_base_url:
        parser.error("--embedded-vla cannot be combined with --vla-base-url")
    if args.record_vla_episode and args.replay_vla_episode:
        parser.error("--record-vla-episode cannot be combined with --replay-vla-episode")
    if args.replay_vla_episode and (args.embedded_vla or args.vla_base_url):
        parser.error("replay cannot be combined with a live VLA backend")
    if (args.embedded_vla or args.vla_base_url or args.record_vla_episode or args.replay_vla_episode) and not args.vla_navigation_demo:
        parser.error("VLA backend options require --vla-navigation-demo")

    navigation_scenario = load_navigation_scenario(args.navigation_scenario) if args.navigation_scenario else None
    active_navigation_scenario = navigation_scenario or DEFAULT_NAVIGATION_SCENARIO
    loopback_robot = (
        LoopbackRobotTransport(
            active_navigation_scenario.start,
            active_navigation_scenario.obstacles,
            robot_radius_m=active_navigation_scenario.robot_radius_m,
            sensor_range_m=active_navigation_scenario.sensor_range_m,
            sensor_latency_ms=args.robot_sensor_latency_ms,
            command_latency_ms=args.robot_command_latency_ms,
        )
        if args.robot_transport in {"loopback", "embedded-http", "embedded-ros2-http"}
        else None
    )
    robot_server = None
    ros2_runtime = None
    robot_transport: RobotTransport | None = loopback_robot
    if args.robot_transport in {"embedded-http", "embedded-ros2-http"}:
        robot_bridge: RobotTransport = loopback_robot
        if args.robot_transport == "embedded-ros2-http":
            ros2_runtime = LoopbackROS2Runtime(loopback_robot)
            robot_bridge = ROS2RobotTransport(ros2_runtime)
        robot_server = EmbeddedRobotServer(robot_bridge)
        robot_server.start()
        robot_transport = HTTPRobotTransport(
            robot_server.base_url,
            sensor_latency_ms=args.robot_sensor_latency_ms,
            command_latency_ms=args.robot_command_latency_ms,
        )
    elif args.robot_transport == "http":
        robot_transport = HTTPRobotTransport(
            args.robot_base_url,
            api_key=os.getenv(args.robot_api_key_env),
        )

    if args.cross_validate_vla_baseline:
        report = run_leave_one_scenario_out(
            args.cross_validate_vla_baseline,
            args.benchmark_navigation_scenarios,
            args.cross_validation_output,
            args.vla_baseline_algorithm,
            args.vla_execution_horizon,
            args.vla_temporal_ensemble_decay,
        )
    elif args.benchmark_vla_baseline:
        report = benchmark_vla_baseline(
            args.benchmark_vla_baseline,
            args.vla_checkpoint,
            args.benchmark_navigation_scenarios,
            args.vla_execution_horizon,
            args.vla_temporal_ensemble_decay,
        )
    elif args.navigation_suite:
        report = run_navigation_suite(args.navigation_suite, args.navigation_episode_directory)
    elif args.train_vla_baseline:
        trainers = {
            "knn": train_knn_baseline,
            "ridge": train_ridge_baseline,
            "temporal-ridge": train_temporal_ridge_baseline,
            "chunked-ridge": train_chunked_temporal_ridge_baseline,
        }
        report = trainers[args.vla_baseline_algorithm](
            args.train_vla_baseline,
            args.vla_checkpoint,
        )
    elif args.export_vla_dataset:
        report = export_dataset(
            args.export_vla_dataset,
            args.vla_dataset_output,
            args.validation_fraction,
        )
    elif args.vla_navigation_demo:
        if args.embedded_vla:
            with EmbeddedVLAServer() as server:
                report = _run_vla(
                    HTTPVLABackend(server.base_url),
                    args.record_vla_episode,
                    navigation_scenario,
                    args.vla_execution_horizon,
                    args.vla_temporal_ensemble_decay,
                    robot_transport,
                )
                report["vla_http_requests"] = len(server.requests)
                report["vla_http_operations"] = [request.operation for request in server.requests]
        elif args.replay_vla_episode:
            replay = ReplayVLABackend(load_episode(args.replay_vla_episode))
            report = _run_vla(
                replay,
                scenario=navigation_scenario,
                execution_horizon=args.vla_execution_horizon,
                temporal_ensemble_decay=args.vla_temporal_ensemble_decay,
                transport=robot_transport,
            )
            replay.assert_complete()
            report["replayed_episode"] = str(args.replay_vla_episode)
            report["replayed_steps"] = replay.index
        elif args.vla_base_url:
            report = _run_vla(
                HTTPVLABackend(args.vla_base_url, api_key=os.getenv(args.vla_api_key_env)),
                args.record_vla_episode,
                navigation_scenario,
                args.vla_execution_horizon,
                args.vla_temporal_ensemble_decay,
                robot_transport,
            )
        else:
            backend = (
                _checkpoint_backend(args.vla_checkpoint)
                if args.vla_checkpoint
                else DeterministicVLABackend()
            )
            report = _run_vla(
                backend,
                args.record_vla_episode,
                navigation_scenario,
                args.vla_execution_horizon,
                args.vla_temporal_ensemble_decay,
                robot_transport,
            )
    elif args.navigation_demo:
        report = run_navigation_demo(scenario=navigation_scenario, transport=robot_transport)
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
                timeout_seconds=args.planner_timeout_seconds,
                output_mode=args.planner_output_mode,
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
    elif args.summarize_planner_providers:
        report = summarize_planner_providers(
            args.summarize_planner_providers,
            args.required_planner_model,
        )
    elif args.planner_live_benchmark:
        report = run_live_planner_benchmark(
            args.planner_live_benchmark,
            OpenAICompatiblePlanner(
                args.planner_base_url,
                args.planner_model,
                api_key=os.getenv(args.planner_api_key_env),
                timeout_seconds=args.planner_timeout_seconds,
                output_mode=args.planner_output_mode,
            ),
            args.planner_provider_name,
        )
    elif args.eeg_planner_benchmark:
        if bool(args.planner_base_url) != bool(args.planner_model):
            parser.error(
                "--eeg-planner-benchmark requires both or neither of "
                "--planner-base-url and --planner-model"
            )
        planner = (
            OpenAICompatiblePlanner(
                args.planner_base_url,
                args.planner_model,
                api_key=os.getenv(args.planner_api_key_env),
                timeout_seconds=args.planner_timeout_seconds,
                output_mode=args.planner_output_mode,
            )
            if args.planner_base_url
            else MockPlanner()
        )
        report = run_eeg_planner_benchmark(
            args.eeg_planner_benchmark,
            planner,
            args.planner_provider_name or "mock",
        )
    elif args.llm_vla_benchmark:
        report = run_llm_vla_benchmark(
            args.llm_vla_benchmark,
            args.llm_vla_counterfactual,
        )
    elif args.contract_catalog:
        report = contract_catalog()
    elif args.planner_benchmark:
        report = run_planner_benchmark(args.planner_benchmark)
    elif args.keyboard_intents:
        report = run_intent_source(
            KeyboardIntentSource(),
            Harness(MockPlanner(), FakeRobot(), RuleBasedVerifier()),
        )
    elif args.monte_carlo_config:
        report = run_monte_carlo(args.monte_carlo_config)
    elif args.intent_directory:
        report = run_intent_suite(args.intent_directory)
    else:
        report = run_suite(args.directory)
    if robot_server is not None:
        report["robot_http_requests"] = len(robot_server.requests)
        report["robot_http_operations"] = [request.operation for request in robot_server.requests]
    if ros2_runtime is not None:
        report["robot_bridge"] = "ros2"
        report["ros2_twist_messages"] = len(ros2_runtime.published_twists)
        report["ros2_zero_twists"] = ros2_runtime.zero_twist_count
        report["ros2_emergency_stops"] = ros2_runtime.emergency_stop_count
    if isinstance(robot_transport, HTTPRobotTransport):
        robot_transport.close()
    if robot_server is not None:
        robot_server.close()
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.demo_html:
        args.demo_html.write_text(render_demo_html(report), encoding="utf-8")
    return int(report.get("failed", 0) > 0 or report.get("accepted") is False)


if __name__ == "__main__":
    raise SystemExit(main())
