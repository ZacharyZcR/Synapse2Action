import unittest

from synapse2action.navigation import BaseVelocity, DEFAULT_NAVIGATION_SCENARIO, Pose2D
from synapse2action.robot_http import EmbeddedRobotServer, HTTPRobotTransport
from synapse2action.robot_transport import (
    LoopbackRobotTransport,
    ObservationRequest,
    decode_command_receipt,
    encode_base_command,
)
from synapse2action.ros2_bridge import (
    ImageMessage,
    LoopbackROS2Runtime,
    ObstacleArrayMessage,
    OdometryMessage,
    ROS2RobotTransport,
    TwistMessage,
)
from synapse2action.vla import run_vla_navigation_demo


class ROS2BridgeTests(unittest.TestCase):
    def test_base_velocity_maps_to_twist_axes(self) -> None:
        runtime = LoopbackROS2Runtime(LoopbackRobotTransport(Pose2D(0.0, 0.0)))
        transport = ROS2RobotTransport(runtime)

        receipt = decode_command_receipt(
            transport.exchange(
                encode_base_command(4, BaseVelocity(0.4, -0.2, 0.3, 100), 500)
            ),
            4,
        )

        self.assertTrue(receipt.accepted)
        self.assertEqual(
            runtime.published_twists,
            [TwistMessage(linear_x=0.4, linear_y=-0.2, angular_z=0.3)],
        )
        self.assertEqual(receipt.started_at_ms, 500)
        self.assertEqual(receipt.completed_at_ms, 600)

    def test_vla_navigation_runs_through_ros2_mapping(self) -> None:
        scenario = DEFAULT_NAVIGATION_SCENARIO
        loopback = LoopbackRobotTransport(
            scenario.start,
            scenario.obstacles,
            robot_radius_m=scenario.robot_radius_m,
            sensor_range_m=scenario.sensor_range_m,
        )
        runtime = LoopbackROS2Runtime(loopback)

        report = run_vla_navigation_demo(
            scenario=scenario,
            transport=ROS2RobotTransport(runtime),
        )

        self.assertTrue(report["passed"])
        self.assertEqual(report["robot_transport"], "ros2")
        self.assertEqual(report["transport_observations"], 45)
        self.assertEqual(report["transport_commands"], 44)
        self.assertEqual(report["transport_halts"], 1)
        self.assertEqual(len(runtime.published_twists), 45)
        self.assertNotEqual(runtime.published_twists[0], TwistMessage())
        self.assertEqual(runtime.published_twists[-1], TwistMessage())
        self.assertEqual(runtime.zero_twist_count, 1)
        self.assertEqual(runtime.emergency_stop_count, 0)
        self.assertEqual(loopback.halt_count, 1)

    def test_sensor_topics_map_to_one_synchronized_observation(self) -> None:
        scenario = DEFAULT_NAVIGATION_SCENARIO
        runtime = LoopbackROS2Runtime(
            LoopbackRobotTransport(scenario.start, scenario.obstacles)
        )
        snapshot = runtime.read_sensor_snapshot(ObservationRequest(3, 700))

        self.assertIsInstance(snapshot.odometry, OdometryMessage)
        self.assertIsInstance(snapshot.image, ImageMessage)
        self.assertIsInstance(snapshot.obstacle_array, ObstacleArrayMessage)
        self.assertEqual(snapshot.captured_at_ms, 700)
        self.assertEqual(snapshot.odometry.pose, scenario.start)
        self.assertEqual(snapshot.obstacle_array.obstacles, scenario.obstacles)
        self.assertGreater(sum(snapshot.image.frame.data), 0)

    def test_stop_maps_to_emergency_stop_and_zero_twist(self) -> None:
        loopback = LoopbackRobotTransport(Pose2D(0.0, 0.0))
        runtime = LoopbackROS2Runtime(loopback)
        transport = ROS2RobotTransport(runtime)

        transport.stop()

        self.assertEqual(runtime.emergency_stop_count, 1)
        self.assertEqual(runtime.published_twists, [TwistMessage()])
        self.assertTrue(loopback.stopped)

    def test_vla_navigation_crosses_http_and_ros2_boundaries(self) -> None:
        scenario = DEFAULT_NAVIGATION_SCENARIO
        runtime = LoopbackROS2Runtime(
            LoopbackRobotTransport(
                scenario.start,
                scenario.obstacles,
                robot_radius_m=scenario.robot_radius_m,
                sensor_range_m=scenario.sensor_range_m,
            )
        )
        with EmbeddedRobotServer(ROS2RobotTransport(runtime)) as server:
            transport = HTTPRobotTransport(server.base_url)

            report = run_vla_navigation_demo(scenario=scenario, transport=transport)

            self.assertTrue(report["passed"])
            self.assertEqual(report["robot_transport"], "http")
            self.assertEqual(len(server.requests), 90)
            self.assertEqual(len(runtime.published_twists), 45)
            self.assertEqual(runtime.published_twists[-1], TwistMessage())
            transport.close()


if __name__ == "__main__":
    unittest.main()
