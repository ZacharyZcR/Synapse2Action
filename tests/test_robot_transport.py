import json
import unittest

from synapse2action.navigation import (
    BaseVelocity,
    DEFAULT_NAVIGATION_SCENARIO,
    NavigationScenario,
    Obstacle2D,
    Pose2D,
)
from synapse2action.robot_transport import (
    LoopbackRobotTransport,
    decode_command_receipt,
    decode_sensor_frame,
    encode_base_command,
    encode_observation_request,
)
from synapse2action.vla import run_vla_navigation_demo


class RobotTransportTests(unittest.TestCase):
    def test_loopback_exchanges_serialized_command_and_feedback(self) -> None:
        transport = LoopbackRobotTransport(Pose2D(0.0, 0.0))

        response = transport.exchange(
            encode_base_command(7, BaseVelocity(0.5, -0.25, 0.1, 200), 300)
        )
        receipt = decode_command_receipt(response, 7)

        self.assertTrue(receipt.accepted)
        self.assertEqual(receipt.completed_at_ms, 500)
        self.assertAlmostEqual(receipt.pose.x, 0.1)
        self.assertAlmostEqual(receipt.pose.y, -0.05)
        self.assertAlmostEqual(receipt.pose.yaw, 0.02)
        self.assertEqual(transport.request_count, 1)

    def test_feedback_sequence_mismatch_is_rejected(self) -> None:
        transport = LoopbackRobotTransport(Pose2D(0.0, 0.0))
        response = transport.exchange(
            encode_base_command(3, BaseVelocity(0.1, 0.0, 0.0, 100), 0)
        )

        with self.assertRaisesRegex(ValueError, "sequence mismatch"):
            decode_command_receipt(response, 4)

    def test_loopback_returns_serialized_multimodal_observation(self) -> None:
        obstacle = Obstacle2D("crate", 0.5, 0.0, 0.1)
        transport = LoopbackRobotTransport(Pose2D(0.0, 0.0), obstacles=(obstacle,))

        frame = decode_sensor_frame(
            transport.exchange(encode_observation_request(9, 700)),
            9,
        )

        self.assertEqual(frame.frame_id, 9)
        self.assertEqual(frame.captured_at_ms, 700)
        self.assertEqual(frame.pose, transport.pose)
        self.assertEqual(frame.obstacles, (obstacle,))
        self.assertEqual(frame.camera.encoding, "mono8")
        self.assertGreater(sum(pixel != 0 for pixel in frame.camera.data), 0)
        self.assertEqual(frame.proprioception, transport.base_state)
        self.assertEqual(transport.observation_request_count, 1)

    def test_loopback_rejects_collision_without_advancing_pose(self) -> None:
        start = Pose2D(0.0, 0.0)
        transport = LoopbackRobotTransport(
            start,
            obstacles=(Obstacle2D("crate", 0.2, 0.0, 0.1),),
            robot_radius_m=0.1,
        )

        receipt = decode_command_receipt(
            transport.exchange(
                encode_base_command(0, BaseVelocity(0.5, 0.0, 0.0, 100), 0)
            ),
            0,
        )

        self.assertFalse(receipt.accepted)
        self.assertEqual(receipt.detail, "command intersects obstacle")
        self.assertEqual(receipt.pose, start)
        self.assertEqual(transport.pose, start)

    def test_vla_navigation_reaches_goal_through_loopback_transport(self) -> None:
        scenario = DEFAULT_NAVIGATION_SCENARIO
        transport = LoopbackRobotTransport(
            scenario.start,
            scenario.obstacles,
            scenario.robot_radius_m,
        )

        report = run_vla_navigation_demo(scenario=scenario, transport=transport)

        self.assertTrue(report["passed"])
        self.assertEqual(report["robot_transport"], "loopback")
        self.assertEqual(report["transport_commands"], report["executed_commands"])
        self.assertEqual(transport.command_request_count, report["transport_commands"])
        self.assertEqual(report["transport_observations"], report["observations"])
        self.assertEqual(
            transport.request_count,
            report["transport_commands"] + report["transport_observations"],
        )
        self.assertEqual(report["transport_halts"], 1)
        self.assertEqual(transport.base_state.vx, 0.0)
        self.assertEqual(
            [feedback["sequence"] for feedback in report["transport_feedback"]],
            list(range(report["transport_commands"])),
        )
        self.assertTrue(all(feedback["accepted"] for feedback in report["transport_feedback"]))

    def test_driver_observation_is_authoritative_for_vla(self) -> None:
        scenario = NavigationScenario(
            "driver_owned_world",
            "point_b",
            Pose2D(0.0, 0.0),
            Pose2D(1.0, 0.0),
            obstacles=(),
        )
        transport = LoopbackRobotTransport(
            scenario.start,
            obstacles=(Obstacle2D("driver_crate", 0.5, 0.0, 0.1),),
        )

        report = run_vla_navigation_demo(scenario=scenario, transport=transport)

        self.assertTrue(report["passed"])
        self.assertEqual(report["obstacles"], [])
        self.assertGreater(report["observed_obstacle_frames"], 0)
        self.assertIn(
            "driver_crate",
            {
                obstacle
                for frame in report["sensor_frames"]
                for obstacle in frame["visible_obstacles"]
            },
        )
        self.assertGreater(max(pose["y"] for pose in report["trajectory"]), 0.1)

    def test_transport_rejects_unknown_wire_operation(self) -> None:
        transport = LoopbackRobotTransport(Pose2D(0.0, 0.0))

        with self.assertRaisesRegex(ValueError, "unsupported robot command"):
            transport.exchange(json.dumps({"schema_version": 1, "operation": "arm"}).encode())


if __name__ == "__main__":
    unittest.main()
