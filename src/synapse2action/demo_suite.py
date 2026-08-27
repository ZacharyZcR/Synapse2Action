from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .demo import load_demo_scenario, run_demo
from .visualization import render_demo_html


def run_demo_suite(directory: Path, artifact_directory: Path | None = None) -> dict[str, Any]:
    results = []
    if artifact_directory:
        artifact_directory.mkdir(parents=True, exist_ok=True)

    for path in sorted(directory.glob("*.json")):
        report = run_demo(load_demo_scenario(path))
        results.append(
            {
                "scenario": path.name,
                "demo": report["demo"],
                "completed": report["completed"],
                "passed": report["passed"],
                "expected_final_state": report["expected_final_state"],
                "final_state": report["final_state"],
                "planned_actions": report["planned_actions"],
                "robot_actions": report["robot_actions"],
                "trajectory_frames": len(report["tabletop_frames"]),
            }
        )
        if artifact_directory:
            stem = path.stem
            (artifact_directory / f"{stem}.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            (artifact_directory / f"{stem}.html").write_text(
                render_demo_html(report), encoding="utf-8"
            )

    completed = sum(result["completed"] for result in results)
    passed = sum(result["passed"] for result in results)
    return {
        "schema_version": 1,
        "scenario_count": len(results),
        "completed": completed,
        "passed": passed,
        "failed": len(results) - passed,
        "completion_rate": completed / len(results) if results else 0.0,
        "pass_rate": passed / len(results) if results else 0.0,
        "planned_actions": sum(result["planned_actions"] for result in results),
        "robot_actions": sum(result["robot_actions"] for result in results),
        "results": results,
    }
