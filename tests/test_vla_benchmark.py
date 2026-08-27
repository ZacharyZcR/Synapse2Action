import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from synapse2action.navigation_suite import run_navigation_suite
from synapse2action.vla_baseline import train_knn_baseline
from synapse2action.vla_benchmark import benchmark_knn_baseline, benchmark_vla_baseline
from synapse2action.vla_dataset import export_dataset
from synapse2action.vla_ridge import train_ridge_baseline


SCENARIOS = Path("experiments/navigation")


def build_benchmark(root: Path) -> tuple[Path, Path]:
    episodes = root / "episodes"
    dataset = root / "dataset"
    checkpoint = root / "knn.json"
    run_navigation_suite(SCENARIOS, episodes)
    export_dataset(sorted(episodes.glob("*.episode.json")), dataset, validation_fraction=0.3)
    train_knn_baseline(dataset, checkpoint)
    return dataset, checkpoint


class VLABenchmarkTests(unittest.TestCase):
    def test_knn_benchmark_exposes_multi_scenario_closed_loop_failures(self) -> None:
        with TemporaryDirectory() as directory:
            dataset, checkpoint = build_benchmark(Path(directory))

            report = benchmark_knn_baseline(dataset, checkpoint, SCENARIOS)

        self.assertEqual(report["training_episodes"], 7)
        self.assertEqual(report["validation_episodes"], 3)
        self.assertEqual(report["validation_samples"], 122)
        self.assertAlmostEqual(report["validation_velocity_mae"], 0.04909137177373667)
        self.assertEqual(report["validation_duration_accuracy"], 1.0)
        self.assertEqual(report["closed_loop_passed"], 1)
        self.assertEqual(report["closed_loop_failed"], 2)
        self.assertEqual(report["closed_loop_success_rate"], 1 / 3)
        self.assertEqual(report["failed"], 2)
        self.assertEqual(
            {result["scenario"] for result in report["results"] if not result["passed"]},
            {"offset_obstacle", "clear_short"},
        )

    def test_benchmark_is_deterministic(self) -> None:
        with TemporaryDirectory() as directory:
            dataset, checkpoint = build_benchmark(Path(directory))

            self.assertEqual(
                benchmark_knn_baseline(dataset, checkpoint, SCENARIOS),
                benchmark_knn_baseline(dataset, checkpoint, SCENARIOS),
            )

    def test_ridge_improves_held_out_closed_loop_behavior(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset, knn_checkpoint = build_benchmark(root)
            ridge_checkpoint = root / "ridge.json"
            train_ridge_baseline(dataset, ridge_checkpoint)

            knn = benchmark_vla_baseline(dataset, knn_checkpoint, SCENARIOS)
            ridge = benchmark_vla_baseline(dataset, ridge_checkpoint, SCENARIOS)

        self.assertEqual(knn["closed_loop_success_rate"], 1 / 3)
        self.assertEqual(ridge["benchmark"], "ridge_vla_held_out_navigation")
        self.assertEqual(ridge["closed_loop_success_rate"], 1.0)
        self.assertEqual(ridge["failed"], 0)
        self.assertLess(ridge["validation_velocity_mae"], knn["validation_velocity_mae"])
        self.assertEqual(
            {result["scenario"] for result in ridge["results"]},
            {"offset_obstacle", "center_crate_late", "clear_short"},
        )
        self.assertTrue(all(result["passed"] for result in ridge["results"]))

    def test_benchmark_rejects_checkpoint_from_different_split(self) -> None:
        with TemporaryDirectory() as directory:
            dataset, checkpoint = build_benchmark(Path(directory))
            manifest = json.loads((dataset / "manifest.json").read_text())
            payload = json.loads(checkpoint.read_text())
            payload["training_episode_ids"].append(manifest["splits"]["validation"]["episodes"][0])
            checkpoint.write_text(json.dumps(payload))

            with self.assertRaisesRegex(ValueError, "do not match"):
                benchmark_knn_baseline(dataset, checkpoint, SCENARIOS)


if __name__ == "__main__":
    unittest.main()
