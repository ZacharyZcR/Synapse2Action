from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CPUProfileTests(unittest.TestCase):
    def test_profile_declares_no_external_assets_or_hardware(self) -> None:
        profile = json.loads((ROOT / "profiles/cpu-ci.json").read_text())

        self.assertEqual(profile["schema_version"], 1)
        self.assertEqual(profile["profile_id"], "cpu-ci")
        self.assertEqual(profile["python"], ">=3.12")
        self.assertFalse(profile["external_network"])
        self.assertTrue(profile["loopback_network"])
        self.assertEqual(profile["required_hardware"], [])
        self.assertEqual(profile["required_model_artifacts"], [])
        self.assertEqual(
            profile["command"],
            [
                "python3",
                "simulation/run_cpu_ci.py",
                "--report",
                "reports/cpu-ci.json",
            ],
        )

    def test_workflow_runs_the_versioned_profile_with_minimal_permissions(self) -> None:
        workflow = (ROOT / ".github/workflows/cpu-ci.yml").read_text()

        self.assertIn("contents: read", workflow)
        self.assertIn('python-version: "3.12"', workflow)
        self.assertIn(
            "python3 simulation/run_cpu_ci.py --report reports/cpu-ci.json",
            workflow,
        )
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("pip install", workflow)

    def test_runner_reports_claim_boundary_and_real_test_counts(self) -> None:
        source = (ROOT / "simulation/run_cpu_ci.py").read_text()

        self.assertIn('"accepted": result.wasSuccessful()', source)
        self.assertIn('"run": result.testsRun', source)
        self.assertIn('discover("tests", top_level_dir=".")', source)
        self.assertIn("hardware-free repository acceptance only", source)
        self.assertNotIn("mock success", source)

    def test_profile_boundary_is_linked_from_readme(self) -> None:
        readme = (ROOT / "README.md").read_text()

        self.assertIn("simulation/run_cpu_ci.py --report reports/cpu-ci.json", readme)
        self.assertIn("](docs/deployment-profiles.md)", readme)


if __name__ == "__main__":
    unittest.main()
