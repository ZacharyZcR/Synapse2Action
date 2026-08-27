import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from synapse2action.navigation import load_navigation_scenario
from synapse2action.navigation_suite import run_navigation_suite
from synapse2action.vla import run_vla_navigation_demo
from synapse2action.vla_dataset import export_dataset
from synapse2action.vla_ridge import (
    RidgeVLABackend,
    load_ridge_checkpoint,
    train_chunked_temporal_ridge_baseline,
    train_ridge_baseline,
    train_temporal_ridge_baseline,
)


SCENARIOS = Path("experiments/navigation")


def build_dataset(root: Path) -> Path:
    episodes = root / "episodes"
    dataset = root / "dataset"
    run_navigation_suite(SCENARIOS, episodes)
    export_dataset(sorted(episodes.glob("*.episode.json")), dataset, validation_fraction=0.3)
    return dataset


class RidgeVLABaselineTests(unittest.TestCase):
    def test_trained_checkpoint_evaluates_and_runs_held_out_scenario(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = build_dataset(root)
            checkpoint_path = root / "ridge.json"

            metrics = train_ridge_baseline(dataset, checkpoint_path)
            checkpoint = load_ridge_checkpoint(checkpoint_path)
            scenario = load_navigation_scenario(SCENARIOS / "05_offset_obstacle.json")
            report = run_vla_navigation_demo(RidgeVLABackend(checkpoint), scenario)

        self.assertEqual(metrics["training_episodes"], 7)
        self.assertEqual(metrics["training_samples"], 339)
        self.assertEqual(metrics["validation_episodes"], 3)
        self.assertEqual(metrics["validation_samples"], 122)
        self.assertAlmostEqual(metrics["validation_velocity_mae"], 0.01388720503560708)
        self.assertEqual(metrics["validation_duration_accuracy"], 1.0)
        self.assertTrue(report["passed"])
        self.assertEqual(report["vla_backend"], "RidgeVLABackend")
        self.assertEqual(report["control_cycles"], 54)

    def test_checkpoint_is_deterministic(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = build_dataset(root)

            train_ridge_baseline(dataset, root / "one.json")
            train_ridge_baseline(dataset, root / "two.json")

            self.assertEqual((root / "one.json").read_bytes(), (root / "two.json").read_bytes())

    def test_temporal_checkpoint_runs_with_resettable_observation_history(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = build_dataset(root)
            checkpoint_path = root / "temporal-ridge.json"

            metrics = train_temporal_ridge_baseline(dataset, checkpoint_path)
            checkpoint = load_ridge_checkpoint(checkpoint_path)
            scenario = load_navigation_scenario(SCENARIOS / "05_offset_obstacle.json")
            backend = RidgeVLABackend(checkpoint)
            first = run_vla_navigation_demo(backend, scenario)
            second = run_vla_navigation_demo(backend, scenario)

        self.assertEqual(metrics["baseline"], "temporal_ridge_behavior_cloning")
        self.assertAlmostEqual(metrics["validation_velocity_mae"], 0.012672697879258805)
        self.assertEqual(checkpoint.history_steps, 1)
        self.assertEqual(checkpoint.temporal_regularization, 100_000.0)
        self.assertEqual(checkpoint.to_dict()["schema_version"], 2)
        self.assertEqual(first, second)
        self.assertTrue(first["passed"])
        self.assertEqual(first["control_cycles"], 53)

    def test_chunked_checkpoint_predicts_four_commands_with_receding_execution(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = build_dataset(root)
            checkpoint_path = root / "chunked-ridge.json"

            metrics = train_chunked_temporal_ridge_baseline(dataset, checkpoint_path)
            checkpoint = load_ridge_checkpoint(checkpoint_path)
            scenario = load_navigation_scenario(SCENARIOS / "05_offset_obstacle.json")
            report = run_vla_navigation_demo(
                RidgeVLABackend(checkpoint),
                scenario,
                execution_horizon=1,
            )

        self.assertEqual(metrics["baseline"], "chunked_temporal_ridge_behavior_cloning")
        self.assertEqual(metrics["action_horizon"], 4)
        self.assertAlmostEqual(metrics["validation_velocity_mae"], 0.013304664700798758)
        self.assertEqual(checkpoint.action_horizon, 4)
        self.assertEqual(len(checkpoint.weights), 12)
        self.assertEqual(checkpoint.to_dict()["schema_version"], 3)
        self.assertEqual(checkpoint.to_dict()["action_padding"], "repeat_last")
        self.assertTrue(report["passed"])
        self.assertEqual(report["predicted_action_horizon"], 4)
        self.assertEqual(report["execution_horizon"], 1)
        self.assertEqual(report["control_cycles"], 53)

    def test_corrupt_checkpoint_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps({"format": "synapse2action.ridge_vla"}), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_ridge_checkpoint(path)

    def test_non_integer_chunk_horizon_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = build_dataset(root)
            path = root / "chunked.json"
            train_chunked_temporal_ridge_baseline(dataset, path)
            payload = json.loads(path.read_text())
            payload["action_horizon"] = "four"
            path.write_text(json.dumps(payload))

            with self.assertRaises(ValueError):
                load_ridge_checkpoint(path)


if __name__ == "__main__":
    unittest.main()
