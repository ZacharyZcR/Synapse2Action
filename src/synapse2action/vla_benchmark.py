from __future__ import annotations

import json
from math import hypot
from pathlib import Path

from .navigation import load_navigation_scenario
from .vla import run_vla_navigation_demo
from .vla_baseline import KNNVLABackend, evaluate_knn_baseline, load_knn_checkpoint


def benchmark_knn_baseline(
    dataset_directory: Path,
    checkpoint_path: Path,
    scenario_directory: Path,
) -> dict[str, object]:
    checkpoint = load_knn_checkpoint(checkpoint_path)
    offline = evaluate_knn_baseline(dataset_directory, checkpoint)
    manifest = json.loads((dataset_directory / "manifest.json").read_text(encoding="utf-8"))
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
    for episode_id in offline["validation_episode_ids"]:
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
        report = run_vla_navigation_demo(KNNVLABackend(checkpoint), scenario)
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
        "benchmark": "knn_vla_held_out_navigation",
        "checkpoint": str(checkpoint_path),
        "training_episodes": len(offline["training_episode_ids"]),
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
