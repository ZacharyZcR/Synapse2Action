from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LiveEEGAssetsTests(unittest.TestCase):
    def test_container_pins_real_brainflow_and_lsl_sdks(self) -> None:
        dockerfile = (ROOT / "simulation" / "docker" / "Dockerfile.live-eeg").read_text()
        self.assertIn('"brainflow==5.19.0"', dockerfile)
        self.assertIn('"pylsl==1.17.6"', dockerfile)
        self.assertIn("liblsl-1.17.7-jammy_amd64.tar.gz", dockerfile)
        self.assertIn("a73dfca12aaffe65d22599032fa6ba683e9a54e2f8e4212cfdb05d5854b86bec", dockerfile)

    def test_live_gate_uses_sdk_streams_calibration_and_abstention(self) -> None:
        source = (ROOT / "simulation" / "live_eeg_lsl.py").read_text()
        self.assertIn("BoardIds.SYNTHETIC_BOARD", source)
        self.assertIn("StreamOutlet", source)
        self.assertIn("StreamInlet", source)
        self.assertIn('("calibration", "select")', source)
        self.assertIn('"drift_within_limit"', source)
        self.assertIn('"uncertain_abstention"', source)
        self.assertIn('"false_activations"', source)

    def test_live_gate_drives_existing_unitree_harness(self) -> None:
        runner = (ROOT / "simulation" / "run_live_eeg_unitree.sh").read_text()
        self.assertIn("--platform linux/amd64", runner)
        self.assertIn("run_harness_unitree.py", runner)
        self.assertIn("--decoded-intents", runner)
        self.assertIn("--task pick-place", runner)


if __name__ == "__main__":
    unittest.main()
