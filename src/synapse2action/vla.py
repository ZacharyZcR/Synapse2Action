from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import asdict, dataclass, field
import json
from math import isfinite
from typing import Protocol

from .navigation import (
    ActionChunk,
    BaseState,
    BaseVelocity,
    CameraFrame,
    NavigationObservation,
    NavigationScenario,
    NavigationTask,
    Obstacle2D,
    Pose2D,
    ScriptedNavigationPolicy,
    SensorFrame,
    run_navigation_demo,
)


class VLAInferenceBackend(Protocol):
    def reset(self, task_payload: bytes) -> None: ...

    def infer(self, observation_payload: bytes) -> bytes: ...


@dataclass(slots=True)
class VLANavigationPolicy:
    backend: VLAInferenceBackend
    task: NavigationTask | None = None
    request_count: int = 0

    @property
    def replan_count(self) -> int | None:
        return getattr(self.backend, "replan_count", None)

    @property
    def backend_request_count(self) -> int | None:
        return getattr(self.backend, "request_count", None)

    def reset(self, task: NavigationTask) -> None:
        self.task = task
        self.request_count = 0
        self.backend.reset(_encode({"schema_version": 1, "task": _task_payload(task)}))

    def predict(self, observation: NavigationObservation) -> ActionChunk:
        if self.task is None or observation.task != self.task:
            raise ValueError("VLA observation does not match the active task")
        response = self.backend.infer(_encode(_observation_payload(observation)))
        self.request_count += 1
        return _decode_action_chunk(response)


@dataclass(slots=True)
class DeterministicVLABackend:
    policy: ScriptedNavigationPolicy = field(default_factory=ScriptedNavigationPolicy)
    requests: list[dict[str, object]] = field(default_factory=list)

    @property
    def replan_count(self) -> int:
        return self.policy.replan_count

    def reset(self, task_payload: bytes) -> None:
        payload = _decode_json(task_payload)
        _require_keys(payload, {"schema_version", "task"})
        if payload["schema_version"] != 1:
            raise ValueError("unsupported VLA task schema")
        self.policy.reset(_parse_task(payload["task"]))
        self.requests.clear()

    def infer(self, observation_payload: bytes) -> bytes:
        payload = _decode_json(observation_payload)
        observation = _parse_observation(payload)
        self.requests.append(payload)
        chunk = self.policy.predict(observation)
        return _encode(
            {
                "schema_version": 1,
                "commands": [asdict(command) for command in chunk.commands],
            }
        )


def run_vla_navigation_demo(
    backend: VLAInferenceBackend | None = None,
    scenario: NavigationScenario | None = None,
) -> dict[str, object]:
    backend = backend or DeterministicVLABackend()
    report = run_navigation_demo(VLANavigationPolicy(backend), scenario=scenario)
    report["demo"] = f"vla_adapter_{report['scenario']}"
    report["vla_backend"] = type(backend).__name__
    report["serialized_observations"] = report["control_cycles"]
    return report


def _encode(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _decode_json(payload: bytes) -> dict[str, object]:
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("VLA payload is not valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("VLA payload must be a JSON object")
    return decoded


def _require_keys(payload: object, expected: set[str]) -> dict[str, object]:
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("VLA payload does not match schema")
    return payload


def _pose_payload(pose: Pose2D) -> dict[str, float]:
    return {"x": pose.x, "y": pose.y, "yaw": pose.yaw}


def _task_payload(task: NavigationTask) -> dict[str, object]:
    return {"instruction": task.instruction, "goal": _pose_payload(task.goal)}


def _observation_payload(observation: NavigationObservation) -> dict[str, object]:
    sensor = observation.sensor
    return {
        "schema_version": 1,
        "task": _task_payload(observation.task),
        "step": observation.step,
        "sensor": {
            "frame_id": sensor.frame_id,
            "captured_at_ms": sensor.captured_at_ms,
            "pose": _pose_payload(sensor.pose),
            "camera": {
                "width": sensor.camera.width,
                "height": sensor.camera.height,
                "encoding": sensor.camera.encoding,
                "data_base64": b64encode(sensor.camera.data).decode("ascii"),
            },
            "proprioception": asdict(sensor.proprioception),
            "obstacles": [asdict(obstacle) for obstacle in sensor.obstacles],
        },
    }


def _parse_pose(payload: object) -> Pose2D:
    values = _require_keys(payload, {"x", "y", "yaw"})
    return Pose2D(*(_number(values[name]) for name in ("x", "y", "yaw")))


def _parse_task(payload: object) -> NavigationTask:
    values = _require_keys(payload, {"instruction", "goal"})
    if not isinstance(values["instruction"], str):
        raise ValueError("VLA instruction must be a string")
    return NavigationTask(values["instruction"], _parse_pose(values["goal"]))


def _parse_observation(payload: dict[str, object]) -> NavigationObservation:
    _require_keys(payload, {"schema_version", "task", "step", "sensor"})
    if payload["schema_version"] != 1 or type(payload["step"]) is not int:
        raise ValueError("unsupported VLA observation schema")
    sensor_payload = _require_keys(
        payload["sensor"],
        {"frame_id", "captured_at_ms", "pose", "camera", "proprioception", "obstacles"},
    )
    if type(sensor_payload["frame_id"]) is not int or type(sensor_payload["captured_at_ms"]) is not int:
        raise ValueError("invalid VLA sensor sequence")
    camera_payload = _require_keys(sensor_payload["camera"], {"width", "height", "encoding", "data_base64"})
    if type(camera_payload["width"]) is not int or type(camera_payload["height"]) is not int:
        raise ValueError("invalid VLA camera dimensions")
    if not isinstance(camera_payload["encoding"], str) or not isinstance(camera_payload["data_base64"], str):
        raise ValueError("invalid VLA camera payload")
    try:
        camera_data = b64decode(camera_payload["data_base64"], validate=True)
    except ValueError as exc:
        raise ValueError("invalid VLA camera data") from exc
    if len(camera_data) != camera_payload["width"] * camera_payload["height"]:
        raise ValueError("VLA camera byte count does not match dimensions")
    proprioception = _require_keys(sensor_payload["proprioception"], {"vx", "vy", "yaw_rate"})
    obstacle_payloads = sensor_payload["obstacles"]
    if not isinstance(obstacle_payloads, list):
        raise ValueError("VLA obstacles must be a list")
    obstacles = tuple(_parse_obstacle(item) for item in obstacle_payloads)
    sensor = SensorFrame(
        sensor_payload["frame_id"],
        sensor_payload["captured_at_ms"],
        _parse_pose(sensor_payload["pose"]),
        obstacles,
        CameraFrame(camera_payload["width"], camera_payload["height"], camera_payload["encoding"], camera_data),
        BaseState(*(_number(proprioception[name]) for name in ("vx", "vy", "yaw_rate"))),
    )
    return NavigationObservation(sensor, _parse_task(payload["task"]), payload["step"])


def _parse_obstacle(payload: object) -> Obstacle2D:
    values = _require_keys(
        payload,
        {"obstacle_id", "x", "y", "radius", "active_from_ms", "active_until_ms"},
    )
    if not isinstance(values["obstacle_id"], str) or type(values["active_from_ms"]) is not int:
        raise ValueError("invalid VLA obstacle")
    active_until = values["active_until_ms"]
    if active_until is not None and type(active_until) is not int:
        raise ValueError("invalid VLA obstacle lifetime")
    return Obstacle2D(
        values["obstacle_id"],
        _number(values["x"]),
        _number(values["y"]),
        _number(values["radius"]),
        values["active_from_ms"],
        active_until,
    )


def _number(value: object) -> float:
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("VLA numeric field is invalid")
    return float(value)


def _decode_action_chunk(payload: bytes) -> ActionChunk:
    response = _decode_json(payload)
    _require_keys(response, {"schema_version", "commands"})
    if response["schema_version"] != 1 or not isinstance(response["commands"], list):
        raise ValueError("unsupported VLA action schema")
    commands = []
    for item in response["commands"]:
        command = _require_keys(item, {"vx", "vy", "yaw_rate", "duration_ms"})
        if type(command["duration_ms"]) is not int or command["duration_ms"] <= 0:
            raise ValueError("VLA action duration must be a positive integer")
        commands.append(
            BaseVelocity(
                _number(command["vx"]),
                _number(command["vy"]),
                _number(command["yaw_rate"]),
                command["duration_ms"],
            )
        )
    return ActionChunk(tuple(commands))
