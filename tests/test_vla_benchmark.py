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
    export_dataset(sorted(episodes.glob("*.episode.json")), dataset, validation_fraction=0.2)
    train_knn_baseline(dataset, checkpoint)
    return dataset, checkpoint


class VLABenchmarkTests(unittest.TestCase):
    def test_held_out_benchmark_exposes_closed_loop_failure(self) -> None:
        with TemporaryDirectory() as directory:
            dataset, checkpoint = build_benchmark(Path(directory))

            report = benchmark_knn_baseline(dataset, checkpoint, SCENARIOS)

        self.assertEqual(report["training_episodes"], 4)
        self.assertEqual(report["validation_episodes"], 1)
        self.assertEqual(report["validation_samples"], 49)
        self.assertGreater(report["validation_velocity_mae"], 0.1)
        self.assertEqual(report["validation_duration_accuracy"], 1.0)
        self.assertEqual(report["closed_loop_passed"], 0)
        self.assertEqual(report["closed_loop_failed"], 1)
        self.assertEqual(report["closed_loop_success_rate"], 0.0)
        self.assertEqual(report["failed"], 1)
        result = report["results"][0]
        self.assertEqual(result["scenario"], "offset_obstacle")
        self.assertEqual(result["execution_detail"], "action chunk intersects obstacle")
        self.assertGreater(result["goal_error_m"], 1.0)

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

        self.assertEqual(knn["closed_loop_success_rate"], 0.0)
        self.assertEqual(ridge["benchmark"], "ridge_vla_held_out_navigation")
        self.assertEqual(ridge["closed_loop_success_rate"], 1.0)
        self.assertEqual(ridge["failed"], 0)
        self.assertLess(ridge["validation_velocity_mae"], knn["validation_velocity_mae"])
        self.assertEqual(ridge["results"][0]["scenario"], "offset_obstacle")
        self.assertTrue(ridge["results"][0]["passed"])

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
