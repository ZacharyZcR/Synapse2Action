from types import SimpleNamespace
import unittest

from synapse2action.rclpy_runtime import (
    RclpyMessageTypes,
    RclpyROS2Runtime,
    ROS2TopicConfig,
)
from synapse2action.robot_transport import ObservationRequest
from synapse2action.ros2_bridge import TwistMessage


class Twist:
    def __init__(self) -> None:
        self.linear = SimpleNamespace(x=0.0, y=0.0, z=0.0)
        self.angular = SimpleNamespace(x=0.0, y=0.0, z=0.0)


class Bool:
    def __init__(self) -> None:
        self.data = False


class Odometry:
    pass


class Image:
    pass


class MarkerArray:
    pass


class FakePublisher:
    def __init__(self) -> None:
        self.messages = []

    def publish(self, message) -> None:
        self.messages.append(message)


class FakeNode:
    def __init__(self) -> None:
        self.publishers = {}
        self.subscriptions = {}

    def create_publisher(self, message_type, topic, qos_depth):
        publisher = FakePublisher()
        self.publishers[topic] = (message_type, qos_depth, publisher)
        return publisher

    def create_subscription(self, message_type, topic, callback, qos_depth):
        subscription = (message_type, callback, qos_depth)
        self.subscriptions[topic] = subscription
        return subscription

    def emit(self, topic, message) -> None:
        self.subscriptions[topic][1](message)


def stamp(milliseconds: int):
    return SimpleNamespace(sec=milliseconds // 1000, nanosec=(milliseconds % 1000) * 1_000_000)


def odometry_message(milliseconds: int):
    return SimpleNamespace(
        header=SimpleNamespace(stamp=stamp(milliseconds)),
        pose=SimpleNamespace(
            pose=SimpleNamespace(
                position=SimpleNamespace(x=1.0, y=2.0),
                orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0),
            )
        ),
        twist=SimpleNamespace(
            twist=SimpleNamespace(
                linear=SimpleNamespace(x=0.2, y=-0.1),
                angular=SimpleNamespace(z=0.3),
            )
        ),
    )


def image_message(milliseconds: int):
    return SimpleNamespace(
        header=SimpleNamespace(stamp=stamp(milliseconds)),
        width=2,
        height=2,
        encoding="mono8",
        data=bytes((0, 255, 0, 0)),
    )


def marker_array_message(milliseconds: int):
    marker = SimpleNamespace(
        header=SimpleNamespace(stamp=stamp(milliseconds)),
        ns="world",
        id=7,
        pose=SimpleNamespace(position=SimpleNamespace(x=0.5, y=0.25)),
        scale=SimpleNamespace(x=0.4, y=0.2),
    )
    return SimpleNamespace(markers=[marker])


class RclpyRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.node = FakeNode()
        self.sleeps = []
        self.runtime = RclpyROS2Runtime(
            self.node,
            RclpyMessageTypes(Twist, Bool, Odometry, Image, MarkerArray),
            sleep=self.sleeps.append,
        )

    def emit_sensor_snapshot(self) -> None:
        self.node.emit("/odom", odometry_message(10_000))
        self.node.emit("/camera/image_raw", image_message(10_020))
        self.node.emit("/obstacles", marker_array_message(10_010))

    def test_subscriptions_form_synchronized_sensor_snapshot(self) -> None:
        self.emit_sensor_snapshot()

        snapshot = self.runtime.read_sensor_snapshot(ObservationRequest(2, 50))

        self.assertEqual(set(self.node.subscriptions), {"/odom", "/camera/image_raw", "/obstacles"})
        self.assertEqual(snapshot.captured_at_ms, 20)
        self.assertEqual(snapshot.available_at_ms, 50)
        self.assertEqual((snapshot.odometry.pose.x, snapshot.odometry.pose.y), (1.0, 2.0))
        self.assertEqual(snapshot.odometry.twist.vx, 0.2)
        self.assertEqual(snapshot.image.frame.data, bytes((0, 255, 0, 0)))
        obstacle = snapshot.obstacle_array.obstacles[0]
        self.assertEqual((obstacle.obstacle_id, obstacle.x, obstacle.y), ("world:7", 0.5, 0.25))
        self.assertEqual(obstacle.radius, 0.2)

    def test_publish_twist_waits_then_publishes_zero_and_ack(self) -> None:
        self.emit_sensor_snapshot()

        receipt = self.runtime.publish_twist(
            3,
            TwistMessage(linear_x=0.4, linear_y=-0.2, angular_z=0.3),
            100,
            500,
        )

        publisher = self.node.publishers["/cmd_vel"][2]
        self.assertEqual(self.sleeps, [0.1])
        self.assertEqual(len(publisher.messages), 2)
        self.assertEqual(publisher.messages[0].linear.x, 0.4)
        self.assertEqual(publisher.messages[0].linear.y, -0.2)
        self.assertEqual(publisher.messages[0].angular.z, 0.3)
        self.assertEqual(publisher.messages[1].linear.x, 0.0)
        self.assertEqual(receipt.completed_at_ms, 600)
        self.assertEqual((receipt.pose.x, receipt.pose.y), (1.0, 2.0))
        self.assertEqual(self.runtime.zero_twist_count, 1)

    def test_halt_and_emergency_stop_publish_expected_messages(self) -> None:
        self.runtime.publish_zero_twist()
        self.runtime.emergency_stop()

        command_publisher = self.node.publishers["/cmd_vel"][2]
        stop_publisher = self.node.publishers["/emergency_stop"][2]
        self.assertEqual(len(command_publisher.messages), 2)
        self.assertTrue(stop_publisher.messages[0].data)
        self.assertEqual(self.runtime.zero_twist_count, 2)
        self.assertEqual(self.runtime.emergency_stop_count, 1)

    def test_custom_topics_are_used(self) -> None:
        node = FakeNode()
        topics = ROS2TopicConfig(
            odometry="/robot/odom",
            camera="/front/image",
            obstacles="/perception/obstacles",
            command_velocity="/robot/cmd_vel",
            emergency_stop="/robot/estop",
        )

        RclpyROS2Runtime(
            node,
            RclpyMessageTypes(Twist, Bool, Odometry, Image, MarkerArray),
            topics,
            sleep=lambda _: None,
        )

        self.assertEqual(
            set(node.subscriptions),
            {"/robot/odom", "/front/image", "/perception/obstacles"},
        )
        self.assertEqual(set(node.publishers), {"/robot/cmd_vel", "/robot/estop"})


if __name__ == "__main__":
    unittest.main()
