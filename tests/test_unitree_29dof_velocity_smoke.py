from collections import deque
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location(
    "run_unitree_29dof_velocity_smoke", ROOT / "simulation/run_unitree_29dof_velocity_smoke.py"
)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Unitree29DofVelocitySmokeTests(unittest.TestCase):
    def test_history_is_concatenated_term_by_term(self) -> None:
        history = {name: deque(maxlen=2) for name in MODULE.TERM_ORDER}
        for frame in (1, 2):
            MODULE.append_history(history, {name: [frame] for name in MODULE.TERM_ORDER})
        self.assertEqual(MODULE.flatten_history(history), [1.0, 2.0] * len(MODULE.TERM_ORDER))

    def test_rejects_fallen_29dof_rollout(self) -> None:
        verdict = MODULE.evaluate(
            {"finite": True, "minimum_height_m": 0.1, "forward_distance_m": 2.0, "physics_steps": 5000},
            minimum_height=0.65,
            minimum_distance=1.0,
        )
        self.assertFalse(verdict["passed"])

    def test_vla_overlay_uses_production_projector_and_is_evidence_gated(self) -> None:
        source = (ROOT / "simulation/run_unitree_29dof_velocity_smoke.py").read_text()
        self.assertIn("G1VLAActionProjector", source)
        self.assertIn('verdict["checks"]["vla_overlay_applied"]', source)
        self.assertIn('"maximum_vla_joint_delta_rad"', source)


if __name__ == "__main__":
    unittest.main()
