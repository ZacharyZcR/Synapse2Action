import unittest
from pathlib import Path

from synapse2action.experiments import run_suite


class ExperimentTests(unittest.TestCase):
    def test_all_bundled_scenarios_pass(self) -> None:
        report = run_suite(Path("experiments/scenarios"))

        self.assertEqual(report["passed"], 6)
        self.assertEqual(report["failed"], 0)

    def test_report_is_deterministic(self) -> None:
        directory = Path("experiments/scenarios")

        self.assertEqual(run_suite(directory), run_suite(directory))


if __name__ == "__main__":
    unittest.main()
