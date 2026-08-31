from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "simulation/run_harness_unitree.py"


class ProductionEntryTests(unittest.TestCase):
    def run_entry(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RUNNER), *arguments],
            cwd=ROOT,
            env={"PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_required_components_have_no_defaults(self) -> None:
        result = self.run_entry()
        self.assertEqual(result.returncode, 2)
        self.assertIn("--task", result.stderr)
        self.assertIn("--policy", result.stderr)
        self.assertIn("--planner", result.stderr)

    def test_live_entry_rejects_mock_planner(self) -> None:
        result = self.run_entry(
            "--task",
            "pick-place",
            "--policy",
            "groot",
            "--planner",
            "mock",
            "--task-spec",
            "experiments/tasks/g1_groot_apple_to_plate.json",
            "--decoded-intents",
            "missing.json",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires --planner live", result.stderr)

    def test_live_entry_rejects_scripted_policy(self) -> None:
        result = self.run_entry(
            "--task",
            "pick-place",
            "--policy",
            "scripted",
            "--planner",
            "live",
            "--task-spec",
            "experiments/tasks/g1_pick_place.json",
            "--decoded-intents",
            "missing.json",
            "--planner-base-url",
            "http://127.0.0.1:1/v1",
            "--planner-model",
            "test",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("forbids ScriptedPolicy", result.stderr)

    def test_test_doubles_require_explicit_opt_in(self) -> None:
        source = RUNNER.read_text()
        self.assertIn('action="store_true"', source)
        self.assertIn("--allow-test-doubles", source)
        self.assertNotIn('default="mock"', source)
        self.assertNotIn('default="scripted"', source)
        self.assertNotIn("default_pick_place_spec", source)


if __name__ == "__main__":
    unittest.main()
