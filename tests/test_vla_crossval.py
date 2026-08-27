import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from synapse2action.navigation_suite import run_navigation_suite
from synapse2action.vla_crossval import run_leave_one_scenario_out


SCENARIOS = Path("experiments/navigation")


class VLACrossValidationTests(unittest.TestCase):
    def test_leave_one_scenario_out_compares_ridge_and_knn(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            episode_directory = root / "episodes"
            run_navigation_suite(SCENARIOS, episode_directory)
            episodes = sorted(episode_directory.glob("*.episode.json"))

            ridge = run_leave_one_scenario_out(episodes, SCENARIOS, root / "ridge", "ridge")
            temporal = run_leave_one_scenario_out(
                episodes,
                SCENARIOS,
                root / "temporal",
                "temporal-ridge",
            )
            knn = run_leave_one_scenario_out(episodes, SCENARIOS, root / "knn", "knn")

            first_fold = ridge["folds"][0]
            manifest = json.loads(
                (root / "ridge" / first_fold["dataset"] / "manifest.json").read_text()
            )
            checkpoint_exists = (root / "ridge" / first_fold["checkpoint"]).is_file()

        self.assertEqual(ridge["episode_count"], 10)
        self.assertEqual(ridge["fold_count"], 10)
        self.assertEqual(ridge["validation_samples"], 461)
        self.assertAlmostEqual(ridge["validation_velocity_mae"], 0.018508698452334143)
        self.assertEqual(ridge["closed_loop_passed"], 10)
        self.assertEqual(ridge["closed_loop_success_rate"], 1.0)
        self.assertEqual(ridge["failed"], 0)
        self.assertEqual(temporal["fold_count"], 10)
        self.assertEqual(temporal["validation_samples"], 461)
        self.assertAlmostEqual(temporal["validation_velocity_mae"], 0.01657545266814853)
        self.assertLess(
            temporal["validation_velocity_mae"],
            ridge["validation_velocity_mae"],
        )
        self.assertEqual(temporal["closed_loop_passed"], 10)
        self.assertEqual(temporal["closed_loop_success_rate"], 1.0)
        self.assertEqual(temporal["failed"], 0)
        self.assertEqual(knn["validation_samples"], 461)
        self.assertAlmostEqual(knn["validation_velocity_mae"], 0.08412305629771478)
        self.assertEqual(knn["closed_loop_passed"], 2)
        self.assertEqual(knn["closed_loop_success_rate"], 0.2)
        self.assertEqual(knn["failed"], 8)
        self.assertEqual(manifest["split_strategy"], "explicit_episode_sources")
        self.assertEqual(len(manifest["splits"]["train"]["episodes"]), 9)
        self.assertEqual(len(manifest["splits"]["validation"]["episodes"]), 1)
        self.assertTrue(checkpoint_exists)

    def test_leave_one_scenario_out_report_is_deterministic(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            episode_directory = root / "episodes"
            run_navigation_suite(SCENARIOS, episode_directory)
            episodes = sorted(episode_directory.glob("*.episode.json"))

            first = run_leave_one_scenario_out(episodes, SCENARIOS, root / "first")
            second = run_leave_one_scenario_out(episodes, SCENARIOS, root / "second")

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
