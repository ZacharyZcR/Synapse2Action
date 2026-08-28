from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicSSVEP256AssetsTests(unittest.TestCase):
    def test_benchmark_uses_high_density_data_and_rest(self) -> None:
        source = (ROOT / "simulation" / "public_ssvep_256_benchmark.py").read_text()
        self.assertIn('f"dataset2/T{subject}a.{suffix}"', source)
        self.assertIn('CHANNEL_NAMES = ("P7", "O1", "Oz", "O2", "P8")', source)
        self.assertIn('"protocol-defined five-second rest intervals"', source)
        self.assertIn('"idle_false_activations_per_minute"', source)
        self.assertIn('"development_accuracy"', source)
        self.assertIn("WINDOW_SECONDS = 2", source)

    def test_runner_reuses_locked_wfdb_image(self) -> None:
        runner = (ROOT / "simulation" / "run_public_ssvep_256.sh").read_text()
        self.assertIn("synapse2action-eeg:locked-v1", runner)
        self.assertIn("public-ssvep-256.json", runner)


if __name__ == "__main__":
    unittest.main()
