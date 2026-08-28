from __future__ import annotations

from pathlib import Path
import unittest

from synapse2action.planner_benchmark import run_planner_benchmark


ROOT = Path(__file__).parents[1]


class PlannerBenchmarkTests(unittest.TestCase):
    def test_bundled_boundary_benchmark_contains_all_failures(self) -> None:
        report = run_planner_benchmark(ROOT / "experiments" / "planner")

        self.assertEqual(report["passed"], 7)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["metrics"]["invented_skill_attempts"], 2)
        self.assertEqual(report["metrics"]["unsafe_action_executions"], 0)
        self.assertEqual(report["metrics"]["provider_failures"], 1)
        self.assertEqual(report["metrics"]["contained_provider_failures"], 1)

    def test_report_is_deterministic(self) -> None:
        directory = ROOT / "experiments" / "planner"
        self.assertEqual(run_planner_benchmark(directory), run_planner_benchmark(directory))


if __name__ == "__main__":
    unittest.main()
