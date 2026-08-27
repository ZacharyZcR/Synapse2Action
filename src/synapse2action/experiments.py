from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .authorization import ChallengeStore
from .components import FakeRobot, MockPlanner, RuleBasedVerifier
from .contracts import ExecutionResult, Intent, IntentKind, TaskState
from .harness import Harness
from .world import FakeWorld, WorldObject


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
            robot_config.get("duration_ms", 0),
        )
    )
    authorization = scenario.get("authorization")
    authorizer = ChallengeStore(authorization.get("lifetime_ms", 3_000)) if authorization else None
    world_config = scenario.get("world")
    world = None
    if world_config:
        objects = [
            WorldObject(
                item["object_id"],
                item["revision"],
                item["observed_at_ms"],
                tuple(item["position"]),
                item.get("occupied", False),
                item.get("reachable", True),
            )
            for item in world_config["objects"]
        ]
        world = FakeWorld(objects, world_config.get("max_age_ms", 1_000))
    harness = Harness(
        MockPlanner(scenario.get("planner_skill", "pick_and_place"), scenario.get("planner_arguments")),
        robot,
        RuleBasedVerifier(),
        authorizer=authorizer,
        world=world,
    )
    error = None

    try:
        for item in scenario["intents"]:
            if "world_update" in item:
                update = item["world_update"]
                if update["op"] == "move":
                    assert world is not None
                    world.move(update["target"], tuple(update["position"]), update["at_ms"])
                elif update["op"] == "occupy":
                    assert world is not None
                    world.set_occupied(update["target"], True, update["at_ms"])
                elif update["op"] == "remove":
                    assert world is not None
                    world.remove(update["target"])
                else:
                    raise ValueError(f"unknown world operation: {update['op']}")
                continue
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
