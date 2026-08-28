from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2
import threading
import time
from typing import Any, Callable, Protocol

from .navigation import BaseState, CameraFrame, Obstacle2D, Pose2D
from .robot_transport import CommandReceipt, ObservationRequest
from .ros2_bridge import (
    ImageMessage,
    ObstacleArrayMessage,
    OdometryMessage,
    ROS2SensorSnapshot,
    TwistMessage,
)


@dataclass(frozen=True, slots=True)
class ROS2TopicConfig:
    odometry: str = "/odom"
    camera: str = "/camera/image_raw"
    obstacles: str = "/obstacles"
    command_velocity: str = "/cmd_vel"
    emergency_stop: str = "/emergency_stop"
    qos_depth: int = 10
    max_sensor_skew_ms: int = 100


@dataclass(frozen=True, slots=True)
class RclpyMessageTypes:
    twist: type
    boolean: type
    odometry: type
    image: type
    marker_array: type


class Publisher(Protocol):
    def publish(self, message: object) -> None: ...


class Node(Protocol):
    def create_publisher(self, message_type: type, topic: str, qos_depth: int) -> Publisher: ...

    def create_subscription(
        self,
        message_type: type,
        topic: str,
        callback: Callable[[object], None],
        qos_depth: int,
    ) -> object: ...


@dataclass(slots=True)
class RclpyROS2Runtime:
    node: Node
    message_types: RclpyMessageTypes
    topics: ROS2TopicConfig = field(default_factory=ROS2TopicConfig)
    sleep: Callable[[float], None] = time.sleep
    published_twists: list[TwistMessage] = field(default_factory=list, init=False)
    zero_twist_count: int = field(default=0, init=False)
    emergency_stop_count: int = field(default=0, init=False)
    _command_publisher: Publisher = field(init=False, repr=False)
    _stop_publisher: Publisher = field(init=False, repr=False)
    _subscriptions: tuple[object, ...] = field(init=False, repr=False)
    _odometry: tuple[int, OdometryMessage] | None = field(default=None, init=False, repr=False)
    _image: tuple[int, ImageMessage] | None = field(default=None, init=False, repr=False)
    _obstacles: tuple[int, ObstacleArrayMessage] | None = field(default=None, init=False, repr=False)
    _stamp_origin_ms: int | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        qos = self.topics.qos_depth
        types = self.message_types
        self._command_publisher = self.node.create_publisher(
            types.twist,
            self.topics.command_velocity,
            qos,
        )
        self._stop_publisher = self.node.create_publisher(
            types.boolean,
            self.topics.emergency_stop,
            qos,
        )
        self._subscriptions = (
            self.node.create_subscription(types.odometry, self.topics.odometry, self._on_odometry, qos),
            self.node.create_subscription(types.image, self.topics.camera, self._on_image, qos),
            self.node.create_subscription(
                types.marker_array,
                self.topics.obstacles,
                self._on_obstacles,
                qos,
            ),
        )

    def read_sensor_snapshot(self, request: ObservationRequest) -> ROS2SensorSnapshot:
        with self._lock:
            if self._odometry is None or self._image is None or self._obstacles is None:
                raise ValueError("ROS2 sensor snapshot is incomplete")
            samples = (self._odometry, self._image, self._obstacles)
            stamps = [sample[0] for sample in samples]
            if max(stamps) - min(stamps) > self.topics.max_sensor_skew_ms:
                raise ValueError("ROS2 sensor snapshot exceeds maximum skew")
            captured_at_ms = max(stamps)
            return ROS2SensorSnapshot(
                captured_at_ms,
                max(request.captured_at_ms, captured_at_ms),
                self._odometry[1],
                self._image[1],
                self._obstacles[1],
            )

    def publish_twist(
        self,
        sequence: int,
        message: TwistMessage,
        duration_ms: int,
        issued_at_ms: int,
    ) -> CommandReceipt:
        self._publish_twist(message)
        self.sleep(duration_ms / 1000)
        self._publish_zero_twist()
        with self._lock:
            if self._odometry is None:
                raise ValueError("ROS2 odometry is unavailable")
            pose = self._odometry[1].pose
        return CommandReceipt(
            sequence,
            True,
            "ROS2 Twist completed",
            issued_at_ms,
            issued_at_ms + duration_ms,
            pose,
            BaseState(),
        )

    def publish_zero_twist(self) -> None:
        self._publish_zero_twist()

    def emergency_stop(self) -> None:
        self._publish_zero_twist()
        message = self.message_types.boolean()
        message.data = True
        self._stop_publisher.publish(message)
        self.emergency_stop_count += 1

    def _publish_twist(self, command: TwistMessage) -> None:
        message = self.message_types.twist()
        message.linear.x = command.linear_x
        message.linear.y = command.linear_y
        message.linear.z = command.linear_z
        message.angular.x = command.angular_x
        message.angular.y = command.angular_y
        message.angular.z = command.angular_z
        self._command_publisher.publish(message)
        self.published_twists.append(command)

    def _publish_zero_twist(self) -> None:
        self._publish_twist(TwistMessage())
        self.zero_twist_count += 1

    def _on_odometry(self, message: object) -> None:
        stamp = self._relative_stamp_ms(message.header.stamp)
        pose = message.pose.pose
        twist = message.twist.twist
        orientation = pose.orientation
        yaw = atan2(
            2 * (orientation.w * orientation.z + orientation.x * orientation.y),
            1 - 2 * (orientation.y**2 + orientation.z**2),
        )
        converted = OdometryMessage(
            Pose2D(pose.position.x, pose.position.y, yaw),
            BaseState(twist.linear.x, twist.linear.y, twist.angular.z),
        )
        with self._lock:
            self._odometry = (stamp, converted)

    def _on_image(self, message: object) -> None:
        stamp = self._relative_stamp_ms(message.header.stamp)
        converted = ImageMessage(
            CameraFrame(message.width, message.height, message.encoding, bytes(message.data))
        )
        with self._lock:
            self._image = (stamp, converted)

    def _on_obstacles(self, message: object) -> None:
        markers = tuple(message.markers)
        if markers:
            stamp = self._relative_raw_stamp_ms(
                max(_stamp_ms(marker.header.stamp) for marker in markers)
            )
        else:
            with self._lock:
                stamp = max(
                    self._odometry[0] if self._odometry else 0,
                    self._image[0] if self._image else 0,
                )
        converted = ObstacleArrayMessage(
            tuple(
                Obstacle2D(
                    f"{marker.ns}:{marker.id}" if marker.ns else str(marker.id),
                    marker.pose.position.x,
                    marker.pose.position.y,
                    max(marker.scale.x, marker.scale.y) / 2,
                )
                for marker in markers
            )
        )
        with self._lock:
            self._obstacles = (stamp, converted)

    def _relative_stamp_ms(self, stamp: object) -> int:
        return self._relative_raw_stamp_ms(_stamp_ms(stamp))

    def _relative_raw_stamp_ms(self, raw_stamp_ms: int) -> int:
        with self._lock:
            if self._stamp_origin_ms is None:
                self._stamp_origin_ms = raw_stamp_ms
            return raw_stamp_ms - self._stamp_origin_ms


def create_rclpy_runtime(
    node: Node,
    topics: ROS2TopicConfig | None = None,
) -> RclpyROS2Runtime:
    try:
        from geometry_msgs.msg import Twist
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import Image
        from std_msgs.msg import Bool
        from visualization_msgs.msg import MarkerArray
    except ImportError as exc:
        raise RuntimeError("rclpy ROS2 message packages are not installed") from exc
    return RclpyROS2Runtime(
        node,
        RclpyMessageTypes(Twist, Bool, Odometry, Image, MarkerArray),
        topics or ROS2TopicConfig(),
    )


def _stamp_ms(stamp: Any) -> int:
    return int(stamp.sec) * 1000 + int(stamp.nanosec) // 1_000_000
