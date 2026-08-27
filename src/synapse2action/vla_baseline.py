from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
import json
from math import isfinite, sqrt
from pathlib import Path


JSON_OBJECT = dict[str, object]
FEATURE_NAMES = (
    "x",
    "y",
    "yaw",
    "vx",
    "vy",
    "yaw_rate",
    "goal_x",
    "goal_y",
    "goal_yaw",
    "camera_occupancy",
    "camera_centroid_x",
    "camera_centroid_y",
)


@dataclass(frozen=True, slots=True)
class KNNCheckpoint:
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    samples: tuple[JSON_OBJECT, ...]
    training_episode_ids: tuple[str, ...]

    def to_dict(self) -> JSON_OBJECT:
        return {
            "schema_version": 1,
            "format": "synapse2action.knn_vla",
            "algorithm": "1_nearest_neighbor",
            "feature_names": list(FEATURE_NAMES),
            "normalization": {"mean": list(self.mean), "scale": list(self.scale)},
            "training_episode_ids": list(self.training_episode_ids),
            "samples": list(self.samples),
        }


@dataclass(slots=True)
class KNNVLABackend:
    checkpoint: KNNCheckpoint
    request_count: int = 0

    def reset(self, task_payload: bytes) -> None:
        task = _json_object(task_payload)
        if task.get("schema_version") != 1 or not isinstance(task.get("task"), dict):
            raise ValueError("invalid task for KNN VLA baseline")
        self.request_count = 1

    def infer(self, observation_payload: bytes) -> bytes:
        observation = _json_object(observation_payload)
        feature = _wire_feature(observation)
        action = _predict(self.checkpoint, feature)
        self.request_count += 1
        return json.dumps(
            {"schema_version": 1, "commands": _action_commands(action)},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()


def train_knn_baseline(dataset_directory: Path, checkpoint_path: Path) -> JSON_OBJECT:
    manifest = _load_manifest(dataset_directory / "manifest.json")
    train_samples = _load_jsonl(dataset_directory / manifest["splits"]["train"]["file"])
    validation_samples = _load_jsonl(dataset_directory / manifest["splits"]["validation"]["file"])
    if not train_samples:
        raise ValueError("VLA baseline requires training samples")

    raw_features = [_sample_feature(sample) for sample in train_samples]
    mean, scale = _normalization(raw_features)
    model_samples = tuple(
        {
            "feature": _normalize(feature, mean, scale),
            "action": _sample_action(sample),
        }
        for feature, sample in zip(raw_features, train_samples, strict=True)
    )
    training_episode_ids = tuple(sorted({str(sample["episode_id"]) for sample in train_samples}))
    checkpoint = KNNCheckpoint(mean, scale, model_samples, training_episode_ids)
    checkpoint_path.write_text(
        json.dumps(checkpoint.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    metrics = _evaluate(checkpoint, validation_samples)
    return {
        "schema_version": 1,
        "baseline": "1_nearest_neighbor",
        "checkpoint": str(checkpoint_path),
        "training_episodes": len(training_episode_ids),
        "training_samples": len(train_samples),
        "validation_episodes": len({sample["episode_id"] for sample in validation_samples}),
        "validation_samples": len(validation_samples),
        **metrics,
    }


def load_knn_checkpoint(path: Path) -> KNNCheckpoint:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version",
        "format",
        "algorithm",
        "feature_names",
        "normalization",
        "training_episode_ids",
        "samples",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("KNN VLA checkpoint does not match schema")
    if (
        payload["schema_version"] != 1
        or payload["format"] != "synapse2action.knn_vla"
        or payload["algorithm"] != "1_nearest_neighbor"
        or payload["feature_names"] != list(FEATURE_NAMES)
    ):
        raise ValueError("unsupported KNN VLA checkpoint")
    normalization = _object(payload["normalization"])
    if set(normalization) != {"mean", "scale"}:
        raise ValueError("invalid KNN VLA normalization")
    mean = _float_vector(normalization["mean"], len(FEATURE_NAMES))
    scale = _float_vector(normalization["scale"], len(FEATURE_NAMES))
    if any(value <= 0 for value in scale):
        raise ValueError("invalid KNN VLA feature scale")
    if not isinstance(payload["training_episode_ids"], list) or not all(
        isinstance(value, str) for value in payload["training_episode_ids"]
    ):
        raise ValueError("invalid KNN VLA training episodes")
    if len(set(payload["training_episode_ids"])) != len(payload["training_episode_ids"]):
        raise ValueError("duplicate KNN VLA training episode")
    if not isinstance(payload["samples"], list) or not payload["samples"]:
        raise ValueError("KNN VLA checkpoint has no samples")
    samples = tuple(_checkpoint_sample(sample) for sample in payload["samples"])
    return KNNCheckpoint(mean, scale, samples, tuple(payload["training_episode_ids"]))


def _evaluate(checkpoint: KNNCheckpoint, samples: list[JSON_OBJECT]) -> JSON_OBJECT:
    if not samples:
        return {"validation_velocity_mae": None, "validation_duration_accuracy": None}
    absolute_error = 0.0
    velocity_values = 0
    durations = 0
    matching_durations = 0
    for sample in samples:
        predicted = _predict(checkpoint, _sample_feature(sample))
        expected = _sample_action(sample)
        if len(predicted) != len(expected):
            raise ValueError("validation action chunk length mismatch")
        for predicted_command, expected_command in zip(predicted, expected, strict=True):
            absolute_error += sum(abs(predicted_command[index] - expected_command[index]) for index in range(3))
            velocity_values += 3
            durations += 1
            matching_durations += predicted_command[3] == expected_command[3]
    return {
        "validation_velocity_mae": absolute_error / velocity_values,
        "validation_duration_accuracy": matching_durations / durations,
    }


def _predict(checkpoint: KNNCheckpoint, raw_feature: list[float]) -> list[list[float | int]]:
    feature = _normalize(raw_feature, checkpoint.mean, checkpoint.scale)
    nearest = min(
        checkpoint.samples,
        key=lambda sample: sum(
            (left - right) ** 2
            for left, right in zip(feature, sample["feature"], strict=True)
        ),
    )
    return nearest["action"]


def _sample_feature(sample: JSON_OBJECT) -> list[float]:
    observation = _object(sample.get("observation"))
    state = _float_vector(observation.get("state"), 6)
    goal = _float_vector(observation.get("goal"), 3)
    return [*state, *goal, *_camera_features(_object(observation.get("camera")))]


def _wire_feature(observation: JSON_OBJECT) -> list[float]:
    sensor = _object(observation.get("sensor"))
    pose = _object(sensor.get("pose"))
    proprioception = _object(sensor.get("proprioception"))
    task = _object(observation.get("task"))
    goal = _object(task.get("goal"))
    state = [
        *(_float(pose.get(name)) for name in ("x", "y", "yaw")),
        *(_float(proprioception.get(name)) for name in ("vx", "vy", "yaw_rate")),
    ]
    goal_values = [_float(goal.get(name)) for name in ("x", "y", "yaw")]
    return [*state, *goal_values, *_camera_features(_object(sensor.get("camera")))]


def _camera_features(camera: JSON_OBJECT) -> list[float]:
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
        raise ValueError("invalid camera for KNN VLA baseline")
    data = b64decode(data_base64, validate=True)
    if width <= 0 or height <= 0 or len(data) != width * height:
        raise ValueError("invalid camera size for KNN VLA baseline")
    occupied = [index for index, pixel in enumerate(data) if pixel]
    if not occupied:
        return [0.0, 0.0, 0.0]
    columns = [index % width for index in occupied]
    rows = [index // width for index in occupied]
    return [
        len(occupied) / len(data),
        sum(columns) / len(columns) / max(1, width - 1) * 2 - 1,
        sum(rows) / len(rows) / max(1, height - 1) * 2 - 1,
    ]


def _normalization(features: list[list[float]]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    mean = tuple(sum(values) / len(values) for values in zip(*features, strict=True))
    scale = tuple(
        sqrt(sum((value - center) ** 2 for value in values) / len(values)) or 1.0
        for values, center in zip(zip(*features, strict=True), mean, strict=True)
    )
    return mean, scale


def _normalize(feature: list[float], mean: tuple[float, ...], scale: tuple[float, ...]) -> list[float]:
    if len(feature) != len(mean):
        raise ValueError("KNN VLA feature length mismatch")
    return [(value - center) / width for value, center, width in zip(feature, mean, scale, strict=True)]


def _sample_action(sample: JSON_OBJECT) -> list[list[float | int]]:
    action = sample.get("action")
    if not isinstance(action, list) or not action:
        raise ValueError("invalid KNN VLA training action")
    return [_action_vector(command) for command in action]


def _action_vector(command: object) -> list[float | int]:
    if (
        not isinstance(command, list)
        or len(command) != 4
        or type(command[3]) is not int
        or command[3] <= 0
    ):
        raise ValueError("invalid KNN VLA action vector")
    return [*(_float(value) for value in command[:3]), command[3]]


def _action_commands(action: list[list[float | int]]) -> list[JSON_OBJECT]:
    return [
        {"vx": command[0], "vy": command[1], "yaw_rate": command[2], "duration_ms": command[3]}
        for command in action
    ]


def _checkpoint_sample(value: object) -> JSON_OBJECT:
    sample = _object(value)
    if set(sample) != {"feature", "action"}:
        raise ValueError("invalid KNN VLA checkpoint sample")
    return {
        "feature": _float_vector(sample["feature"], len(FEATURE_NAMES)),
        "action": [_action_vector(command) for command in _list(sample["action"])],
    }


def _load_manifest(path: Path) -> JSON_OBJECT:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("format") != "synapse2action.vla_dataset":
        raise ValueError("invalid VLA dataset manifest")
    splits = _object(manifest.get("splits"))
    for split in ("train", "validation"):
        split_metadata = _object(splits.get(split))
        if not isinstance(split_metadata.get("file"), str):
            raise ValueError("invalid VLA dataset split")
    return manifest


def _load_jsonl(path: Path) -> list[JSON_OBJECT]:
    return [_json_object(line.encode()) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _json_object(payload: bytes) -> JSON_OBJECT:
    value = json.loads(payload)
    return _object(value)


def _object(value: object) -> JSON_OBJECT:
    if not isinstance(value, dict):
        raise ValueError("KNN VLA field must be an object")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list) or not value:
        raise ValueError("KNN VLA field must be a non-empty list")
    return value


def _float_vector(value: object, length: int) -> list[float]:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError("KNN VLA vector length mismatch")
    return [_float(item) for item in value]


def _float(value: object) -> float:
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("KNN VLA numeric field is invalid")
    return float(value)
