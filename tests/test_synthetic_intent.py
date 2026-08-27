import unittest
from pathlib import Path

from synapse2action.synthetic_intent import run_intent_suite


class SyntheticIntentTests(unittest.TestCase):
    def test_bundled_intent_experiments_pass(self) -> None:
        report = run_intent_suite(Path("experiments/intent_streams"))

        self.assertEqual(report["passed"], 4)
        self.assertEqual(report["failed"], 0)

    def test_seeded_results_are_deterministic(self) -> None:
        directory = Path("experiments/intent_streams")

        self.assertEqual(run_intent_suite(directory), run_intent_suite(directory))


if __name__ == "__main__":
    unittest.main()
