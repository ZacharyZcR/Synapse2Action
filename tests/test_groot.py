import json
from pathlib import Path
import tempfile
import unittest

from synapse2action.contracts import Action, ExecutionResult
from synapse2action.groot import GrootPolicy
from synapse2action.task_spec import load_task_spec
from synapse2action.unitree_simulation import GrootPickPlaceSimulationRobot, GrootPickPlaceVerifier


ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "experiments" / "tasks" / "g1_groot_apple_to_plate.json"


class GrootPolicyTests(unittest.TestCase):
    def test_policy_binds_validated_plan_to_groot_steps(self) -> None:
        task = load_task_spec(TASK_PATH)
        prepared = GrootPolicy(task).prepare(Action(task.skill, task.arguments))
        self.assertEqual(
            prepared.steps,
            ("groot_vla", "whole_body_control", "strict_physical_verification"),
        )

    def test_policy_rejects_task_not_supported_by_checkpoint(self) -> None:
        task = load_task_spec(TASK_PATH)
        with self.assertRaises(ValueError):
            GrootPolicy(task).prepare(
                Action("pick_and_place", {"target": "red_cube", "destination": "plate"})
            )

    def test_contact_only_result_fails_strict_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_dir = Path(directory)
            (report_dir / "g1-groot-closed-loop-acceptance.json").write_text(
                json.dumps({"accepted": True})
            )
            (report_dir / "g1-groot-closed-loop.json").write_text(
                json.dumps(
                    {
                        "official_contact_success": True,
                        "grasped": None,
                        "lifted": None,
                        "released": None,
                        "stable_on_target": None,
                        "remained_standing": None,
                    }
                )
            )

            def run(*args, **kwargs):
                from subprocess import CompletedProcess

                return CompletedProcess(args[0], 0, "", "")

            robot = GrootPickPlaceSimulationRobot(
                ROOT / "simulation" / "run_groot_g1_pick_place.py",
                report_dir,
                task_spec_path=TASK_PATH,
                run=run,
            )
            result = robot.execute(Action("pick_and_place", {"target": "apple", "destination": "plate"}))

            self.assertTrue(result.success)
            self.assertFalse(GrootPickPlaceVerifier(robot).verify(result))

    def test_strict_verification_requires_all_physical_evidence(self) -> None:
        robot = GrootPickPlaceSimulationRobot(
            ROOT / "simulation" / "run_groot_g1_pick_place.py",
            ROOT / "reports" / "simulation",
            task_spec_path=TASK_PATH,
        )
        robot.last_simulator_report = {
            "official_contact_success": True,
            "grasped": True,
            "lifted": True,
            "released": True,
            "stable_on_target": True,
            "remained_standing": True,
        }
        self.assertTrue(GrootPickPlaceVerifier(robot).verify(ExecutionResult(True, "ok")))


if __name__ == "__main__":
    unittest.main()
