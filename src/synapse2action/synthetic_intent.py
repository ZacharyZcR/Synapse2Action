from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .components import FakeRobot, MockPlanner, RuleBasedVerifier
from .contracts import Intent, IntentKind
from .harness import Harness


@dataclass(frozen=True, slots=True)
class DecodedEvent:
    source_window: int
    delivery_ms: int
    intent: Intent
    confidence: float
    duplicate: bool = False


def _decode(scenario: dict[str, Any]) -> tuple[list[DecodedEvent], dict[str, int]]:
    config = scenario.get("decoder", {})
    rng = random.Random(scenario.get("seed", 0))
    events: list[DecodedEvent] = []
    metrics = {"truth_windows": 0, "correct": 0, "abstentions": 0, "false_activations": 0, "duplicates": 0}
    kinds = list(IntentKind)

    for index, window in enumerate(scenario["windows"]):
        truth_data = window.get("truth")
        confidence = float(window.get("confidence", 1.0))
        if truth_data is None:
            if rng.random() >= config.get("false_activation_probability", 0.0):
                continue
            kind = rng.choice(kinds)
            target = "noise_target" if kind is IntentKind.SELECT else None
            metrics["false_activations"] += 1
        else:
            metrics["truth_windows"] += 1
            if confidence < config.get("confidence_threshold", 0.0) or rng.random() < config.get("abstention_probability", 0.0):
                metrics["abstentions"] += 1
                continue
            truth_kind = IntentKind(truth_data["kind"])
            kind = truth_kind
            if rng.random() < config.get("confusion_probability", 0.0):
                kind = rng.choice([candidate for candidate in kinds if candidate is not truth_kind])
            else:
                metrics["correct"] += 1
            target = truth_data.get("target") if kind is IntentKind.SELECT else None
            if kind is IntentKind.SELECT and target is None:
                target = "confused_target"

        jitter = rng.randint(0, config.get("max_jitter_ms", 0))
        event = DecodedEvent(index, window["at_ms"] + jitter, Intent(kind, target), confidence)
        events.append(event)
        if rng.random() < config.get("duplicate_probability", 0.0):
            events.append(DecodedEvent(index, event.delivery_ms + 1, event.intent, confidence, True))
            metrics["duplicates"] += 1

    return sorted(events, key=lambda event: (event.delivery_ms, event.source_window, event.duplicate)), metrics


def run_intent_scenario(path: Path) -> dict[str, Any]:
    scenario = json.loads(path.read_text(encoding="utf-8"))
    events, metrics = _decode(scenario)
    robot = FakeRobot()
    harness = Harness(MockPlanner(), robot, RuleBasedVerifier())
    transition_errors = 0

    for event in events:
        try:
            harness.handle(event.intent)
        except ValueError:
            transition_errors += 1

    authorized = 0
    selected = False
    for window in scenario["windows"]:
        truth = window.get("truth")
        if not truth:
            continue
        kind = truth["kind"]
        if kind == "select":
            selected = True
        elif kind == "confirm" and selected:
            authorized += 1
            selected = False
        elif kind in {"cancel", "stop"}:
            selected = False

    metrics.update(
        emitted_events=len(events),
        transition_errors=transition_errors,
        actions=len(robot.executed),
        unauthorized_actions=max(0, len(robot.executed) - authorized),
    )
    expected = scenario["expect"]
    passed = (
        harness.state.value == expected["final_state"]
        and metrics["unauthorized_actions"] <= expected.get("max_unauthorized_actions", 0)
        and metrics["abstentions"] >= expected.get("min_abstentions", 0)
        and metrics["false_activations"] >= expected.get("min_false_activations", 0)
        and metrics["duplicates"] >= expected.get("min_duplicates", 0)
    )
    return {
        "name": scenario["name"],
        "passed": passed,
        "final_state": harness.state.value,
        "metrics": metrics,
        "events": [
            {**asdict(event), "intent": {"kind": event.intent.kind.value, "target": event.intent.target}}
            for event in events
        ],
    }


def run_intent_suite(directory: Path) -> dict[str, Any]:
    results = [run_intent_scenario(path) for path in sorted(directory.glob("*.json"))]
    return {
        "schema_version": 1,
        "passed": sum(result["passed"] for result in results),
        "failed": sum(not result["passed"] for result in results),
        "results": results,
    }
