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


if __name__ == "__main__":
    unittest.main()
