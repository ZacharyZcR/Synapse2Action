import tempfile
import unittest
from pathlib import Path

from synapse2action.demo_suite import run_demo_suite


class DemoSuiteTests(unittest.TestCase):
    def test_all_demo_scenarios_complete_and_emit_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifacts = Path(temporary)
            report = run_demo_suite(Path("experiments/demos"), artifacts)

            self.assertEqual(report["scenario_count"], 4)
            self.assertEqual(report["completed"], 2)
            self.assertEqual(report["passed"], 4)
            self.assertEqual(report["failed"], 0)
            self.assertEqual(report["pass_rate"], 1.0)
            self.assertEqual(len(list(artifacts.glob("*.json"))), 4)
            self.assertEqual(len(list(artifacts.glob("*.html"))), 4)

    def test_suite_report_is_deterministic(self) -> None:
        directory = Path("experiments/demos")

        self.assertEqual(run_demo_suite(directory), run_demo_suite(directory))


if __name__ == "__main__":
    unittest.main()
