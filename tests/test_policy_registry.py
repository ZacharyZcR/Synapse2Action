from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from synapse2action.policy_registry import (
    PolicyLifecycle,
    PolicyRegistry,
    load_policy_manifest,
)
from synapse2action.task_spec import load_task_spec


ROOT = Path(__file__).resolve().parents[1]


class PolicyRegistryTests(unittest.TestCase):
    def test_published_manifests_are_candidates_not_admitted_claims(self) -> None:
        registry = PolicyRegistry.load(ROOT / "policies")
        task = load_task_spec(ROOT / "experiments/tasks/g1_groot_apple_to_plate.json")

        with self.assertRaisesRegex(ValueError, "no admitted policy"):
            registry.select(task, embodiment="unitree-g1", requested_policy="groot")
        selected = registry.select(
            task,
            embodiment="unitree-g1",
            requested_policy="groot",
            allow_candidate=True,
        )
        self.assertEqual(selected.policy_id, "groot")
        self.assertEqual(selected.qualification, "candidate")

    def test_matcher_rejects_wrong_task_and_ambiguous_auto_selection(self) -> None:
        registry = PolicyRegistry.load(ROOT / "policies")
        groot_task = load_task_spec(ROOT / "experiments/tasks/g1_groot_apple_to_plate.json")
        generic_task = load_task_spec(ROOT / "experiments/tasks/g1_pick_place.json")

        with self.assertRaisesRegex(ValueError, "no admitted policy"):
            registry.select(
                groot_task,
                embodiment="unitree-g1",
                requested_policy="smolvla",
                allow_candidate=True,
            )
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            registry.select(
                generic_task,
                embodiment="unitree-g1",
                allow_candidate=True,
            )

    def test_admitted_manifest_requires_immutable_evidence(self) -> None:
        source = json.loads(
            (ROOT / "policies/groot-n16-g1-apple-plate.json").read_text()
        )
        source["admission"]["status"] = "admitted"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError, "lacks immutable evidence"):
                load_policy_manifest(path)

    def test_registry_rejects_missing_claimed_evidence_bundle(self) -> None:
        source = json.loads(
            (ROOT / "policies/groot-n16-g1-apple-plate.json").read_text()
        )
        source["admission"] = {
            "status": "admitted",
            "evidence_bundle": "evidence/missing",
            "evidence_sha256": "a" * 64,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root / "policies"
            registry.mkdir()
            (registry / "manifest.json").write_text(json.dumps(source))
            with self.assertRaises((OSError, ValueError)):
                PolicyRegistry.load(registry)

    def test_unique_admitted_policy_is_selected_automatically(self) -> None:
        candidate = load_policy_manifest(
            ROOT / "policies/groot-n16-g1-apple-plate.json"
        )
        admitted = replace(
            candidate,
            qualification="admitted",
            evidence_bundle="evidence/groot-v1",
            evidence_sha256="a" * 64,
        )
        task = load_task_spec(ROOT / "experiments/tasks/g1_groot_apple_to_plate.json")
        selected = PolicyRegistry((admitted,)).select(
            task,
            embodiment="unitree-g1",
        )
        self.assertEqual(selected.policy_id, "groot")


class PolicyLifecycleTests(unittest.TestCase):
    def test_switch_stops_old_policy_and_resets_state(self) -> None:
        events: list[str] = []
        lifecycle = PolicyLifecycle(
            safe_stop=lambda: events.append("stop"),
            clear_action_buffer=lambda: events.append("clear"),
            reset_observation_history=lambda: events.append("reset"),
        )
        lifecycle.activate("first")
        self.assertEqual(events, ["clear", "reset"])
        events.clear()
        lifecycle.activate("second")
        self.assertEqual(events, ["stop", "clear", "reset"])

    def test_switch_during_execution_is_rejected(self) -> None:
        lifecycle = PolicyLifecycle(
            safe_stop=lambda: None,
            clear_action_buffer=lambda: None,
            reset_observation_history=lambda: None,
        )
        lifecycle.activate("first")
        lifecycle.begin()
        with self.assertRaisesRegex(RuntimeError, "during execution"):
            lifecycle.activate("second")
        lifecycle.finish()
        lifecycle.activate("second")
        self.assertEqual(lifecycle.active_policy, "second")


if __name__ == "__main__":
    unittest.main()
