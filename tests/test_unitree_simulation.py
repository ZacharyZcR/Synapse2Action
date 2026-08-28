from __future__ import annotations

import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from synapse2action.components import MockPlanner, ScriptedPolicy
from synapse2action.contracts import Action, Intent, IntentKind, TaskState
from synapse2action.harness import Harness
from synapse2action.navigation import Pose2D
from synapse2action.unitree_simulation import (
    NavigateToPlanner,
    UnitreePickPlaceSimulationRobot,
    UnitreePickPlaceVerifier,
    UnitreeSimulationRobot,
    UnitreeSimulationVerifier,
    unitree_pick_place_skill_registry,
)


TASK_SPEC = Path(__file__).resolve().parents[1] / "experiments/tasks/g1_pick_place.json"


class UnitreeSimulationTests(unittest.TestCase):
    def test_confirmed_navigation_crosses_harness_and_real_runner_boundary(self) -> None:
        with TemporaryDirectory() as directory:
            reports = Path(directory)
            calls: list[tuple[str, ...]] = []

            def run(command, **kwargs):
                calls.append(tuple(command))
                (reports / "acceptance.json").write_text(json.dumps({"accepted": True}))
                (reports / "g1-mujoco.json").write_text(
                    json.dumps({"final_position_error_m": 0.04, "final_yaw_error_rad": 0.03})
                )
                return subprocess.CompletedProcess(command, 0, "", "")

            robot = UnitreeSimulationRobot(
                Path("simulation/run_unitree_headless.sh"),
                reports,
                {"point_b": Pose2D(0.8, 0.2, 0.3)},
                run=run,
            )
            harness = Harness(
                NavigateToPlanner(), robot, UnitreeSimulationVerifier(robot), policy=ScriptedPolicy()
            )

            harness.handle(Intent(IntentKind.SELECT, "point_b"))
            state = harness.handle(Intent(IntentKind.CONFIRM))

            self.assertEqual(state, TaskState.COMPLETED)
            self.assertEqual(calls[0], ("simulation/run_unitree_headless.sh", "locomotion", "0.8", "0.2", "0.3"))
            self.assertEqual([record.event for record in harness.trace], [
                "select", "plan", "await_confirmation", "confirm", "policy", "execute", "verify", "result"
            ])

    def test_runner_is_never_called_before_confirmation(self) -> None:
        calls = 0

        def run(command, **kwargs):
            nonlocal calls
            calls += 1
            return subprocess.CompletedProcess(command, 0, "", "")

        robot = UnitreeSimulationRobot(Path("runner"), Path("reports"), {"point_b": Pose2D(1, 0, 0)}, run=run)
        harness = Harness(NavigateToPlanner(), robot, UnitreeSimulationVerifier(robot))

        harness.handle(Intent(IntentKind.SELECT, "point_b"))

        self.assertEqual(calls, 0)
        self.assertEqual(robot.executed, [])

    def test_acceptance_report_cannot_self_report_success_without_pose_evidence(self) -> None:
        with TemporaryDirectory() as directory:
            reports = Path(directory)
            calls: list[tuple[str, ...]] = []

            def run(command, **kwargs):
                calls.append(tuple(command))
                (reports / "acceptance.json").write_text(json.dumps({"accepted": True}))
                (reports / "g1-mujoco.json").write_text(
                    json.dumps({"final_position_error_m": 0.2, "final_yaw_error_rad": 0.0})
                )
                return subprocess.CompletedProcess(command, 0, "", "")

            robot = UnitreeSimulationRobot(Path("runner"), reports, {"point_b": Pose2D(1, 0, 0)}, run=run)
            action = Action("navigate_to", {"destination": "point_b"}, ("closed_loop_navigation",))

            result = robot.execute(action)

            self.assertTrue(result.success)
            self.assertFalse(UnitreeSimulationVerifier(robot).verify(result))

    def test_confirmed_pick_place_uses_physical_report_evidence(self) -> None:
        with TemporaryDirectory() as directory:
            reports = Path(directory)
            calls: list[tuple[str, ...]] = []

            def run(command, **kwargs):
                calls.append(tuple(command))
                (reports / "vla-acceptance.json").write_text(json.dumps({"accepted": True}))
                (reports / "vla.json").write_text(json.dumps({
                    "grasped": True,
                    "released": True,
                    "initial_object_position_xyz_m": [0.15, 0.0, 0.68],
                    "maximum_object_height_m": 0.81,
                    "final_drop_zone_error_m": 0.08,
                    "final_object_center_in_drop_zone": True,
                    "minimum_base_height_m": 0.78,
                }))
                return subprocess.CompletedProcess(command, 0, "", "")

            robot = UnitreePickPlaceSimulationRobot(
                Path("runner"), reports, report_stem="vla", task_spec_path=TASK_SPEC, run=run
            )
            harness = Harness(
                MockPlanner(arguments={"target": "red_cube", "destination": "drop_tray"}),
                robot,
                UnitreePickPlaceVerifier(robot),
                skills=unitree_pick_place_skill_registry(),
            )
            harness.handle(Intent(IntentKind.SELECT, "red_cube"))

            state = harness.handle(Intent(IntentKind.CONFIRM))

            self.assertEqual(state, TaskState.COMPLETED)
            self.assertEqual(len(robot.executed), 1)
            self.assertEqual(
                calls,
                [("runner", str(TASK_SPEC), "planner_action")],
            )

    def test_failed_runner_keeps_physical_report_for_observability(self) -> None:
        with TemporaryDirectory() as directory:
            reports = Path(directory)

            def run(command, **kwargs):
                (reports / "vla-acceptance.json").write_text(json.dumps({"accepted": False}))
                (reports / "vla.json").write_text(json.dumps({"grasped": False}))
                return subprocess.CompletedProcess(command, 1, "", "acceptance failed")

            robot = UnitreePickPlaceSimulationRobot(
                Path("runner"), reports, report_stem="vla", task_spec_path=TASK_SPEC, run=run
            )
            result = robot.execute(
                Action("pick_and_place", {"target": "red_cube", "destination": "drop_tray"})
            )

            self.assertFalse(result.success)
            self.assertEqual(robot.last_acceptance, {"accepted": False})
            self.assertEqual(robot.last_simulator_report, {"grasped": False})


if __name__ == "__main__":
    unittest.main()
