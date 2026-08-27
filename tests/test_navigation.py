import unittest
from math import hypot

from synapse2action.components import MockPlanner
from synapse2action.contracts import Intent, IntentKind, TaskState
from synapse2action.harness import Harness
from synapse2action.navigation import (
    NavigationRobot,
    NavigationVerifier,
    Pose2D,
    run_navigation_demo,
)


class NavigationTests(unittest.TestCase):
    def test_confirmed_navigation_runs_observation_action_loop(self) -> None:
        goal = Pose2D(1.0, 0.5)
        robot = NavigationRobot(Pose2D(0.0, 0.0), {"point_b": goal})
        harness = Harness(
            MockPlanner("navigate_to", {"destination": "point_b"}),
            robot,
            NavigationVerifier(robot, goal),
        )

        harness.handle(Intent(IntentKind.SELECT, "point_b"))
        state = harness.handle(Intent(IntentKind.CONFIRM))

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertGreater(len(robot.chunks), 1)
        self.assertEqual(len(robot.frames), len(robot.chunks) + 1)
        self.assertLessEqual(hypot(robot.pose.x - goal.x, robot.pose.y - goal.y), robot.tolerance_m)

    def test_unknown_destination_fails_without_motion(self) -> None:
        robot = NavigationRobot(Pose2D(0.0, 0.0), {})
        harness = Harness(
            MockPlanner("navigate_to", {"destination": "point_b"}),
            robot,
            NavigationVerifier(robot, Pose2D(1.0, 0.0)),
        )

        harness.handle(Intent(IntentKind.SELECT, "point_b"))
        state = harness.handle(Intent(IntentKind.CONFIRM))

        self.assertEqual(state, TaskState.FAILED)
        self.assertEqual(robot.chunks, [])

    def test_demo_reaches_point_b(self) -> None:
        report = run_navigation_demo()

        self.assertTrue(report["passed"])
        self.assertEqual(report["final_state"], "completed")
        self.assertGreater(report["control_cycles"], 1)


if __name__ == "__main__":
    unittest.main()
