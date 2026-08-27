from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .authorization import ChallengeStore
from .components import FakeRobot, MockPlanner, RuleBasedVerifier
from .contracts import ExecutionResult, Intent, IntentKind, TaskState
from .harness import Harness


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    name: str
    passed: bool
    final_state: str
    action_count: int
    stopped: bool
    error: str | None
    trace: list[dict[str, Any]]


def run_scenario(path: Path) -> ExperimentResult:
    scenario = json.loads(path.read_text(encoding="utf-8"))
    robot_config = scenario.get("robot", {})
    robot = FakeRobot(
        result=ExecutionResult(
            robot_config.get("success", True),
            robot_config.get("detail", "simulated action completed"),
        )
    )
    authorization = scenario.get("authorization")
    authorizer = ChallengeStore(authorization.get("lifetime_ms", 3_000)) if authorization else None
    harness = Harness(
        MockPlanner(scenario.get("planner_skill", "pick_and_place")),
        robot,
        RuleBasedVerifier(),
        authorizer=authorizer,
    )
    error = None

    try:
        for item in scenario["intents"]:
            harness.handle(
                Intent(
                    IntentKind(item["kind"]),
                    item.get("target"),
                    item.get("target_revision"),
                    item.get("challenge_token"),
                    item.get("at_ms"),
                )
            )
    except (ValueError, KeyError) as exc:
        error = type(exc).__name__

    expected = scenario["expect"]
    passed = (
        harness.state.value == expected["final_state"]
        and len(robot.executed) == expected.get("action_count", 0)
        and robot.stopped is expected.get("stopped", False)
        and error == expected.get("error")
    )
    trace = [
        {**asdict(record), "state": record.state.value}
        for record in harness.trace
    ]
    return ExperimentResult(
        scenario["name"], passed, harness.state.value, len(robot.executed), robot.stopped, error, trace
    )


def run_suite(directory: Path) -> dict[str, Any]:
    results = [run_scenario(path) for path in sorted(directory.glob("*.json"))]
    return {
        "schema_version": 1,
        "passed": sum(result.passed for result in results),
        "failed": sum(not result.passed for result in results),
        "results": [asdict(result) for result in results],
    }
