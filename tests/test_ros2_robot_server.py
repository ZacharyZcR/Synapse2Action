from contextlib import redirect_stderr
from io import StringIO
from types import ModuleType
import sys
import unittest
from unittest.mock import patch

from synapse2action.ros2_robot_server import main


class Message:
    pass


class FakePublisher:
    def publish(self, message) -> None:
        pass


class FakeLogger:
    def __init__(self) -> None:
        self.messages = []

    def info(self, message) -> None:
        self.messages.append(message)


class FakeNode:
    def __init__(self) -> None:
        self.logger = FakeLogger()
        self.destroyed = False

    def create_publisher(self, message_type, topic, qos_depth):
        return FakePublisher()

    def create_subscription(self, message_type, topic, callback, qos_depth):
        return (message_type, topic, callback, qos_depth)

    def get_logger(self):
        return self.logger

    def destroy_node(self) -> None:
        self.destroyed = True


class FakeServer:
    instances = []

    def __init__(self, bridge, host, port) -> None:
        self.bridge = bridge
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}/v1"
        self.started = False
        self.closed = False
        self.instances.append(self)

    def start(self) -> None:
        self.started = True

    def close(self) -> None:
        self.closed = True


def module(name: str, **attributes: object) -> ModuleType:
    value = ModuleType(name)
    for key, attribute in attributes.items():
        setattr(value, key, attribute)
    return value


class ROS2RobotServerTests(unittest.TestCase):
    def test_standalone_server_initializes_spins_and_closes_ros2(self) -> None:
        node = FakeNode()
        calls = []
        fake_rclpy = module(
            "rclpy",
            init=lambda args=None: calls.append(("init", args)),
            create_node=lambda name: calls.append(("create_node", name)) or node,
            spin=lambda active_node: calls.append(("spin", active_node)),
            shutdown=lambda: calls.append(("shutdown", None)),
        )
        modules = {
            "rclpy": fake_rclpy,
            "geometry_msgs": module("geometry_msgs"),
            "geometry_msgs.msg": module("geometry_msgs.msg", Twist=Message),
            "nav_msgs": module("nav_msgs"),
            "nav_msgs.msg": module("nav_msgs.msg", Odometry=Message),
            "sensor_msgs": module("sensor_msgs"),
            "sensor_msgs.msg": module("sensor_msgs.msg", Image=Message),
            "std_msgs": module("std_msgs"),
            "std_msgs.msg": module("std_msgs.msg", Bool=Message),
            "visualization_msgs": module("visualization_msgs"),
            "visualization_msgs.msg": module("visualization_msgs.msg", MarkerArray=Message),
        }
        FakeServer.instances.clear()

        with patch.dict(sys.modules, modules), patch(
            "synapse2action.ros2_robot_server.EmbeddedRobotServer",
            FakeServer,
        ):
            result = main(["--host", "127.0.0.1", "--port", "9200"])

        server = FakeServer.instances[0]
        self.assertEqual(result, 0)
        self.assertTrue(server.started)
        self.assertTrue(server.closed)
        self.assertEqual((server.host, server.port), ("127.0.0.1", 9200))
        self.assertEqual(calls[0], ("init", None))
        self.assertEqual(calls[1], ("create_node", "synapse2action_robot_bridge"))
        self.assertEqual(calls[2], ("spin", node))
        self.assertEqual(calls[3], ("shutdown", None))
        self.assertTrue(node.destroyed)
        self.assertEqual(node.logger.messages, ["robot bridge listening on http://127.0.0.1:9200/v1"])

    def test_invalid_server_configuration_is_rejected_before_ros_import(self) -> None:
        for arguments in (["--port", "0"], ["--qos-depth", "0"], ["--max-sensor-skew-ms", "-1"]):
            with self.subTest(arguments=arguments), redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit):
                    main(arguments)


if __name__ == "__main__":
    unittest.main()
