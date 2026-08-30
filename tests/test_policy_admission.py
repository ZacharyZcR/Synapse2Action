from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from synapse2action.language_qualification import build_language_qualification
from synapse2action.policy_admission import qualification_digest, verify_policy_admission
from synapse2action.task_spec import load_task_spec


ROOT = Path(__file__).resolve().parents[1]


def language_bundle() -> tuple[dict[str, object], dict[str, object]]:
    tasks = [load_task_spec(path) for path in sorted((ROOT / "experiments/tasks").glob("*.json"))]
    manifest = build_language_qualification(tasks)
    cases = []
    for requirement in manifest["cases"]:
        evidence = {
            "case_id": requirement["case_id"],
            "seed": 41,
            "observation_id": f"observation:{requirement['task_id']}",
            "passed": True,
        }
        decision = requirement["expected_decision"]
        if decision == "execute":
            evidence.update(
                observed_decision="execute",
                skill=requirement["expected_skill"],
                arguments=requirement["expected_arguments"],
            )
        elif decision == "change_behavior":
            evidence["action_changed"] = True
        else:
            evidence.update(observed_decision="refuse", action_chunks=0)
        cases.append(evidence)
    evaluation = {
        "schema_version": 1,
        "benchmark": "language_to_work_policy_evaluation",
        "policy_id": "fixture-policy",
        "qualification_sha256": qualification_digest(manifest),
        "cases": cases,
    }
    return manifest, evaluation


def run(seed: int) -> dict[str, object]:
    return {
        "policy": "fixture-policy",
        "seed": seed,
        "accepted": True,
        "final_state": "completed",
        "result": {
            "schema_version": 3,
            "success": True,
            "outcome_success": True,
            "process_compliance": True,
            "safety_passed": True,
            "detail": "verified",
            "duration_ms": 100,
        },
        "recovery_attempts": 0,
        "recovery_history": [],
        "trace": [
            {"sequence": 1, "event": "confirm", "state": "armed"},
            {"sequence": 2, "event": "execute", "state": "executing"},
            {"sequence": 3, "event": "result", "state": "completed"},
        ],
    }


def write_bundle(
    directory: str,
    runs: list[dict[str, object]],
    manifest: dict[str, object],
    evaluation: dict[str, object],
) -> tuple[list[Path], Path, Path]:
    root = Path(directory)
    run_paths = []
    for index, payload in enumerate(runs):
        path = root / f"run-{index}.json"
        path.write_text(json.dumps(payload))
        run_paths.append(path)
    manifest_path = root / "manifest.json"
    evaluation_path = root / "evaluation.json"
    manifest_path.write_text(json.dumps(manifest))
    evaluation_path.write_text(json.dumps(evaluation))
    return run_paths, manifest_path, evaluation_path


class PolicyAdmissionTests(unittest.TestCase):
    def test_accepts_complete_seed_aligned_evidence(self) -> None:
        manifest, evaluation = language_bundle()
        with TemporaryDirectory() as directory:
            paths, manifest_path, evaluation_path = write_bundle(
                directory,
                [run(1001), run(1002)],
                manifest,
                evaluation,
            )
            report = verify_policy_admission(
                paths,
                manifest_path,
                evaluation_path,
                required_seeds=[1001, 1002],
                minimum_outcome_success_rate=1.0,
            )

        self.assertTrue(report["accepted"])
        self.assertEqual(report["failed_checks"], [])

    def test_rejects_missing_language_case(self) -> None:
        manifest, evaluation = language_bundle()
        evaluation["cases"].pop()
        with TemporaryDirectory() as directory:
            paths, manifest_path, evaluation_path = write_bundle(
                directory, [run(1001)], manifest, evaluation
            )
            report = verify_policy_admission(
                paths,
                manifest_path,
                evaluation_path,
                required_seeds=[1001],
            )

        self.assertFalse(report["accepted"])
        self.assertIn("language_coverage_complete", report["failed_checks"])

    def test_rejects_wrong_seed_and_contradictory_success(self) -> None:
        manifest, evaluation = language_bundle()
        contradictory = run(9999)
        contradictory["result"]["outcome_success"] = False
        with TemporaryDirectory() as directory:
            paths, manifest_path, evaluation_path = write_bundle(
                directory, [run(1001), contradictory], manifest, evaluation
            )
            report = verify_policy_admission(
                paths,
                manifest_path,
                evaluation_path,
                required_seeds=[1001, 1002],
            )

        self.assertFalse(report["accepted"])
        self.assertIn("seed_set_exact", report["failed_checks"])
        self.assertIn("result_schema_v3_valid", report["failed_checks"])

    def test_rejects_recovery_after_safety_failure(self) -> None:
        manifest, evaluation = language_bundle()
        evidence = run(1001)
        evidence["recovery_attempts"] = 1
        evidence["recovery_history"] = [
            {
                "failure_class": "safety_violation",
                "allowed_skills": [],
                "requires_confirmation": False,
                "automatic_execution": False,
                "remaining_attempts": 1,
            }
        ]
        evidence["trace"] = [
            {"sequence": 1, "event": "confirm", "state": "armed"},
            {"sequence": 2, "event": "execute", "state": "executing"},
            {"sequence": 3, "event": "confirm_recovery", "state": "armed"},
            {"sequence": 4, "event": "execute", "state": "executing"},
        ]
        with TemporaryDirectory() as directory:
            paths, manifest_path, evaluation_path = write_bundle(
                directory, [evidence], manifest, evaluation
            )
            report = verify_policy_admission(
                paths,
                manifest_path,
                evaluation_path,
                required_seeds=[1001],
            )

        self.assertFalse(report["accepted"])
        self.assertIn("recovery_bounded", report["failed_checks"])

    def test_rejects_execution_without_confirmation_trace(self) -> None:
        manifest, evaluation = language_bundle()
        evidence = run(1001)
        evidence["trace"] = [
            {"sequence": 1, "event": "execute", "state": "executing"},
            {"sequence": 2, "event": "result", "state": "completed"},
        ]
        with TemporaryDirectory() as directory:
            paths, manifest_path, evaluation_path = write_bundle(
                directory, [evidence], manifest, evaluation
            )
            report = verify_policy_admission(
                paths,
                manifest_path,
                evaluation_path,
                required_seeds=[1001],
            )

        self.assertFalse(report["accepted"])
        self.assertIn("trace_authorized", report["failed_checks"])

    def test_rejects_mismatched_language_observation(self) -> None:
        manifest, evaluation = language_bundle()
        evaluation = deepcopy(evaluation)
        evaluation["cases"][1]["observation_id"] = "different-observation"
        with TemporaryDirectory() as directory:
            paths, manifest_path, evaluation_path = write_bundle(
                directory, [run(1001)], manifest, evaluation
            )
            report = verify_policy_admission(
                paths,
                manifest_path,
                evaluation_path,
                required_seeds=[1001],
            )

        self.assertFalse(report["accepted"])
        self.assertIn("language_cases_passed", report["failed_checks"])


if __name__ == "__main__":
    unittest.main()
