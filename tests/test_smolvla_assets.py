from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SmolVLAAssetsTests(unittest.TestCase):
    def test_lock_pins_real_lerobot_checkpoint(self) -> None:
        lock = json.loads((ROOT / "simulation" / "vla.lock.json").read_text())
        self.assertEqual(lock["lerobot"], "0.6.1")
        self.assertEqual(lock["model"], "lerobot/smolvla_base")
        self.assertEqual(lock["parameter_count"], 450046176)

    def test_runner_invokes_real_policy_inference(self) -> None:
        source = (ROOT / "simulation" / "smolvla_inference_smoke.py").read_text()
        self.assertIn("SmolVLAPolicy.from_pretrained", source)
        self.assertIn("policy.select_action", source)
        self.assertIn("make_pre_post_processors", source)
        self.assertNotIn("DeterministicVLABackend", source)

    def test_g1_training_uses_dataset_inferred_dimensions(self) -> None:
        runner = (ROOT / "simulation" / "run_smolvla_g1_train.sh").read_text()
        self.assertIn("lerobot-train", runner)
        self.assertIn("--policy.input_features=null", runner)
        self.assertIn("--policy.output_features=null", runner)
        self.assertIn("--policy.push_to_hub=false", runner)
        self.assertIn("validate_smolvla_g1_checkpoint.py", runner)

    def test_g1_checkpoint_gate_requires_full_action_space(self) -> None:
        source = (ROOT / "simulation" / "validate_smolvla_g1_checkpoint.py").read_text()
        self.assertIn('== [29]', source)
        self.assertIn('action.shape == (29,)', source)
        self.assertIn('sum(key.startswith("observation.images.")', source)

    def test_g1_dataset_converter_supports_multiple_episodes(self) -> None:
        source = (ROOT / "simulation" / "convert_g1_episode_to_lerobot.py").read_text()
        self.assertIn('nargs="+"', source)
        self.assertIn('"episode_count": reopened.meta.total_episodes == episode_count', source)
        self.assertIn("for episode, episode_frames in zip(episodes, frame_counts, strict=True)", source)

    def test_g1_offline_gate_reports_manipulation_joint_error(self) -> None:
        source = (ROOT / "simulation" / "evaluate_smolvla_g1_offline.py").read_text()
        self.assertIn("ARM_WAIST_JOINTS", source)
        self.assertIn('"arm_waist_mse"', source)
        self.assertIn("policy.config.chunk_size", source)

    def test_g1_dataset_suite_records_independent_timing_variations(self) -> None:
        runner = (ROOT / "simulation" / "run_lerobot_dataset_suite.sh").read_text()
        self.assertIn("S2A_MANIPULATION_TIME_SCALE", runner)
        self.assertIn("S2A_EPISODE_NAME", runner)
        self.assertIn("g1-pick-place-sim-suite", runner)

    def test_pick_place_uses_rectangular_drop_zone_geometry(self) -> None:
        simulator = (ROOT / "simulation" / "g1_mujoco_pick_place.py").read_text()
        runner = (ROOT / "simulation" / "run_unitree_pick_place.sh").read_text()
        self.assertIn('"drop_zone_half_extents_xy_m": [0.12, 0.22]', simulator)
        self.assertIn('simulator["final_object_center_in_drop_zone"]', runner)

    def test_suite_training_uses_episode_level_holdout(self) -> None:
        runner = (ROOT / "simulation" / "run_smolvla_g1_suite_train.sh").read_text()
        self.assertIn("--dataset.eval_split=0.2", runner)
        self.assertIn("g1-pick-place-1.05.npz", runner)
        self.assertIn("evaluate_smolvla_g1_offline.py", runner)
        self.assertIn("HF_HUB_OFFLINE=1", runner)
        self.assertIn("simulation/vendor/huggingface", runner)


if __name__ == "__main__":
    unittest.main()
