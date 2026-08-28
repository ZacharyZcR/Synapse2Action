from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from synapse2action.components import MockPlanner
from synapse2action.eeg_planner_benchmark import run_eeg_planner_benchmark


class EEGPlannerBenchmarkTests(unittest.TestCase):
    def test_measures_selection_gate_and_plan_yield_without_execution(self) -> None:
        report = {
            "window_seconds": 2,
            "continuous_stream": {
                "events": [
                    {"window": 0, "expected": "select", "decoded": "select"},
                    {"window": 1, "expected": "confirm", "decoded": "select"},
                    {"window": 2, "expected": "select", "decoded": "abstain"},
                    {"window": 3, "expected": "stop", "decoded": "stop"},
                ]
            },
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "eeg.json"
            path.write_text(json.dumps(report))
            result = run_eeg_planner_benchmark(path, MockPlanner(), "fixture", "fixture_target")

        metrics = result["metrics"]
        self.assertFalse(result["accepted"])
        self.assertEqual(metrics["selection_precision"], 0.5)
        self.assertEqual(metrics["selection_recall"], 0.5)
        self.assertEqual(metrics["conditional_plan_validity"], 1.0)
        self.assertEqual(metrics["end_to_end_plan_recall"], 0.5)
        self.assertEqual(metrics["unexpected_executions"], 0)
        self.assertEqual(sum(item["valid_plan"] for item in result["results"]), 2)

    def test_rejects_report_without_continuous_events(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "eeg.json"
            path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "continuous event stream"):
                run_eeg_planner_benchmark(path, MockPlanner(), "fixture", "fixture_target")


if __name__ == "__main__":
    unittest.main()
