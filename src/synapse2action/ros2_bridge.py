from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Protocol

from .navigation import BaseState, BaseVelocity, CameraFrame, Obstacle2D, Pose2D, SensorFrame
from .robot_transport import (
    BaseCommandRequest,
    CommandReceipt,
    LoopbackRobotTransport,
    ObservationRequest,
    SensorPacket,
    decode_base_command,
    decode_command_receipt,
    decode_observation_request,
    decode_sensor_packet,
    encode_base_command,
    encode_command_receipt,
    encode_observation_request,
    encode_sensor_packet,
)


@dataclass(frozen=True, slots=True)
class TwistMessage:
    linear_x: float = 0.0
    linear_y: float = 0.0
    linear_z: float = 0.0
    angular_x: float = 0.0
    angular_y: float = 0.0
    angular_z: float = 0.0


@dataclass(frozen=True, slots=True)
class OdometryMessage:
    pose: Pose2D
    twist: BaseState


@dataclass(frozen=True, slots=True)
class ImageMessage:
    frame: CameraFrame


@dataclass(frozen=True, slots=True)
class ObstacleArrayMessage:
    obstacles: tuple[Obstacle2D, ...]


@dataclass(frozen=True, slots=True)
class ROS2SensorSnapshot:
    captured_at_ms: int
    available_at_ms: int
    odometry: OdometryMessage
    image: ImageMessage
    obstacle_array: ObstacleArrayMessage


class ROS2Runtime(Protocol):
    def read_sensor_snapshot(self, request: ObservationRequest) -> ROS2SensorSnapshot: ...

    def publish_twist(
        self,
        sequence: int,
        message: TwistMessage,
        duration_ms: int,
        issued_at_ms: int,
    ) -> CommandReceipt: ...

    def publish_zero_twist(self) -> None: ...

    def emergency_stop(self) -> None: ...


@dataclass(slots=True)
class ROS2RobotTransport:
    runtime: ROS2Runtime
    name: str = "ros2"
    command_request_count: int = 0
    observation_request_count: int = 0
    halt_count: int = 0

    @property
    def request_count(self) -> int:
        return self.command_request_count + self.observation_request_count

    @property
    def sensor_latency_ms(self) -> int:
        return getattr(self.runtime, "sensor_latency_ms", 0)

    @property
    def command_latency_ms(self) -> int:
        return getattr(self.runtime, "command_latency_ms", 0)

    def exchange(self, request: bytes) -> bytes:
        payload = json.loads(request)
        operation = payload.get("operation") if isinstance(payload, dict) else None
        if operation == "observe":
            self.observation_request_count += 1
            observation = decode_observation_request(request)
            snapshot = self.runtime.read_sensor_snapshot(observation)
            return encode_sensor_packet(
                SensorPacket(
                    SensorFrame(
                        observation.frame_id,
                        snapshot.captured_at_ms,
                        snapshot.odometry.pose,
                        snapshot.obstacle_array.obstacles,
                        snapshot.image.frame,
                        snapshot.odometry.twist,
                    ),
                    snapshot.available_at_ms,
                )
            )
        if operation != "base_velocity":
            raise ValueError("unsupported ROS2 robot operation")
        self.command_request_count += 1
        return encode_command_receipt(self._publish(decode_base_command(request)))

    def _publish(self, request: BaseCommandRequest) -> CommandReceipt:
        command = request.command
        return self.runtime.publish_twist(
            request.sequence,
            TwistMessage(
                linear_x=command.vx,
                linear_y=command.vy,
                angular_z=command.yaw_rate,
            ),
            command.duration_ms,
            request.issued_at_ms,
        )

    def halt(self) -> None:
        self.runtime.publish_zero_twist()
        self.halt_count += 1

    def stop(self) -> None:
        self.runtime.emergency_stop()


@dataclass(slots=True)
class LoopbackROS2Runtime:
    bridge: LoopbackRobotTransport
    published_twists: list[TwistMessage] = field(default_factory=list)
    zero_twist_count: int = 0
    emergency_stop_count: int = 0

    @property
    def sensor_latency_ms(self) -> int:
        return self.bridge.sensor_latency_ms

    @property
    def command_latency_ms(self) -> int:
        return self.bridge.command_latency_ms

    def read_sensor_snapshot(self, request: ObservationRequest) -> ROS2SensorSnapshot:
        packet = decode_sensor_packet(
            self.bridge.exchange(
                encode_observation_request(request.frame_id, request.captured_at_ms)
            ),
            request.frame_id,
        )
        frame = packet.frame
        return ROS2SensorSnapshot(
            frame.captured_at_ms,
            packet.available_at_ms,
            OdometryMessage(frame.pose, frame.proprioception),
            ImageMessage(frame.camera),
            ObstacleArrayMessage(frame.obstacles),
        )

    def publish_twist(
        self,
        sequence: int,
        message: TwistMessage,
        duration_ms: int,
        issued_at_ms: int,
    ) -> CommandReceipt:
        self.published_twists.append(message)
        return decode_command_receipt(
            self.bridge.exchange(
                encode_base_command(
                    sequence,
                    BaseVelocity(
                        message.linear_x,
                        message.linear_y,
                        message.angular_z,
                        duration_ms,
                    ),
                    issued_at_ms,
                )
            ),
            sequence,
        )

    def publish_zero_twist(self) -> None:
        self.published_twists.append(TwistMessage())
        self.zero_twist_count += 1
        self.bridge.halt()

    def emergency_stop(self) -> None:
        self.published_twists.append(TwistMessage())
        self.emergency_stop_count += 1
        self.bridge.stop()
