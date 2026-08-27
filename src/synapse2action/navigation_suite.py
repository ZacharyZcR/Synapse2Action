from __future__ import annotations

from pathlib import Path

from .navigation import load_navigation_scenario
from .vla import DeterministicVLABackend, run_vla_navigation_demo
from .vla_episode import RecordingVLABackend, save_episode


def run_navigation_suite(
    scenario_directory: Path,
    episode_directory: Path | None = None,
) -> dict[str, object]:
    scenario_paths = sorted(scenario_directory.glob("*.json"))
    if not scenario_paths:
        raise ValueError("navigation suite contains no scenarios")
    if episode_directory:
        episode_directory.mkdir(parents=True, exist_ok=True)

    results = []
    total_cycles = 0
    for path in scenario_paths:
        scenario = load_navigation_scenario(path)
        backend = DeterministicVLABackend()
        recorder = RecordingVLABackend(backend) if episode_directory else None
        report = run_vla_navigation_demo(recorder or backend, scenario)
        episode_path = None
        if recorder and episode_directory:
            episode_path = episode_directory / f"{scenario.name}.episode.json"
            save_episode(episode_path, recorder.episode())
        total_cycles += report["control_cycles"]
        results.append(
            {
                "scenario": scenario.name,
                "source": path.name,
                "passed": report["passed"],
                "final_state": report["final_state"],
                "control_cycles": report["control_cycles"],
                "replan_count": report["replan_count"],
                "episode": str(episode_path) if episode_path else None,
            }
        )

    passed = sum(result["passed"] for result in results)
    return {
        "schema_version": 1,
        "suite": "navigation_scenario_distribution",
        "scenario_count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": passed / len(results),
        "total_control_cycles": total_cycles,
        "recorded_episodes": sum(result["episode"] is not None for result in results),
        "results": results,
    }
