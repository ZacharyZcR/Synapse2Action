from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from synapse2action.vla import DeterministicVLABackend, run_vla_navigation_demo
from synapse2action.vla_dataset import export_dataset
from synapse2action.vla_episode import RecordingVLABackend, VLAEpisode, save_episode


def recorded_episode() -> VLAEpisode:
    recorder = RecordingVLABackend(DeterministicVLABackend())
    run_vla_navigation_demo(recorder)
    return recorder.episode()


def renamed_episode(episode: VLAEpisode, instruction: str) -> VLAEpisode:
    payload = deepcopy(episode.to_dict())
    payload["task"]["task"]["instruction"] = instruction
    for step in payload["steps"]:
        step["observation"]["task"]["instruction"] = instruction
    return VLAEpisode(payload["task"], tuple(payload["steps"]), episode.backend)


class VLADatasetTests(unittest.TestCase):
    def test_export_splits_whole_episodes_and_normalizes_samples(self) -> None:
        first = recorded_episode()
        second = renamed_episode(first, "go around the crate to point_b")

        with TemporaryDirectory() as directory:
            root = Path(directory)
            first_path = root / "first.episode.json"
            second_path = root / "second.episode.json"
            output = root / "dataset"
            save_episode(first_path, first)
            save_episode(second_path, second)

            manifest = export_dataset([first_path, second_path], output)
            train = [json.loads(line) for line in (output / "train.jsonl").read_text().splitlines()]
            validation = [json.loads(line) for line in (output / "validation.jsonl").read_text().splitlines()]

        self.assertEqual(manifest["episode_count"], 2)
        self.assertEqual(manifest["sample_count"], 88)
        self.assertEqual(manifest["splits"]["train"]["samples"], 44)
        self.assertEqual(manifest["splits"]["validation"]["samples"], 44)
        self.assertEqual({sample["episode_id"] for sample in train} & {sample["episode_id"] for sample in validation}, set())
        sample = train[0]
        self.assertEqual(len(sample["observation"]["state"]), 6)
        self.assertEqual(len(sample["observation"]["goal"]), 3)
        self.assertEqual(len(sample["action"][0]), 4)
        self.assertEqual(sample["observation"]["camera"]["encoding"], "mono8")
        self.assertIn("obstacles", sample["observation"])
        obstacle = next(
            obstacle
            for dataset_sample in train
            for obstacle in dataset_sample["observation"]["obstacles"]
        )
        self.assertEqual(
            set(obstacle),
            {"obstacle_id", "x", "y", "radius"},
        )

    def test_export_is_deterministic_regardless_of_input_order(self) -> None:
        first = recorded_episode()
        second = renamed_episode(first, "alternate instruction")

        with TemporaryDirectory() as directory:
            root = Path(directory)
            first_path = root / "first.json"
            second_path = root / "second.json"
            save_episode(first_path, first)
            save_episode(second_path, second)
            export_dataset([first_path, second_path], root / "one")
            export_dataset([second_path, first_path], root / "two")

            for name in ("manifest.json", "train.jsonl", "validation.jsonl"):
                self.assertEqual((root / "one" / name).read_bytes(), (root / "two" / name).read_bytes())

    def test_duplicate_episode_content_is_rejected(self) -> None:
        episode = recorded_episode()

        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.json"
            second = root / "second.json"
            save_episode(first, episode)
            save_episode(second, episode)

            with self.assertRaisesRegex(ValueError, "duplicate"):
                export_dataset([first, second], root / "dataset")


if __name__ == "__main__":
    unittest.main()
