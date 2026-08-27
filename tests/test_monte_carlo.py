import unittest
from pathlib import Path

from synapse2action.monte_carlo import run_monte_carlo


class MonteCarloTests(unittest.TestCase):
    def test_gate_reduces_unauthorized_actions(self) -> None:
        result = run_monte_carlo(Path("experiments/monte_carlo/false_activation.json"))

        self.assertLess(result["gated"]["unauthorized_actions"], result["baseline"]["unauthorized_actions"])

    def test_seeded_run_is_deterministic(self) -> None:
        path = Path("experiments/monte_carlo/false_activation.json")

        self.assertEqual(run_monte_carlo(path), run_monte_carlo(path))


if __name__ == "__main__":
    unittest.main()
