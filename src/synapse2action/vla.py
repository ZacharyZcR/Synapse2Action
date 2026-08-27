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
from .robot_transport import RobotTransport


class VLAInferenceBackend(Protocol):
    def reset(self, task_payload: bytes) -> None: ...

    def infer(self, observation_payload: bytes) -> bytes: ...


@dataclass(slots=True)
class VLANavigationPolicy:
    backend: VLAInferenceBackend
    execution_horizon: int | None = None
    temporal_ensemble_decay: float | None = None
    task: NavigationTask | None = None
    request_count: int = 0
    predicted_action_horizon: int = 0
    max_ensemble_contributors: int = 0
    ensemble_reset_count: int = 0
    previous_obstacle_ids: frozenset[str] | None = None
    predictions: list[tuple[int, tuple[BaseVelocity, ...]]] = field(default_factory=list)

    @property
    def replan_count(self) -> int | None:
        return getattr(self.backend, "replan_count", None)

    @property
    def backend_request_count(self) -> int | None:
        return getattr(self.backend, "request_count", None)

    def reset(self, task: NavigationTask) -> None:
        self.task = task
        self.request_count = 0
        self.predicted_action_horizon = 0
        self.max_ensemble_contributors = 0
        self.ensemble_reset_count = 0
        self.previous_obstacle_ids = None
        self.predictions.clear()
        if self.temporal_ensemble_decay is not None and not 0 < self.temporal_ensemble_decay <= 1:
            raise ValueError("VLA temporal ensemble decay must be in (0, 1]")
        if self.temporal_ensemble_decay is not None and self.execution_horizon not in (None, 1):
            raise ValueError("VLA temporal ensembling requires execution horizon one")
        self.backend.reset(_encode({"schema_version": 1, "task": _task_payload(task)}))

    def predict(self, observation: NavigationObservation) -> ActionChunk:
        if self.task is None or observation.task != self.task:
            raise ValueError("VLA observation does not match the active task")
        response = self.backend.infer(_encode(_observation_payload(observation)))
        prediction_step = self.request_count
        self.request_count += 1
        chunk = _decode_action_chunk(response)
        self.predicted_action_horizon = len(chunk.commands)
        if self.temporal_ensemble_decay is not None:
            obstacle_ids = frozenset(obstacle.obstacle_id for obstacle in observation.obstacles)
            perception_changed = (
                self.previous_obstacle_ids is not None
                and obstacle_ids != self.previous_obstacle_ids
            )
            if self.predictions and (obstacle_ids or perception_changed):
                self.predictions.clear()
                self.ensemble_reset_count += 1
            self.previous_obstacle_ids = obstacle_ids
            self.predictions.append((prediction_step, chunk.commands))
            self.predictions = [
                prediction
                for prediction in self.predictions
                if prediction[0] + len(prediction[1]) > prediction_step
            ]
            return ActionChunk((self._ensemble_command(prediction_step),))
        if self.execution_horizon is None:
            return chunk
        if self.execution_horizon <= 0:
            raise ValueError("VLA execution horizon must be positive")
        return ActionChunk(chunk.commands[: self.execution_horizon])

    def _ensemble_command(self, prediction_step: int) -> BaseVelocity:
        candidates = []
        for start, commands in self.predictions:
            age = prediction_step - start
            if 0 <= age < len(commands):
                candidates.append((self.temporal_ensemble_decay**age, commands[age]))
        self.max_ensemble_contributors = max(self.max_ensemble_contributors, len(candidates))
        total_weight = sum(weight for weight, _ in candidates)
        newest = candidates[-1][1]
        return BaseVelocity(
            sum(weight * command.vx for weight, command in candidates) / total_weight,
            sum(weight * command.vy for weight, command in candidates) / total_weight,
            sum(weight * command.yaw_rate for weight, command in candidates) / total_weight,
            newest.duration_ms,
        )


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
    execution_horizon: int | None = None,
    temporal_ensemble_decay: float | None = None,
    transport: RobotTransport | None = None,
) -> dict[str, object]:
    backend = backend or DeterministicVLABackend()
    policy = VLANavigationPolicy(backend, execution_horizon, temporal_ensemble_decay)
    report = run_navigation_demo(policy, scenario=scenario, transport=transport)
    report["demo"] = f"vla_adapter_{report['scenario']}"
    report["vla_backend"] = type(backend).__name__
    report["serialized_observations"] = report["control_cycles"]
    report["predicted_action_horizon"] = policy.predicted_action_horizon
    report["execution_horizon"] = (
        1
        if temporal_ensemble_decay is not None
        else min(execution_horizon, policy.predicted_action_horizon)
        if execution_horizon is not None
        else policy.predicted_action_horizon
    )
    report["temporal_ensemble_decay"] = temporal_ensemble_decay
    report["max_ensemble_contributors"] = policy.max_ensemble_contributors
    report["ensemble_reset_count"] = policy.ensemble_reset_count
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
