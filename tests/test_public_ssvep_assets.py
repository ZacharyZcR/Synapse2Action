from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicSSVEPAssetsTests(unittest.TestCase):
    def test_runner_uses_official_wfdb_and_locked_image(self) -> None:
        runner = (ROOT / "simulation" / "run_public_ssvep.sh").read_text()
        dockerfile = (ROOT / "simulation" / "docker" / "Dockerfile.eeg").read_text()
        self.assertIn("synapse2action-eeg:locked-v1", runner)
        self.assertIn('"wfdb==4.3.0"', dockerfile)
        self.assertIn('"scikit-learn==1.7.2"', dockerfile)

    def test_benchmark_is_subject_independent_and_replays_harness(self) -> None:
        source = (ROOT / "simulation" / "public_ssvep_benchmark.py").read_text()
        self.assertIn('wfdb.dl_files("mssvepdb"', source)
        self.assertIn('"train_subjects": ["001", "002"]', source)
        self.assertIn('"calibration_subjects": ["003"]', source)
        self.assertIn('"test_subjects": ["004"]', source)
        self.assertIn("CCA(n_components=1", source)
        self.assertIn("class SpectralMLP", source)
        self.assertIn("Harness.handle(Intent)", source)
        self.assertIn('"coverage"', source)

    def test_public_predictions_drive_unitree_harness_runner(self) -> None:
        runner = (ROOT / "simulation" / "run_public_ssvep_unitree.sh").read_text()
        harness = (ROOT / "simulation" / "run_harness_unitree.py").read_text()
        self.assertIn("run_public_ssvep.sh", runner)
        self.assertIn("--task pick-place", runner)
        self.assertIn("--decoded-intents", runner)
        self.assertIn("public EEG did not decode the execution authorization sequence", harness)


if __name__ == "__main__":
    unittest.main()
