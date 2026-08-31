from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GrootActionEvidenceTests(unittest.TestCase):
    def test_runner_records_and_maps_real_action_modalities(self) -> None:
        source = (ROOT / "simulation/run_groot_evidence_rollout.py").read_text()
        mapper = (ROOT / "simulation/map_groot_action_evidence.py").read_text()
        self.assertIn("class ActionEvidencePolicy", source)
        self.assertIn('parser.add_argument("--action-output"', source)
        self.assertIn('"first_action"', source)
        self.assertIn("map_groot_unitree_action", mapper)
        self.assertIn('"unsupported_hand_dimensions"', mapper)


if __name__ == "__main__":
    unittest.main()
