from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from synapse2action.navigation import load_navigation_scenario
from synapse2action.navigation_suite import run_navigation_suite
from synapse2action.vla_episode import load_episode


SCENARIOS = Path("experiments/navigation")


class NavigationSuiteTests(unittest.TestCase):
    def test_bundled_geometry_distribution_passes_and_records_episodes(self) -> None:
        with TemporaryDirectory() as directory:
            episode_directory = Path(directory) / "episodes"
            report = run_navigation_suite(SCENARIOS, episode_directory)
            episode_paths = sorted(episode_directory.glob("*.episode.json"))
            episodes = [load_episode(path) for path in episode_paths]

        self.assertEqual(report["scenario_count"], 10)
        self.assertEqual(report["passed"], 10)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["recorded_episodes"], 10)
        self.assertEqual(len(episode_paths), 10)
        self.assertEqual(sum(len(episode.steps) for episode in episodes), report["total_control_cycles"])
        instructions = {episode.task["task"]["instruction"] for episode in episodes}
        self.assertGreater(len(instructions), 1)
        self.assertEqual({result["replan_count"] for result in report["results"]}, {0, 1})

    def test_scenario_loader_preserves_geometry_and_timing(self) -> None:
        scenario = load_navigation_scenario(SCENARIOS / "04_diagonal_dynamic.json")

        self.assertEqual(scenario.name, "diagonal_dynamic")
        self.assertNotEqual(scenario.start.y, scenario.goal.y)
        self.assertEqual(scenario.obstacles[0].active_from_ms, 200)
        self.assertEqual(scenario.sensor_range_m, 2.5)

    def test_suite_report_is_deterministic(self) -> None:
        self.assertEqual(run_navigation_suite(SCENARIOS), run_navigation_suite(SCENARIOS))


if __name__ == "__main__":
    unittest.main()
