from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from synapse2action.llm_vla_benchmark import run_llm_vla_benchmark


def write_report(directory: str, simulator: dict[str, object]) -> Path:
    path = Path(directory) / "run.json"
    path.write_text(
        json.dumps(
            {
                "planner": {
                    "status": "completed",
                    "provider": "fixture",
                    "model": "fixture-model",
                    "output": {
                        "skill": "pick_and_place",
                        "arguments": {"target": "red_cube", "destination": "drop_tray"},
                    },
                },
                "unitree_simulator": simulator,
            }
        )
    )
    return path


class LLMVLABenchmarkTests(unittest.TestCase):
    def test_missing_binding_and_latency_are_explicit_failures(self) -> None:
        with TemporaryDirectory() as directory:
            path = write_report(
                directory,
                {
                    "vla_runtime": {
                        "accepted": True,
                        "chunks_received": 3,
                        "minimum_chunk_coverage_ms": 10_000,
                        "stale_fallbacks": 0,
                    }
                },
            )
            report = run_llm_vla_benchmark(path)

        self.assertFalse(report["accepted"])
        self.assertFalse(report["metrics"]["task_binding_proven"])
        self.assertFalse(report["metrics"]["first_chunk_latency_observable"])

    def test_accepts_complete_boundary_evidence(self) -> None:
        binding = {
            "skill": "pick_and_place",
            "arguments": {"target": "red_cube", "destination": "drop_tray"},
            "source": "planner_action",
        }
        with TemporaryDirectory() as directory:
            path = write_report(
                directory,
                {
                    "vla_task_binding": binding,
                    "vla_first_chunk_latency_ms": 900,
                    "vla_plan_counterfactual": {
                        "changed": True,
                        "same_observation": True,
                        "same_seed": True,
                    },
                    "vla_runtime": {
                        "accepted": True,
                        "chunks_received": 3,
                        "minimum_chunk_coverage_ms": 10_000,
                        "stale_fallbacks": 0,
                    },
                },
            )
            report = run_llm_vla_benchmark(path)

        self.assertTrue(report["accepted"])
        self.assertTrue(report["metrics"]["task_binding_proven"])
        self.assertTrue(report["metrics"]["first_chunk_latency_within_coverage"])

    def test_accepts_separate_counterfactual_artifact(self) -> None:
        with TemporaryDirectory() as directory:
            path = write_report(
                directory,
                {
                    "vla_task_binding": {
                        "skill": "pick_and_place",
                        "arguments": {"target": "red_cube", "destination": "drop_tray"},
                        "source": "planner_action",
                    },
                    "vla_first_chunk_latency_ms": 900,
                    "vla_runtime": {
                        "accepted": True,
                        "chunks_received": 1,
                        "minimum_chunk_coverage_ms": 10_000,
                        "stale_fallbacks": 0,
                    },
                },
            )
            counterfactual = Path(directory) / "counterfactual.json"
            counterfactual.write_text(json.dumps({
                "changed": True,
                "same_observation": True,
                "same_seed": True,
            }))
            report = run_llm_vla_benchmark(path, counterfactual)

        self.assertTrue(report["accepted"])
        self.assertEqual(report["counterfactual_report"], str(counterfactual))

    def test_rejects_unrelated_report(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "Planner and VLA"):
                run_llm_vla_benchmark(path)


if __name__ == "__main__":
    unittest.main()
