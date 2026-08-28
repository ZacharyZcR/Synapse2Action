from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import asdict, dataclass
import json
from math import hypot
from typing import Protocol

from .navigation import (
    BaseState,
    BaseVelocity,
    CameraFrame,
    Obstacle2D,
    Pose2D,
    SensorFrame,
    render_camera,
)


class RobotTransport(Protocol):
    name: str

    def exchange(self, request: bytes) -> bytes: ...

    def halt(self) -> None: ...

    def stop(self) -> None: ...


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    sequence: int
    accepted: bool
    detail: str
    started_at_ms: int
    completed_at_ms: int
    pose: Pose2D
    base_state: BaseState


@dataclass(frozen=True, slots=True)
class SensorPacket:
    frame: SensorFrame
    available_at_ms: int


@dataclass(frozen=True, slots=True)
class BaseCommandRequest:
    sequence: int
    issued_at_ms: int
    command: BaseVelocity


@dataclass(frozen=True, slots=True)
class ObservationRequest:
    frame_id: int
    captured_at_ms: int


@dataclass(slots=True)
class LoopbackRobotTransport:
    pose: Pose2D
    obstacles: tuple[Obstacle2D, ...] = ()
    robot_radius_m: float = 0.1
    sensor_range_m: float = 3.0
    sensor_latency_ms: int = 0
    command_latency_ms: int = 0
    name: str = "loopback"
    stopped: bool = False
    command_request_count: int = 0
    observation_request_count: int = 0
    halt_count: int = 0
    base_state: BaseState = BaseState()

    def __post_init__(self) -> None:
        if self.sensor_latency_ms < 0 or self.command_latency_ms < 0:
            raise ValueError("robot transport latency must be non-negative")

    @property
    def request_count(self) -> int:
        return self.command_request_count + self.observation_request_count

    def exchange(self, request: bytes) -> bytes:
        payload = json.loads(request)
        if payload.get("schema_version") != 1:
            raise ValueError("unsupported robot command envelope")
        if payload.get("operation") == "observe":
            return self._observe(decode_observation_request(request))
        if payload.get("operation") != "base_velocity":
            raise ValueError("unsupported robot command envelope")
        return self._execute(decode_base_command(request))

    def _execute(self, request: BaseCommandRequest) -> bytes:
        sequence = request.sequence
        issued_at_ms = request.issued_at_ms
        command = request.command
        self.command_request_count += 1
        started_at_ms = issued_at_ms + self.command_latency_ms
        completed_at_ms = started_at_ms + command.duration_ms
        if self.stopped:
            return encode_command_receipt(
                CommandReceipt(
                    sequence,
                    False,
                    "transport is stopped",
                    started_at_ms,
                    completed_at_ms,
                    self.pose,
                    BaseState(),
                )
            )

        seconds = command.duration_ms / 1000
        next_pose = Pose2D(
            self.pose.x + command.vx * seconds,
            self.pose.y + command.vy * seconds,
            self.pose.yaw + command.yaw_rate * seconds,
        )
        collision = any(
            obstacle.active_from_ms <= completed_at_ms
            and (obstacle.active_until_ms is None or completed_at_ms < obstacle.active_until_ms)
            and hypot(next_pose.x - obstacle.x, next_pose.y - obstacle.y)
            < obstacle.radius + self.robot_radius_m
            for obstacle in self.obstacles
        )
        if collision:
            self.base_state = BaseState()
            return encode_command_receipt(
                CommandReceipt(
                    sequence,
                    False,
                    "command intersects obstacle",
                    started_at_ms,
                    completed_at_ms,
                    self.pose,
                    BaseState(),
                )
            )

        self.pose = next_pose
        self.base_state = BaseState(command.vx, command.vy, command.yaw_rate)
        return encode_command_receipt(
            CommandReceipt(
                sequence,
                True,
                "command completed",
                started_at_ms,
                completed_at_ms,
                self.pose,
                self.base_state,
            )
        )

    def _observe(self, request: ObservationRequest) -> bytes:
        frame_id = request.frame_id
        captured_at_ms = request.captured_at_ms
        visible = tuple(
            obstacle
            for obstacle in self.obstacles
            if obstacle.active_from_ms <= captured_at_ms
            and (obstacle.active_until_ms is None or captured_at_ms < obstacle.active_until_ms)
            and hypot(obstacle.x - self.pose.x, obstacle.y - self.pose.y) <= self.sensor_range_m
        )
        self.observation_request_count += 1
        return encode_sensor_packet(
            SensorPacket(
                SensorFrame(
                    frame_id,
                    captured_at_ms,
                    self.pose,
                    visible,
                    render_camera(self.pose, visible, self.sensor_range_m),
                    self.base_state,
                ),
                captured_at_ms + self.sensor_latency_ms,
            )
        )

    def halt(self) -> None:
        self.halt_count += 1
        self.base_state = BaseState()

    def stop(self) -> None:
        self.stopped = True
        self.halt()


def encode_base_command(sequence: int, command: BaseVelocity, issued_at_ms: int) -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "operation": "base_velocity",
            "sequence": sequence,
            "issued_at_ms": issued_at_ms,
            "command": asdict(command),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def encode_observation_request(frame_id: int, captured_at_ms: int) -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "operation": "observe",
            "frame_id": frame_id,
            "captured_at_ms": captured_at_ms,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def decode_base_command(request: bytes) -> BaseCommandRequest:
    payload = json.loads(request)
    if payload.get("schema_version") != 1 or payload.get("operation") != "base_velocity":
        raise ValueError("unsupported robot base command envelope")
    command = payload.get("command")
    if not isinstance(command, dict):
        raise ValueError("robot command is missing")
    return BaseCommandRequest(
        _required_int(payload, "sequence"),
        _required_int(payload, "issued_at_ms"),
        BaseVelocity(
            float(command["vx"]),
            float(command["vy"]),
            float(command["yaw_rate"]),
            _required_int(command, "duration_ms"),
        ),
    )


def decode_observation_request(request: bytes) -> ObservationRequest:
    payload = json.loads(request)
    if payload.get("schema_version") != 1 or payload.get("operation") != "observe":
        raise ValueError("unsupported robot observation envelope")
    return ObservationRequest(
        _required_int(payload, "frame_id"),
        _required_int(payload, "captured_at_ms"),
    )


def decode_command_receipt(response: bytes, expected_sequence: int) -> CommandReceipt:
    payload = json.loads(response)
    if payload.get("schema_version") != 1 or payload.get("operation") != "base_velocity_ack":
        raise ValueError("unsupported robot feedback envelope")
    sequence = _required_int(payload, "sequence")
    if sequence != expected_sequence:
        raise ValueError("robot feedback sequence mismatch")
    pose = payload.get("pose")
    state = payload.get("base_state")
    if not isinstance(pose, dict) or not isinstance(state, dict):
        raise ValueError("robot feedback state is missing")
    return CommandReceipt(
        sequence,
        bool(payload["accepted"]),
        str(payload["detail"]),
        _required_int(payload, "started_at_ms"),
        _required_int(payload, "completed_at_ms"),
        Pose2D(float(pose["x"]), float(pose["y"]), float(pose["yaw"])),
        BaseState(float(state["vx"]), float(state["vy"]), float(state["yaw_rate"])),
    )


def decode_sensor_packet(response: bytes, expected_frame_id: int) -> SensorPacket:
    payload = json.loads(response)
    if payload.get("schema_version") != 1 or payload.get("operation") != "sensor_frame":
        raise ValueError("unsupported robot sensor envelope")
    frame_id = _required_int(payload, "frame_id")
    if frame_id != expected_frame_id:
        raise ValueError("robot sensor frame mismatch")
    pose = payload["pose"]
    camera = payload["camera"]
    state = payload["proprioception"]
    obstacles = payload["obstacles"]
    if not all(isinstance(value, dict) for value in (pose, camera, state)) or not isinstance(
        obstacles, list
    ):
        raise ValueError("robot sensor frame is incomplete")
    return SensorPacket(
        SensorFrame(
            frame_id,
            _required_int(payload, "captured_at_ms"),
            Pose2D(float(pose["x"]), float(pose["y"]), float(pose["yaw"])),
            tuple(_decode_obstacle(obstacle) for obstacle in obstacles),
            CameraFrame(
                _required_int(camera, "width"),
                _required_int(camera, "height"),
                str(camera["encoding"]),
                b64decode(str(camera["data_base64"]), validate=True),
            ),
            BaseState(float(state["vx"]), float(state["vy"]), float(state["yaw_rate"])),
        ),
        _required_int(payload, "available_at_ms"),
    )


def decode_sensor_frame(response: bytes, expected_frame_id: int) -> SensorFrame:
    return decode_sensor_packet(response, expected_frame_id).frame


def encode_command_receipt(receipt: CommandReceipt) -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "operation": "base_velocity_ack",
            **asdict(receipt),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def encode_sensor_packet(packet: SensorPacket) -> bytes:
    frame = packet.frame
    return json.dumps(
        {
            "schema_version": 1,
            "operation": "sensor_frame",
            "frame_id": frame.frame_id,
            "captured_at_ms": frame.captured_at_ms,
            "available_at_ms": packet.available_at_ms,
            "pose": asdict(frame.pose),
            "obstacles": [asdict(obstacle) for obstacle in frame.obstacles],
            "camera": {
                "width": frame.camera.width,
                "height": frame.camera.height,
                "encoding": frame.camera.encoding,
                "data_base64": b64encode(frame.camera.data).decode("ascii"),
            },
            "proprioception": asdict(frame.proprioception),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _decode_obstacle(payload: object) -> Obstacle2D:
    if not isinstance(payload, dict):
        raise ValueError("robot sensor obstacle is invalid")
    active_until = payload["active_until_ms"]
    return Obstacle2D(
        str(payload["obstacle_id"]),
        float(payload["x"]),
        float(payload["y"]),
        float(payload["radius"]),
        _required_int(payload, "active_from_ms"),
        None if active_until is None else _required_int(payload, "active_until_ms"),
    )


def _required_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"robot envelope {key} must be an integer")
    return value
