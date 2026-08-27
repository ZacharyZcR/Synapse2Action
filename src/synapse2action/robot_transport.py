from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from math import hypot
from typing import Protocol

from .navigation import BaseState, BaseVelocity, Obstacle2D, Pose2D


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
    completed_at_ms: int
    pose: Pose2D
    base_state: BaseState


@dataclass(slots=True)
class LoopbackRobotTransport:
    pose: Pose2D
    obstacles: tuple[Obstacle2D, ...] = ()
    robot_radius_m: float = 0.1
    name: str = "loopback"
    stopped: bool = False
    request_count: int = 0
    halt_count: int = 0
    base_state: BaseState = BaseState()

    def exchange(self, request: bytes) -> bytes:
        payload = json.loads(request)
        if payload.get("schema_version") != 1 or payload.get("operation") != "base_velocity":
            raise ValueError("unsupported robot command envelope")
        sequence = _required_int(payload, "sequence")
        issued_at_ms = _required_int(payload, "issued_at_ms")
        command_payload = payload.get("command")
        if not isinstance(command_payload, dict):
            raise ValueError("robot command is missing")
        command = BaseVelocity(
            float(command_payload["vx"]),
            float(command_payload["vy"]),
            float(command_payload["yaw_rate"]),
            _required_int(command_payload, "duration_ms"),
        )
        self.request_count += 1
        completed_at_ms = issued_at_ms + command.duration_ms
        if self.stopped:
            return _encode_receipt(
                CommandReceipt(sequence, False, "transport is stopped", completed_at_ms, self.pose, BaseState())
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
            return _encode_receipt(
                CommandReceipt(sequence, False, "command intersects obstacle", completed_at_ms, self.pose, BaseState())
            )

        self.pose = next_pose
        self.base_state = BaseState(command.vx, command.vy, command.yaw_rate)
        return _encode_receipt(
            CommandReceipt(
                sequence,
                True,
                "command completed",
                completed_at_ms,
                self.pose,
                self.base_state,
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
        _required_int(payload, "completed_at_ms"),
        Pose2D(float(pose["x"]), float(pose["y"]), float(pose["yaw"])),
        BaseState(float(state["vx"]), float(state["vy"]), float(state["yaw_rate"])),
    )


def _encode_receipt(receipt: CommandReceipt) -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "operation": "base_velocity_ack",
            **asdict(receipt),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _required_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"robot envelope {key} must be an integer")
    return value
