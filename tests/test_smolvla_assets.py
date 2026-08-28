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


if __name__ == "__main__":
    unittest.main()
