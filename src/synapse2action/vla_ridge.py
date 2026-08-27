from __future__ import annotations

from base64 import b64decode
from collections import Counter
from dataclasses import dataclass
import json
from math import hypot, isfinite, sqrt
from pathlib import Path


JSON_OBJECT = dict[str, object]
BASE_FEATURE_NAMES = (
    "goal_dx",
    "goal_dy",
    "goal_distance",
    "goal_unit_x",
    "goal_unit_y",
    "vx",
    "vy",
    "yaw_rate",
    "camera_occupancy",
    "camera_centroid_x",
    "camera_centroid_y",
    "occupancy_x_centroid_x",
    "occupancy_x_centroid_y",
    "obstacle_relative_x",
    "obstacle_relative_y",
    "obstacle_radius",
    "obstacle_along_goal",
    "obstacle_cross_goal",
    "obstacle_cross_squared",
    "blocking_score",
    "detour_x",
    "detour_y",
)
FEATURE_NAMES = BASE_FEATURE_NAMES
TEMPORAL_START = BASE_FEATURE_NAMES.index("camera_occupancy")
TEMPORAL_FEATURE_NAMES = (
    *BASE_FEATURE_NAMES,
    *(f"delta_{name}" for name in BASE_FEATURE_NAMES[TEMPORAL_START:]),
)


@dataclass(frozen=True, slots=True)
class RidgeCheckpoint:
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    weights: tuple[tuple[float, ...], ...]
    duration_ms: int
    training_episode_ids: tuple[str, ...]
    ridge_lambda: float
    history_steps: int = 0
    temporal_regularization: float = 1.0

    def to_dict(self) -> JSON_OBJECT:
        payload: JSON_OBJECT = {
            "schema_version": 1 if self.history_steps == 0 else 2,
            "format": "synapse2action.ridge_vla",
            "algorithm": (
                "ridge_behavior_cloning"
                if self.history_steps == 0
                else "temporal_ridge_behavior_cloning"
            ),
            "feature_names": list(_feature_names(self.history_steps)),
            "normalization": {"mean": list(self.mean), "scale": list(self.scale)},
            "weights": [list(row) for row in self.weights],
            "duration_ms": self.duration_ms,
            "training_episode_ids": list(self.training_episode_ids),
            "ridge_lambda": self.ridge_lambda,
        }
        if self.history_steps:
            payload["history_steps"] = self.history_steps
            payload["temporal_regularization"] = self.temporal_regularization
        return payload


@dataclass(slots=True)
class RidgeVLABackend:
    checkpoint: RidgeCheckpoint
    request_count: int = 0
    previous_feature: tuple[float, ...] | None = None

    def reset(self, task_payload: bytes) -> None:
        payload = _json_object(task_payload)
        if payload.get("schema_version") != 1 or not isinstance(payload.get("task"), dict):
            raise ValueError("invalid task for Ridge VLA baseline")
        self.request_count = 1
        self.previous_feature = None

    def infer(self, observation_payload: bytes) -> bytes:
        current = _wire_feature(_json_object(observation_payload))
        feature = _model_feature(current, self.previous_feature, self.checkpoint.history_steps)
        velocity = _predict(self.checkpoint, feature)
        self.previous_feature = tuple(current)
        self.request_count += 1
        return json.dumps(
            {
                "schema_version": 1,
                "commands": [
                    {
                        "vx": velocity[0],
                        "vy": velocity[1],
                        "yaw_rate": velocity[2],
                        "duration_ms": self.checkpoint.duration_ms,
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()


def train_ridge_baseline(
    dataset_directory: Path,
    checkpoint_path: Path,
    ridge_lambda: float = 0.01,
) -> JSON_OBJECT:
    return _train_ridge_baseline(dataset_directory, checkpoint_path, ridge_lambda, 0)


def train_temporal_ridge_baseline(
    dataset_directory: Path,
    checkpoint_path: Path,
    ridge_lambda: float = 0.01,
    temporal_regularization: float = 100_000.0,
) -> JSON_OBJECT:
    if temporal_regularization < 1 or not isfinite(temporal_regularization):
        raise ValueError("temporal regularization must be finite and at least one")
    return _train_ridge_baseline(
        dataset_directory,
        checkpoint_path,
        ridge_lambda,
        1,
        temporal_regularization,
    )


def _train_ridge_baseline(
    dataset_directory: Path,
    checkpoint_path: Path,
    ridge_lambda: float,
    history_steps: int,
    temporal_regularization: float = 1.0,
) -> JSON_OBJECT:
    if ridge_lambda <= 0 or not isfinite(ridge_lambda):
        raise ValueError("ridge lambda must be positive")
    manifest = _load_manifest(dataset_directory / "manifest.json")
    train_samples = _load_jsonl(dataset_directory / manifest["splits"]["train"]["file"])
    validation_samples = _load_jsonl(dataset_directory / manifest["splits"]["validation"]["file"])
    if not train_samples:
        raise ValueError("Ridge VLA baseline requires training samples")

    features = _sequence_features(train_samples, history_steps)
    targets = [_single_action(sample)[:3] for sample in train_samples]
    mean, scale = _normalization(features)
    design = [[1.0, *_normalize(feature, mean, scale)] for feature in features]
    weights = tuple(
        tuple(
            _ridge_solve(
                design,
                [target[axis] for target in targets],
                ridge_lambda,
                len(BASE_FEATURE_NAMES) if history_steps else len(FEATURE_NAMES),
                temporal_regularization,
            )
        )
        for axis in range(3)
    )
    duration_ms = Counter(_single_action(sample)[3] for sample in train_samples).most_common(1)[0][0]
    training_episode_ids = tuple(sorted({str(sample["episode_id"]) for sample in train_samples}))
    checkpoint = RidgeCheckpoint(
        mean,
        scale,
        weights,
        duration_ms,
        training_episode_ids,
        ridge_lambda,
        history_steps,
        temporal_regularization,
    )
    checkpoint_path.write_text(
        json.dumps(checkpoint.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    metrics = evaluate_ridge_baseline(dataset_directory, checkpoint)
    return {
        "schema_version": 1,
        "baseline": (
            "ridge_behavior_cloning" if history_steps == 0 else "temporal_ridge_behavior_cloning"
        ),
        "checkpoint": str(checkpoint_path),
        "training_episodes": len(training_episode_ids),
        "training_samples": len(train_samples),
        **metrics,
    }


def evaluate_ridge_baseline(dataset_directory: Path, checkpoint: RidgeCheckpoint) -> JSON_OBJECT:
    manifest = _load_manifest(dataset_directory / "manifest.json")
    train_ids = set(manifest["splits"]["train"]["episodes"])
    validation_ids = set(manifest["splits"]["validation"]["episodes"])
    if set(checkpoint.training_episode_ids) != train_ids or train_ids & validation_ids:
        raise ValueError("Ridge checkpoint does not match dataset split")
    samples = _load_jsonl(dataset_directory / manifest["splits"]["validation"]["file"])
    if {sample["episode_id"] for sample in samples} != validation_ids:
        raise ValueError("validation samples do not match dataset manifest")
    if not samples:
        return {
            "training_episode_ids": sorted(train_ids),
            "validation_episode_ids": sorted(validation_ids),
            "validation_episodes": 0,
            "validation_samples": 0,
            "validation_velocity_mae": None,
            "validation_duration_accuracy": None,
        }
    absolute_error = 0.0
    durations = 0
    matching_duration = 0
    for sample, feature in zip(
        samples,
        _sequence_features(samples, checkpoint.history_steps),
        strict=True,
    ):
        predicted = _predict(checkpoint, feature)
        expected = _single_action(sample)
        absolute_error += sum(abs(predicted[index] - expected[index]) for index in range(3))
        durations += 1
        matching_duration += checkpoint.duration_ms == expected[3]
    return {
        "training_episode_ids": sorted(train_ids),
        "validation_episode_ids": sorted(validation_ids),
        "validation_episodes": len(validation_ids),
        "validation_samples": len(samples),
        "validation_velocity_mae": absolute_error / (len(samples) * 3),
        "validation_duration_accuracy": matching_duration / durations,
    }


def load_ridge_checkpoint(path: Path) -> RidgeCheckpoint:
    payload = json.loads(path.read_text(encoding="utf-8"))
    common = {
        "schema_version",
        "format",
        "algorithm",
        "feature_names",
        "normalization",
        "weights",
        "duration_ms",
        "training_episode_ids",
        "ridge_lambda",
    }
    if not isinstance(payload, dict):
        raise ValueError("Ridge VLA checkpoint does not match schema")
    history_steps = payload.get("history_steps", 0)
    expected = common | (
        {"history_steps", "temporal_regularization"} if history_steps else set()
    )
    feature_names = _feature_names(history_steps)
    algorithm = "ridge_behavior_cloning" if history_steps == 0 else "temporal_ridge_behavior_cloning"
    schema_version = 1 if history_steps == 0 else 2
    if set(payload) != expected or (
        payload["schema_version"] != schema_version
        or payload["format"] != "synapse2action.ridge_vla"
        or payload["algorithm"] != algorithm
        or payload["feature_names"] != list(feature_names)
        or history_steps not in (0, 1)
    ):
        raise ValueError("unsupported Ridge VLA checkpoint")
    normalization = _object(payload["normalization"])
    if set(normalization) != {"mean", "scale"}:
        raise ValueError("invalid Ridge VLA normalization")
    mean = tuple(_vector(normalization.get("mean"), len(feature_names)))
    scale = tuple(_vector(normalization.get("scale"), len(feature_names)))
    if any(value <= 0 for value in scale):
        raise ValueError("invalid Ridge VLA scale")
    if not isinstance(payload["weights"], list) or len(payload["weights"]) != 3:
        raise ValueError("invalid Ridge VLA weights")
    weights = tuple(tuple(_vector(row, len(feature_names) + 1)) for row in payload["weights"])
    duration = payload["duration_ms"]
    if type(duration) is not int or duration <= 0:
        raise ValueError("invalid Ridge VLA duration")
    episode_ids = payload["training_episode_ids"]
    if not isinstance(episode_ids, list) or not all(isinstance(value, str) for value in episode_ids):
        raise ValueError("invalid Ridge VLA training episodes")
    if len(set(episode_ids)) != len(episode_ids):
        raise ValueError("duplicate Ridge VLA training episode")
    ridge_lambda = _number(payload["ridge_lambda"])
    if ridge_lambda <= 0:
        raise ValueError("invalid Ridge VLA lambda")
    temporal_regularization = (
        _number(payload["temporal_regularization"]) if history_steps else 1.0
    )
    if temporal_regularization < 1:
        raise ValueError("invalid temporal Ridge regularization")
    return RidgeCheckpoint(
        mean,
        scale,
        weights,
        duration,
        tuple(episode_ids),
        ridge_lambda,
        history_steps,
        temporal_regularization,
    )


def _ridge_solve(
    design: list[list[float]],
    targets: list[float],
    ridge_lambda: float,
    base_feature_count: int,
    temporal_regularization: float,
) -> list[float]:
    width = len(design[0])
    matrix = [
        [
            sum(row[left] * row[right] for row in design)
            + (
                ridge_lambda
                * (temporal_regularization if left > base_feature_count else 1.0)
                if left == right and left
                else 0.0
            )
            for right in range(width)
        ]
        + [sum(row[left] * target for row, target in zip(design, targets, strict=True))]
        for left in range(width)
    ]
    for column in range(width):
        pivot = max(range(column, width), key=lambda row: abs(matrix[row][column]))
        if abs(matrix[pivot][column]) < 1e-12:
            raise ValueError("Ridge VLA normal equation is singular")
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        divisor = matrix[column][column]
        matrix[column] = [value / divisor for value in matrix[column]]
        for row in range(width):
            if row == column:
                continue
            factor = matrix[row][column]
            matrix[row] = [value - factor * pivot_value for value, pivot_value in zip(matrix[row], matrix[column], strict=True)]
    return [matrix[row][-1] for row in range(width)]


def _predict(checkpoint: RidgeCheckpoint, feature: list[float]) -> list[float]:
    design = [1.0, *_normalize(feature, checkpoint.mean, checkpoint.scale)]
    return [sum(weight * value for weight, value in zip(row, design, strict=True)) for row in checkpoint.weights]


def _sample_feature(sample: JSON_OBJECT) -> list[float]:
    observation = _object(sample.get("observation"))
    state = _vector(observation.get("state"), 6)
    goal = _vector(observation.get("goal"), 3)
    return _features(state, goal, _object(observation.get("camera")), observation.get("obstacles"))


def _sequence_features(samples: list[JSON_OBJECT], history_steps: int) -> list[list[float]]:
    previous: dict[str, tuple[int, tuple[float, ...]]] = {}
    features = []
    for sample in samples:
        episode_id = sample.get("episode_id")
        step = sample.get("step_index")
        if not isinstance(episode_id, str) or type(step) is not int:
            raise ValueError("invalid Ridge VLA episode sequence")
        prior = previous.get(episode_id)
        if step != (prior[0] + 1 if prior else 0):
            raise ValueError("Ridge VLA episode steps are not contiguous")
        current = _sample_feature(sample)
        features.append(_model_feature(current, prior[1] if prior else None, history_steps))
        previous[episode_id] = (step, tuple(current))
    return features


def _model_feature(
    current: list[float],
    previous: tuple[float, ...] | None,
    history_steps: int,
) -> list[float]:
    if len(current) != len(BASE_FEATURE_NAMES):
        raise ValueError("Ridge VLA base feature length mismatch")
    if history_steps == 0:
        return current
    if history_steps != 1:
        raise ValueError("unsupported Ridge VLA history length")
    prior = previous or tuple(current)
    return [
        *current,
        *(
            value - old
            for value, old in zip(
                current[TEMPORAL_START:],
                prior[TEMPORAL_START:],
                strict=True,
            )
        ),
    ]


def _feature_names(history_steps: int) -> tuple[str, ...]:
    if history_steps == 0:
        return FEATURE_NAMES
    if history_steps == 1:
        return TEMPORAL_FEATURE_NAMES
    raise ValueError("unsupported Ridge VLA history length")


def _wire_feature(observation: JSON_OBJECT) -> list[float]:
    sensor = _object(observation.get("sensor"))
    pose = _object(sensor.get("pose"))
    proprioception = _object(sensor.get("proprioception"))
    goal = _object(_object(observation.get("task")).get("goal"))
    state = [
        *(_number(pose.get(name)) for name in ("x", "y", "yaw")),
        *(_number(proprioception.get(name)) for name in ("vx", "vy", "yaw_rate")),
    ]
    goal_values = [_number(goal.get(name)) for name in ("x", "y", "yaw")]
    return _features(state, goal_values, _object(sensor.get("camera")), sensor.get("obstacles"))


def _features(
    state: list[float],
    goal: list[float],
    camera: JSON_OBJECT,
    obstacle_values: object,
) -> list[float]:
    dx = goal[0] - state[0]
    dy = goal[1] - state[1]
    distance = hypot(dx, dy)
    unit_x, unit_y = (dx / distance, dy / distance) if distance else (0.0, 0.0)
    occupancy, centroid_x, centroid_y = _camera_features(camera)
    obstacle_x, obstacle_y, obstacle_radius = _blocking_obstacle(state, goal, obstacle_values)
    along = obstacle_x * unit_x + obstacle_y * unit_y
    cross = unit_x * obstacle_y - unit_y * obstacle_x
    blocking = float(obstacle_radius > 0)
    detour_offset = obstacle_radius + 0.2
    return [
        dx,
        dy,
        distance,
        unit_x,
        unit_y,
        state[3],
        state[4],
        state[5],
        occupancy,
        centroid_x,
        centroid_y,
        occupancy * centroid_x,
        occupancy * centroid_y,
        obstacle_x,
        obstacle_y,
        obstacle_radius,
        along,
        cross,
        cross * cross,
        blocking,
        obstacle_x - unit_y * detour_offset if blocking else 0.0,
        obstacle_y + unit_x * detour_offset if blocking else 0.0,
    ]


def _blocking_obstacle(
    state: list[float],
    goal: list[float],
    value: object,
) -> tuple[float, float, float]:
    if not isinstance(value, list):
        raise ValueError("invalid obstacles for Ridge VLA")
    goal_x = goal[0] - state[0]
    goal_y = goal[1] - state[1]
    length_squared = goal_x * goal_x + goal_y * goal_y
    blocking = []
    for item in value:
        obstacle = _object(item)
        relative_x = _number(obstacle.get("x")) - state[0]
        relative_y = _number(obstacle.get("y")) - state[1]
        radius = _number(obstacle.get("radius"))
        progress = (
            max(0.0, min(1.0, (relative_x * goal_x + relative_y * goal_y) / length_squared))
            if length_squared
            else 0.0
        )
        nearest_x = progress * goal_x
        nearest_y = progress * goal_y
        distance = hypot(relative_x - nearest_x, relative_y - nearest_y)
        if 0 < progress < 1 and distance < radius + 0.1:
            blocking.append((progress, relative_x, relative_y, radius))
    if not blocking:
        return 0.0, 0.0, 0.0
    _, relative_x, relative_y, radius = min(blocking)
    return relative_x, relative_y, radius


def _camera_features(camera: JSON_OBJECT) -> tuple[float, float, float]:
    width = camera.get("width")
    height = camera.get("height")
    data_base64 = camera.get("data_base64")
    if (
        set(camera) != {"width", "height", "encoding", "data_base64"}
        or camera.get("encoding") != "mono8"
        or type(width) is not int
        or type(height) is not int
        or not isinstance(data_base64, str)
    ):
        raise ValueError("invalid camera for Ridge VLA")
    data = b64decode(data_base64, validate=True)
    if width <= 0 or height <= 0 or len(data) != width * height:
        raise ValueError("invalid camera size for Ridge VLA")
    occupied = [index for index, pixel in enumerate(data) if pixel]
    if not occupied:
        return 0.0, 0.0, 0.0
    return (
        len(occupied) / len(data),
        sum(index % width for index in occupied) / len(occupied) / max(1, width - 1) * 2 - 1,
        sum(index // width for index in occupied) / len(occupied) / max(1, height - 1) * 2 - 1,
    )


def _normalization(features: list[list[float]]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    columns = list(zip(*features, strict=True))
    mean = tuple(sum(column) / len(column) for column in columns)
    scale = tuple(sqrt(sum((value - center) ** 2 for value in column) / len(column)) or 1.0 for column, center in zip(columns, mean, strict=True))
    return mean, scale


def _normalize(feature: list[float], mean: tuple[float, ...], scale: tuple[float, ...]) -> list[float]:
    return [(value - center) / width for value, center, width in zip(feature, mean, scale, strict=True)]


def _single_action(sample: JSON_OBJECT) -> list[float | int]:
    action = sample.get("action")
    if not isinstance(action, list) or len(action) != 1:
        raise ValueError("Ridge VLA requires one-command action chunks")
    command = action[0]
    if not isinstance(command, list) or len(command) != 4 or type(command[3]) is not int or command[3] <= 0:
        raise ValueError("invalid Ridge VLA action")
    return [*(_number(value) for value in command[:3]), command[3]]


def _load_manifest(path: Path) -> JSON_OBJECT:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("format") != "synapse2action.vla_dataset":
        raise ValueError("invalid VLA dataset manifest")
    return manifest


def _load_jsonl(path: Path) -> list[JSON_OBJECT]:
    return [_object(json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _json_object(payload: bytes) -> JSON_OBJECT:
    return _object(json.loads(payload))


def _object(value: object) -> JSON_OBJECT:
    if not isinstance(value, dict):
        raise ValueError("Ridge VLA field must be an object")
    return value


def _vector(value: object, length: int) -> list[float]:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError("Ridge VLA vector length mismatch")
    return [_number(item) for item in value]


def _number(value: object) -> float:
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("Ridge VLA numeric field is invalid")
    return float(value)
