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
            chunked_open = run_leave_one_scenario_out(
                episodes,
                SCENARIOS,
                root / "chunked-open",
                "chunked-ridge",
            )
            chunked_receding = run_leave_one_scenario_out(
                episodes,
                SCENARIOS,
                root / "chunked-receding",
                "chunked-ridge",
                execution_horizon=1,
            )
            chunked_ensemble = run_leave_one_scenario_out(
                episodes,
                SCENARIOS,
                root / "chunked-ensemble",
                "chunked-ridge",
                execution_horizon=1,
                temporal_ensemble_decay=0.75,
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
        self.assertAlmostEqual(chunked_open["validation_velocity_mae"], 0.019343048297592078)
        self.assertEqual(chunked_open["predicted_action_horizon"], 4)
        self.assertEqual(chunked_open["execution_horizon"], 4)
        self.assertEqual(chunked_open["closed_loop_passed"], 8)
        self.assertEqual(
            {fold["scenario"] for fold in chunked_open["folds"] if not fold["passed"]},
            {"center_crate_late", "short_range_blocked"},
        )
        self.assertEqual(sum(fold["control_cycles"] for fold in chunked_open["folds"]), 160)
        self.assertEqual(chunked_receding["predicted_action_horizon"], 4)
        self.assertEqual(chunked_receding["execution_horizon"], 1)
        self.assertEqual(chunked_receding["closed_loop_passed"], 10)
        self.assertEqual(chunked_receding["failed"], 0)
        self.assertEqual(
            sum(fold["control_cycles"] for fold in chunked_receding["folds"]),
            478,
        )
        self.assertAlmostEqual(
            chunked_receding["mean_translational_velocity_delta_mps"],
            0.012513543458248946,
        )
        self.assertEqual(chunked_ensemble["closed_loop_passed"], 10)
        self.assertEqual(chunked_ensemble["failed"], 0)
        self.assertEqual(chunked_ensemble["temporal_ensemble_decay"], 0.75)
        self.assertAlmostEqual(
            chunked_ensemble["mean_translational_velocity_delta_mps"],
            0.012338673605871193,
        )
        self.assertLess(
            chunked_ensemble["mean_translational_velocity_delta_mps"],
            chunked_receding["mean_translational_velocity_delta_mps"],
        )
        self.assertEqual(chunked_ensemble["translational_velocity_delta_samples"], 466)
        self.assertEqual(chunked_ensemble["ensemble_reset_count"], 382)
        self.assertEqual(
            sum(fold["control_cycles"] for fold in chunked_ensemble["folds"]),
            476,
        )
        self.assertEqual(
            max(fold["max_ensemble_contributors"] for fold in chunked_ensemble["folds"]),
            4,
        )
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
