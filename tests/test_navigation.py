import unittest
from math import hypot

from synapse2action.components import MockPlanner
from synapse2action.contracts import Intent, IntentKind, TaskState
from synapse2action.harness import Harness
from synapse2action.navigation import (
    ActionChunk,
    BaseVelocity,
    NavigationRobot,
    NavigationVerifier,
    NavigationObservation,
    NavigationTask,
    Obstacle2D,
    Pose2D,
    run_navigation_demo,
)


class BlindStraightPolicy:
    def reset(self, task: NavigationTask) -> None:
        pass

    def predict(self, observation: NavigationObservation) -> ActionChunk:
        return ActionChunk((BaseVelocity(0.5, 0.0, 0.0, 100),))


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
        self.assertGreater(report["observed_obstacle_frames"], 1)
        self.assertGreater(max(pose["y"] for pose in report["trajectory"]), 0.3)
        self.assertEqual(report["replan_count"], 1)
        frames = report["sensor_frames"]
        self.assertEqual([frame["frame_id"] for frame in frames], list(range(len(frames))))
        self.assertTrue(all(not frame["visible_obstacles"] for frame in frames if frame["captured_at_ms"] < 600))
        self.assertTrue(all(frame["visible_obstacles"] == ["crate"] for frame in frames if frame["captured_at_ms"] >= 600))
        self.assertEqual([frame["captured_at_ms"] for frame in frames], list(range(0, len(frames) * 100, 100)))
        self.assertTrue(all(frame["instruction"] == "navigate to point_b" for frame in frames))
        self.assertTrue(all(frame["camera"]["encoding"] == "mono8" for frame in frames))
        self.assertTrue(all(frame["camera"]["nonzero_pixels"] == 0 for frame in frames[:6]))
        self.assertGreater(frames[6]["camera"]["nonzero_pixels"], 0)
        self.assertTrue(all(frame["camera"]["nonzero_pixels"] > 0 for frame in frames[23:]))
        self.assertEqual(frames[0]["proprioception"], {"vx": 0.0, "vy": 0.0, "yaw_rate": 0.0})
        self.assertEqual(report["final_proprioception"], {"vx": 0.0, "vy": 0.0, "yaw_rate": 0.0})

    def test_robot_rejects_policy_chunk_that_hits_obstacle(self) -> None:
        goal = Pose2D(2.0, 0.0)
        robot = NavigationRobot(
            Pose2D(0.0, 0.0),
            {"point_b": goal},
            policy=BlindStraightPolicy(),
            obstacles=(Obstacle2D("crate", 1.0, 0.0, 0.25),),
        )
        harness = Harness(
            MockPlanner("navigate_to", {"destination": "point_b"}),
            robot,
            NavigationVerifier(robot, goal),
        )

        harness.handle(Intent(IntentKind.SELECT, "point_b"))
        state = harness.handle(Intent(IntentKind.CONFIRM))

        self.assertEqual(state, TaskState.FAILED)
        self.assertLess(robot.pose.x, 1.0)
        self.assertEqual(robot.base_state.vx, 0.0)


if __name__ == "__main__":
    unittest.main()
