import tempfile
import unittest
from pathlib import Path

from synapse2action.demo import acquire_demo_eeg, load_demo_scenario, run_demo
from synapse2action.eeg import load_recording, save_recording


class DemoTests(unittest.TestCase):
    def test_hardware_free_pipeline_completes(self) -> None:
        report = run_demo()

        self.assertTrue(report["completed"])
        self.assertEqual(report["planned_actions"], 1)
        self.assertEqual(report["robot_actions"], 1)
        self.assertEqual(report["final_state"], "completed")
        self.assertEqual(len(report["pipeline"]), 7)

    def test_demo_report_is_deterministic(self) -> None:
        self.assertEqual(run_demo(), run_demo())

    def test_bundled_scenarios_complete(self) -> None:
        for path in Path("experiments/demos").glob("*.json"):
            with self.subTest(path=path):
                report = run_demo(load_demo_scenario(path))
                self.assertTrue(report["passed"])
                self.assertEqual(report["tabletop_final"]["item"]["object_id"], path.stem)

    def test_recorded_eeg_replays_identically(self) -> None:
        scenario = load_demo_scenario(Path("experiments/demos/red_cube.json"))
        windows = acquire_demo_eeg(scenario)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "recording.json"
            save_recording(path, windows)

            replayed = run_demo(scenario, load_recording(path))

        self.assertEqual(replayed, run_demo(scenario, windows))


if __name__ == "__main__":
    unittest.main()
