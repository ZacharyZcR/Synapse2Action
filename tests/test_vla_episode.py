from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from synapse2action.vla import DeterministicVLABackend, run_vla_navigation_demo
from synapse2action.vla_episode import (
    RecordingVLABackend,
    ReplayVLABackend,
    load_episode,
    save_episode,
)


class VLAEpisodeTests(unittest.TestCase):
    def test_recorded_episode_replays_identical_navigation(self) -> None:
        recorder = RecordingVLABackend(DeterministicVLABackend())
        recorded_report = run_vla_navigation_demo(recorder)
        episode = recorder.episode()

        with TemporaryDirectory() as directory:
            path = Path(directory) / "episode.json"
            save_episode(path, episode)
            loaded = load_episode(path)

        replay = ReplayVLABackend(loaded)
        replayed_report = run_vla_navigation_demo(replay)
        replay.assert_complete()

        self.assertEqual(len(loaded.steps), recorded_report["control_cycles"])
        self.assertEqual(replay.index, replayed_report["control_cycles"])
        self.assertEqual(replayed_report["final_pose"], recorded_report["final_pose"])
        self.assertEqual(replayed_report["trajectory"], recorded_report["trajectory"])
        camera = loaded.steps[6]["observation"]["sensor"]["camera"]
        self.assertEqual(camera["encoding"], "mono8")
        self.assertTrue(camera["data_base64"])

    def test_replay_rejects_diverged_observation(self) -> None:
        recorder = RecordingVLABackend(DeterministicVLABackend())
        run_vla_navigation_demo(recorder)
        episode = recorder.episode()
        episode.steps[0]["observation"]["step"] = 99

        with self.assertRaisesRegex(ValueError, "diverged at step 0"):
            run_vla_navigation_demo(ReplayVLABackend(episode))

    def test_load_rejects_non_contiguous_step_index(self) -> None:
        recorder = RecordingVLABackend(DeterministicVLABackend())
        run_vla_navigation_demo(recorder)
        episode = recorder.episode()

        with TemporaryDirectory() as directory:
            path = Path(directory) / "episode.json"
            save_episode(path, episode)
            payload = path.read_text(encoding="utf-8").replace('"index": 1', '"index": 9', 1)
            path.write_text(payload, encoding="utf-8")

            with self.assertRaises(ValueError):
                load_episode(path)


if __name__ == "__main__":
    unittest.main()
