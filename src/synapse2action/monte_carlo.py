from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from .components import FakeRobot, MockPlanner, RuleBasedVerifier
from .contracts import Intent, IntentKind
from .harness import Harness
from .safety import IntentGate


def _replay(events: list[tuple[int, Intent]], gate: IntentGate | None) -> tuple[int, int]:
    robot = FakeRobot()
    harness = Harness(MockPlanner(), robot, RuleBasedVerifier())
    rejected = 0
    for at_ms, intent in events:
        if gate:
            decision = gate.admit(intent, at_ms)
            if not decision.accepted:
                rejected += 1
                continue
        try:
            harness.handle(intent)
        except ValueError:
            rejected += 1
    return len(robot.executed), rejected


def run_monte_carlo(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    rng = random.Random(config["seed"])
    kinds = [IntentKind(value) for value in config.get("activation_kinds", ["select", "confirm", "cancel"])]
    baseline_actions = gated_actions = baseline_rejections = gated_rejections = activations = 0

    for _ in range(config["trials"]):
        events = []
        for window in range(config["windows_per_trial"]):
            if rng.random() < config["false_activation_probability"]:
                kind = rng.choice(kinds)
                target = "noise_target" if kind is IntentKind.SELECT else None
                events.append((window * config["window_interval_ms"], Intent(kind, target)))
        activations += len(events)
        actions, rejected = _replay(events, None)
        baseline_actions += actions
        baseline_rejections += rejected
        gate = IntentGate(**config["gate"])
        actions, rejected = _replay(events, gate)
        gated_actions += actions
        gated_rejections += rejected

    total_windows = config["trials"] * config["windows_per_trial"]
    return {
        "schema_version": 1,
        "seed": config["seed"],
        "trials": config["trials"],
        "total_windows": total_windows,
        "false_activations": activations,
        "baseline": {
            "unauthorized_actions": baseline_actions,
            "actions_per_million_windows": baseline_actions * 1_000_000 / total_windows,
            "rejected_events": baseline_rejections,
        },
        "gated": {
            "unauthorized_actions": gated_actions,
            "actions_per_million_windows": gated_actions * 1_000_000 / total_windows,
            "rejected_events": gated_rejections,
        },
    }
