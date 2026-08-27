from __future__ import annotations

import json
from math import hypot
from pathlib import Path
from typing import Callable

from .navigation import load_navigation_scenario
from .vla import VLAInferenceBackend, run_vla_navigation_demo
from .vla_baseline import KNNVLABackend, evaluate_knn_baseline, load_knn_checkpoint
from .vla_ridge import RidgeVLABackend, evaluate_ridge_baseline, load_ridge_checkpoint


def benchmark_vla_baseline(
    dataset_directory: Path,
    checkpoint_path: Path,
    scenario_directory: Path,
) -> dict[str, object]:
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint_format = payload.get("format") if isinstance(payload, dict) else None
    if checkpoint_format == "synapse2action.knn_vla":
        return benchmark_knn_baseline(dataset_directory, checkpoint_path, scenario_directory)
    if checkpoint_format == "synapse2action.ridge_vla":
        return benchmark_ridge_baseline(dataset_directory, checkpoint_path, scenario_directory)
    raise ValueError("unsupported VLA baseline checkpoint")


def benchmark_knn_baseline(
    dataset_directory: Path,
    checkpoint_path: Path,
    scenario_directory: Path,
) -> dict[str, object]:
    checkpoint = load_knn_checkpoint(checkpoint_path)
    offline = evaluate_knn_baseline(dataset_directory, checkpoint)
    manifest = _manifest(dataset_directory)
    return _closed_loop_benchmark(
        "knn_vla_held_out_navigation",
        checkpoint_path,
        scenario_directory,
        manifest,
        offline["validation_episode_ids"],
        len(offline["training_episode_ids"]),
        offline,
        lambda: KNNVLABackend(checkpoint),
    )


def benchmark_ridge_baseline(
    dataset_directory: Path,
    checkpoint_path: Path,
    scenario_directory: Path,
) -> dict[str, object]:
    checkpoint = load_ridge_checkpoint(checkpoint_path)
    offline = evaluate_ridge_baseline(dataset_directory, checkpoint)
    manifest = _manifest(dataset_directory)
    validation_ids = manifest["splits"]["validation"]["episodes"]
    return _closed_loop_benchmark(
        "ridge_vla_held_out_navigation",
        checkpoint_path,
        scenario_directory,
        manifest,
        validation_ids,
        len(checkpoint.training_episode_ids),
        offline,
        lambda: RidgeVLABackend(checkpoint),
    )


def _manifest(dataset_directory: Path) -> dict[str, object]:
    manifest = json.loads((dataset_directory / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("format") != "synapse2action.vla_dataset":
        raise ValueError("invalid benchmark dataset manifest")
    return manifest


def _closed_loop_benchmark(
    benchmark_name: str,
    checkpoint_path: Path,
    scenario_directory: Path,
    manifest: dict[str, object],
    validation_episode_ids: list[str],
    training_episode_count: int,
    offline: dict[str, object],
    backend_factory: Callable[[], VLAInferenceBackend],
) -> dict[str, object]:
    episode_metadata = {episode["episode_id"]: episode for episode in manifest["episodes"]}
    scenarios = {
        scenario.name: scenario
        for scenario in (
            load_navigation_scenario(path)
            for path in sorted(scenario_directory.glob("*.json"))
        )
    }
    if not scenarios:
        raise ValueError("VLA benchmark contains no navigation scenarios")

    results = []
    for episode_id in validation_episode_ids:
        metadata = episode_metadata.get(episode_id)
        if not metadata or not isinstance(metadata.get("source"), str):
            raise ValueError("validation episode is missing source metadata")
        suffix = ".episode.json"
        source = metadata["source"]
        if not source.endswith(suffix):
            raise ValueError("validation episode source is not a suite episode")
        scenario_name = source[: -len(suffix)]
        scenario = scenarios.get(scenario_name)
        if scenario is None:
            raise ValueError(f"validation scenario not found: {scenario_name}")
        report = run_vla_navigation_demo(backend_factory(), scenario)
        final_pose = report["final_pose"]
        goal = report["goal"]
        verify_detail = next(
            (record["detail"] for record in report["trace"] if record["event"] == "verify"),
            "",
        )
        results.append(
            {
                "episode_id": episode_id,
                "scenario": scenario_name,
                "passed": report["passed"],
                "final_state": report["final_state"],
                "control_cycles": report["control_cycles"],
                "goal_error_m": hypot(final_pose["x"] - goal["x"], final_pose["y"] - goal["y"]),
                "execution_detail": verify_detail,
            }
        )

    passed = sum(result["passed"] for result in results)
    return {
        "schema_version": 1,
        "benchmark": benchmark_name,
        "checkpoint": str(checkpoint_path),
        "training_episodes": training_episode_count,
        "validation_episodes": len(results),
        "validation_samples": offline["validation_samples"],
        "validation_velocity_mae": offline["validation_velocity_mae"],
        "validation_duration_accuracy": offline["validation_duration_accuracy"],
        "closed_loop_passed": passed,
        "closed_loop_failed": len(results) - passed,
        "closed_loop_success_rate": passed / len(results) if results else None,
        "failed": len(results) - passed,
        "results": results,
    }
