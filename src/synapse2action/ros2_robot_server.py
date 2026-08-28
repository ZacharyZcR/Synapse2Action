from __future__ import annotations

import argparse
from collections.abc import Sequence

from .rclpy_runtime import ROS2TopicConfig, create_rclpy_runtime
from .robot_http import EmbeddedRobotServer
from .ros2_bridge import ROS2RobotTransport


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Synapse2Action ROS2 robot HTTP bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9100)
    parser.add_argument("--node-name", default="synapse2action_robot_bridge")
    parser.add_argument("--odometry-topic", default="/odom")
    parser.add_argument("--camera-topic", default="/camera/image_raw")
    parser.add_argument("--obstacles-topic", default="/obstacles")
    parser.add_argument("--command-velocity-topic", default="/cmd_vel")
    parser.add_argument("--emergency-stop-topic", default="/emergency_stop")
    parser.add_argument("--qos-depth", type=int, default=10)
    parser.add_argument("--max-sensor-skew-ms", type=int, default=100)
    args = parser.parse_args(argv)
    if not 0 < args.port <= 65535:
        parser.error("--port must be in [1, 65535]")
    if args.qos_depth <= 0:
        parser.error("--qos-depth must be positive")
    if args.max_sensor_skew_ms < 0:
        parser.error("--max-sensor-skew-ms must be non-negative")

    try:
        import rclpy
    except ImportError as exc:
        raise RuntimeError("rclpy is not installed; run this bridge in a ROS2 environment") from exc

    rclpy.init(args=None)
    node = rclpy.create_node(args.node_name)
    topics = ROS2TopicConfig(
        args.odometry_topic,
        args.camera_topic,
        args.obstacles_topic,
        args.command_velocity_topic,
        args.emergency_stop_topic,
        args.qos_depth,
        args.max_sensor_skew_ms,
    )
    server = EmbeddedRobotServer(
        ROS2RobotTransport(create_rclpy_runtime(node, topics)),
        args.host,
        args.port,
    )
    server.start()
    node.get_logger().info(f"robot bridge listening on {server.base_url}")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
