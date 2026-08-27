from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path
from typing import Any

from .authorization import ChallengeStore
from .components import MockPlanner, ScriptedPolicy
from .contracts import Intent, IntentKind
from .eeg import EEGWindow, FrequencyDecoder, SyntheticSSVEPSource
from .harness import Harness
from .tabletop import Point2D, TabletopObject, TabletopRobot, TabletopVerifier
from .world import FakeWorld, WorldObject


DEFAULT_SCENARIO: dict[str, Any] = {
    "name": "synthetic_eeg_pick_and_place",
    "expected_final_state": "completed",
    "decoder_threshold": 0.55,
    "eeg_seed": 42,
    "object": {
        "object_id": "red_cube",
        "revision": 1,
        "observed_at_ms": 0,
        "position": [0.4, 0.1, 0.2],
        "color": "#dc2626",
    },
    "destination": {"name": "drop_zone", "position": [0.8, 0.6]},
    "neural_windows": [
        {"at_ms": 0, "label": "select", "signal_amplitude": 1.0, "noise_std": 0.15},
        {"at_ms": 800, "label": "confirm", "signal_amplitude": 1.0, "noise_std": 0.15},
    ],
}


class FakePerception:
    def __init__(self, item: WorldObject) -> None:
        self.item = item

    def observe(self) -> WorldObject:
        return self.item


def load_demo_scenario(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def acquire_demo_eeg(scenario: dict[str, Any]) -> list[EEGWindow]:
    return SyntheticSSVEPSource(seed=scenario.get("eeg_seed", 0)).acquire(scenario["neural_windows"])


def run_demo(
    scenario: dict[str, Any] | None = None,
    eeg_windows: list[EEGWindow] | None = None,
) -> dict[str, Any]:
    scenario = scenario or DEFAULT_SCENARIO
    item = scenario["object"]
    target = FakePerception(
        WorldObject(
            item["object_id"], item["revision"], item["observed_at_ms"], tuple(item["position"])
        )
    ).observe()
    world = FakeWorld([target], max_age_ms=2_000)
    policy = ScriptedPolicy()
    destination_config = scenario["destination"]
    drop_zone = Point2D(*destination_config["position"])
    robot = TabletopRobot(
        TabletopObject(target.object_id, Point2D(target.position[0], target.position[1])),
        {destination_config["name"]: drop_zone},
    )
    harness = Harness(
        MockPlanner(arguments={"target": target.object_id, "destination": destination_config["name"]}),
        robot,
        TabletopVerifier(robot, drop_zone),
        authorizer=ChallengeStore(lifetime_ms=2_000),
        world=world,
        policy=policy,
    )
    windows = eeg_windows if eeg_windows is not None else acquire_demo_eeg(scenario)
    decoder = FrequencyDecoder(scenario.get("decoder_threshold", 0.55))
    decoded: list[Intent] = []
    decoder_results = []

    for window in windows:
        decoded_eeg = decoder.decode(window)
        if decoded_eeg is None:
            continue
        decoder_results.append(decoded_eeg)
        intent = Intent(decoded_eeg.kind, at_ms=window.at_ms)
        if intent.kind is IntentKind.SELECT:
            intent = replace(intent, target=target.object_id, target_revision=target.revision)
        elif intent.kind is IntentKind.CONFIRM:
            intent = replace(
                intent,
                target_revision=target.revision,
                challenge_token=harness.challenge_token,
            )
        decoded.append(intent)
        harness.handle(intent)

    expected_final_state = scenario.get("expected_final_state", "completed")
    return {
        "schema_version": 1,
        "demo": scenario["name"],
        "completed": harness.state.value == "completed",
        "passed": harness.state.value == expected_final_state,
        "expected_final_state": expected_final_state,
        "pipeline": [
            "synthetic_ssvep_source",
            "frequency_decoder",
            "fake_perception",
            "mock_planner",
            "scripted_policy",
            "fake_robot",
            "rule_based_verifier",
        ],
        "world_object": asdict(target),
        "visual": {"object_color": item.get("color", "#dc2626")},
        "neural_windows": [
            {
                "at_ms": window.at_ms,
                "sample_rate_hz": window.sample_rate_hz,
                "sample_count": len(window.samples),
                "expected_intent": window.expected_intent.value,
                "sample_preview": list(window.samples[:8]),
            }
            for window in windows
        ],
        "decoder_results": [
            {
                "kind": result.kind.value,
                "confidence": result.confidence,
                "frequency_hz": result.frequency_hz,
            }
            for result in decoder_results
        ],
        "decoded_intents": [
            {**asdict(intent), "kind": intent.kind.value}
            for intent in decoded
        ],
        "planned_actions": len(policy.prepared),
        "robot_actions": len(robot.executed),
        "tabletop_final": robot.snapshot(),
        "tabletop_frames": [
            {
                "step": frame.step,
                "gripper": asdict(frame.gripper),
                "object_position": asdict(frame.object_position),
                "object_held": frame.object_held,
            }
            for frame in robot.frames
        ],
        "final_state": harness.state.value,
        "trace": [
            {**asdict(record), "state": record.state.value}
            for record in harness.trace
        ],
    }
