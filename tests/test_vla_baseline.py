from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from synapse2action.vla import DeterministicVLABackend, run_vla_navigation_demo
from synapse2action.vla_baseline import KNNVLABackend, load_knn_checkpoint, train_knn_baseline
from synapse2action.vla_dataset import export_dataset
from synapse2action.vla_episode import RecordingVLABackend, VLAEpisode, save_episode


def make_episodes() -> tuple[VLAEpisode, VLAEpisode]:
    recorder = RecordingVLABackend(DeterministicVLABackend())
    run_vla_navigation_demo(recorder)
    first = recorder.episode()
    payload = deepcopy(first.to_dict())
    instruction = "go around the crate to point_b"
    payload["task"]["task"]["instruction"] = instruction
    for step in payload["steps"]:
        step["observation"]["task"]["instruction"] = instruction
    return first, VLAEpisode(payload["task"], tuple(payload["steps"]), first.backend)


class VLABaselineTests(unittest.TestCase):
    def test_trained_checkpoint_evaluates_and_runs_closed_loop(self) -> None:
        first, second = make_episodes()

        with TemporaryDirectory() as directory:
            root = Path(directory)
            first_path = root / "first.json"
            second_path = root / "second.json"
            dataset = root / "dataset"
            checkpoint_path = root / "knn.json"
            save_episode(first_path, first)
            save_episode(second_path, second)
            manifest = export_dataset([first_path, second_path], dataset)

            metrics = train_knn_baseline(dataset, checkpoint_path)
            checkpoint = load_knn_checkpoint(checkpoint_path)
            report = run_vla_navigation_demo(KNNVLABackend(checkpoint))

        self.assertEqual(metrics["training_samples"], 44)
        self.assertEqual(metrics["validation_samples"], 44)
        self.assertEqual(metrics["validation_velocity_mae"], 0.0)
        self.assertEqual(metrics["validation_duration_accuracy"], 1.0)
        self.assertEqual(set(checkpoint.training_episode_ids), set(manifest["splits"]["train"]["episodes"]))
        self.assertEqual(set(checkpoint.training_episode_ids) & set(manifest["splits"]["validation"]["episodes"]), set())
        self.assertTrue(report["passed"])
        self.assertEqual(report["vla_backend"], "KNNVLABackend")
        self.assertEqual(report["policy_backend_requests"], report["control_cycles"] + 1)

    def test_checkpoint_is_deterministic(self) -> None:
        first, second = make_episodes()

        with TemporaryDirectory() as directory:
            root = Path(directory)
            first_path = root / "first.json"
            second_path = root / "second.json"
            dataset = root / "dataset"
            save_episode(first_path, first)
            save_episode(second_path, second)
            export_dataset([first_path, second_path], dataset)
            train_knn_baseline(dataset, root / "one.json")
            train_knn_baseline(dataset, root / "two.json")

            self.assertEqual((root / "one.json").read_bytes(), (root / "two.json").read_bytes())

    def test_corrupt_checkpoint_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps({"format": "synapse2action.knn_vla"}), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_knn_checkpoint(path)

    def test_checkpoint_rejects_non_positive_recorded_action(self) -> None:
        first, second = make_episodes()

        with TemporaryDirectory() as directory:
            root = Path(directory)
            first_path = root / "first.json"
            second_path = root / "second.json"
            dataset = root / "dataset"
            checkpoint = root / "knn.json"
            save_episode(first_path, first)
            save_episode(second_path, second)
            export_dataset([first_path, second_path], dataset)
            train_knn_baseline(dataset, checkpoint)
            payload = json.loads(checkpoint.read_text())
            payload["samples"][0]["action"][0][3] = 0
            checkpoint.write_text(json.dumps(payload))

            with self.assertRaises(ValueError):
                load_knn_checkpoint(checkpoint)


if __name__ == "__main__":
    unittest.main()
