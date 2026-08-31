from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location(
    "run_unitree_locomotion_smoke", ROOT / "simulation/run_unitree_locomotion_smoke.py"
)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class UnitreeLocomotionSmokeTests(unittest.TestCase):
    def test_runner_supports_same_rollout_video_evidence(self) -> None:
        source = (ROOT / "simulation/run_unitree_locomotion_smoke.py").read_text()
        self.assertIn('parser.add_argument("--video"', source)
        self.assertIn('"video_frames": video_frames', source)
        self.assertIn("if video_path:", source)

    def test_labels_29dof_path_as_negative_transfer_experiment(self) -> None:
        source = (ROOT / "simulation/run_unitree_locomotion_smoke.py").read_text()
        self.assertIn("negative transfer experiment", source)
        self.assertIn('"unitree-g1-29dof-static-upper-smoke"', source)

    def test_accepts_stable_finite_walk(self) -> None:
        verdict = MODULE.evaluate(
            {"finite": True, "minimum_height_m": 0.75, "forward_distance_m": 4.0, "physics_steps": 5000},
            minimum_height=0.65,
            minimum_distance=1.0,
        )
        self.assertTrue(verdict["passed"])

    def test_rejects_fsm_success_when_robot_falls(self) -> None:
        verdict = MODULE.evaluate(
            {"finite": True, "minimum_height_m": 0.09, "forward_distance_m": 0.9, "physics_steps": 5000},
            minimum_height=0.65,
            minimum_distance=1.0,
        )
        self.assertFalse(verdict["passed"])
        self.assertFalse(verdict["checks"]["minimum_height"])


if __name__ == "__main__":
    unittest.main()
