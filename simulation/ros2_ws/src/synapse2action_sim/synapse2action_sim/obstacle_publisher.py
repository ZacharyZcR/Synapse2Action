from __future__ import annotations

import rclpy
from rclpy.node import Node
from visualization_msgs.msg import Marker, MarkerArray


class ObstaclePublisher(Node):
    def __init__(self) -> None:
        super().__init__("synapse2action_obstacles")
        self.publisher = self.create_publisher(MarkerArray, "/obstacles", 10)
        self.timer = self.create_timer(0.1, self.publish_obstacles)

    def publish_obstacles(self) -> None:
        crate = Marker()
        crate.header.frame_id = "odom"
        crate.header.stamp = self.get_clock().now().to_msg()
        crate.ns = "navigation"
        crate.id = 1
        crate.type = Marker.CUBE
        crate.action = Marker.ADD
        crate.pose.position.x = 1.0
        crate.pose.position.y = 0.0
        crate.pose.position.z = 0.25
        crate.pose.orientation.w = 1.0
        crate.scale.x = 0.5
        crate.scale.y = 0.5
        crate.scale.z = 0.5
        crate.color.r = 0.75
        crate.color.g = 0.25
        crate.color.b = 0.1
        crate.color.a = 1.0
        self.publisher.publish(MarkerArray(markers=[crate]))


def main() -> None:
    rclpy.init()
    node = ObstaclePublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
