from __future__ import annotations

from base64 import b64decode
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

from .vla_episode import VLAEpisode, load_episode


JSON_OBJECT = dict[str, object]


def export_dataset(
    episode_paths: list[Path],
    output_directory: Path,
    validation_fraction: float = 0.2,
    *,
    validation_sources: set[str] | None = None,
) -> JSON_OBJECT:
    if not episode_paths:
        raise ValueError("at least one VLA episode is required")
    if not 0 <= validation_fraction < 1:
        raise ValueError("validation fraction must be in [0, 1)")

    episodes = []
    seen = set()
    for path in episode_paths:
        episode = load_episode(path)
        episode_id = _episode_id(episode)
        if episode_id in seen:
            raise ValueError("duplicate VLA episode content")
        seen.add(episode_id)
        episodes.append((episode_id, path.name, episode))
    episodes.sort(key=lambda item: item[0])

    if validation_sources is None:
        validation_count = 0
        if len(episodes) > 1 and validation_fraction > 0:
            validation_count = max(1, min(len(episodes) - 1, round(len(episodes) * validation_fraction)))
        validation_ids = {episode_id for episode_id, _, _ in episodes[:validation_count]}
        split_strategy = "episode_hash_fraction"
    else:
        sources = [source for _, source, _ in episodes]
        if len(set(sources)) != len(sources):
            raise ValueError("explicit VLA split requires unique episode source names")
        unknown = validation_sources - set(sources)
        if unknown:
            raise ValueError(f"validation episode source not found: {sorted(unknown)[0]}")
        if not validation_sources or len(validation_sources) == len(episodes):
            raise ValueError("explicit VLA split requires non-empty train and validation sets")
        validation_ids = {
            episode_id for episode_id, source, _ in episodes if source in validation_sources
        }
        split_strategy = "explicit_episode_sources"
    samples = {"train": [], "validation": []}
    split_episodes = {"train": [], "validation": []}

    for episode_id, source, episode in episodes:
        split = "validation" if episode_id in validation_ids else "train"
        split_episodes[split].append(episode_id)
        samples[split].extend(_episode_samples(episode_id, split, episode))

    output_directory.mkdir(parents=True, exist_ok=True)
    for split in ("train", "validation"):
        _write_jsonl(output_directory / f"{split}.jsonl", samples[split])

    manifest: JSON_OBJECT = {
        "schema_version": 1,
        "format": "synapse2action.vla_dataset",
        "episode_count": len(episodes),
        "sample_count": sum(len(values) for values in samples.values()),
        "validation_fraction": len(validation_ids) / len(episodes),
        "split_strategy": split_strategy,
        "features": {
            "instruction": "string",
            "camera": {"encoding": "mono8", "storage": "base64"},
            "obstacles": ["x", "y", "radius"],
            "state": ["x", "y", "yaw", "vx", "vy", "yaw_rate"],
            "goal": ["x", "y", "yaw"],
            "action": ["vx", "vy", "yaw_rate", "duration_ms"],
        },
        "episodes": [
            {"episode_id": episode_id, "source": source, "steps": len(episode.steps)}
            for episode_id, source, episode in episodes
        ],
        "splits": {
            split: {
                "file": f"{split}.jsonl",
                "episodes": split_episodes[split],
                "samples": len(samples[split]),
            }
            for split in ("train", "validation")
        },
    }
    (output_directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _episode_id(episode: VLAEpisode) -> str:
    content = {"task": episode.task, "steps": list(episode.steps)}
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return sha256(encoded).hexdigest()


def _episode_samples(episode_id: str, split: str, episode: VLAEpisode) -> list[JSON_OBJECT]:
    task_envelope = _object(episode.task)
    if set(task_envelope) != {"schema_version", "task"}:
        raise ValueError("invalid VLA episode task envelope")
    task = _object(task_envelope.get("task"))
    if set(task) != {"instruction", "goal"}:
        raise ValueError("invalid VLA episode task")
    instruction = task.get("instruction")
    goal = _pose(task.get("goal"))
    if task_envelope.get("schema_version") != 1 or not isinstance(instruction, str):
        raise ValueError("invalid VLA episode task")

    samples = []
    for index, recorded_step in enumerate(episode.steps):
        observation = _object(recorded_step.get("observation"))
        action = _object(recorded_step.get("action"))
        if set(observation) != {"schema_version", "task", "step", "sensor"}:
            raise ValueError("invalid VLA episode observation")
        if observation.get("schema_version") != 1 or observation.get("step") != index:
            raise ValueError("invalid VLA episode observation sequence")
        if observation.get("task") != task:
            raise ValueError("VLA episode task changed within trajectory")
        sensor = _object(observation.get("sensor"))
        if set(sensor) != {"frame_id", "captured_at_ms", "pose", "camera", "proprioception", "obstacles"}:
            raise ValueError("invalid VLA episode sensor frame")
        if sensor.get("frame_id") != index or type(sensor.get("captured_at_ms")) is not int:
            raise ValueError("invalid VLA episode frame sequence")
        pose = _pose(sensor.get("pose"))
        proprioception = _object(sensor.get("proprioception"))
        if set(proprioception) != {"vx", "vy", "yaw_rate"}:
            raise ValueError("invalid VLA episode proprioception")
        camera = _camera(sensor.get("camera"))
        obstacles = _obstacles(sensor.get("obstacles"))
        commands = _commands(action)
        samples.append(
            {
                "schema_version": 1,
                "episode_id": episode_id,
                "split": split,
                "step_index": index,
                "instruction": instruction,
                "observation": {
                    "frame_id": sensor.get("frame_id"),
                    "timestamp_ms": sensor.get("captured_at_ms"),
                    "camera": camera,
                    "obstacles": obstacles,
                    "state": [
                        *pose,
                        *(_number(proprioception.get(name)) for name in ("vx", "vy", "yaw_rate")),
                    ],
                    "goal": goal,
                },
                "action": commands,
            }
        )
    return samples


def _obstacles(value: object) -> list[JSON_OBJECT]:
    if not isinstance(value, list):
        raise ValueError("invalid VLA dataset obstacles")
    obstacles = []
    expected = {"obstacle_id", "x", "y", "radius", "active_from_ms", "active_until_ms"}
    for item in value:
        obstacle = _object(item)
        if set(obstacle) != expected or not isinstance(obstacle["obstacle_id"], str):
            raise ValueError("invalid VLA dataset obstacle")
        radius = _number(obstacle["radius"])
        if radius <= 0:
            raise ValueError("invalid VLA dataset obstacle radius")
        obstacles.append(
            {
                "obstacle_id": obstacle["obstacle_id"],
                "x": _number(obstacle["x"]),
                "y": _number(obstacle["y"]),
                "radius": radius,
            }
        )
    return obstacles


def _camera(value: object) -> JSON_OBJECT:
    camera = _object(value)
    required = {"width", "height", "encoding", "data_base64"}
    if (
        set(camera) != required
        or type(camera["width"]) is not int
        or type(camera["height"]) is not int
        or camera["width"] <= 0
        or camera["height"] <= 0
    ):
        raise ValueError("invalid VLA dataset camera")
    if camera["encoding"] != "mono8" or not isinstance(camera["data_base64"], str):
        raise ValueError("unsupported VLA dataset camera")
    try:
        data = b64decode(camera["data_base64"], validate=True)
    except ValueError as exc:
        raise ValueError("invalid VLA dataset camera bytes") from exc
    if len(data) != camera["width"] * camera["height"]:
        raise ValueError("VLA dataset camera size mismatch")
    return camera


def _commands(action: JSON_OBJECT) -> list[list[float | int]]:
    if set(action) != {"schema_version", "commands"} or action.get("schema_version") != 1:
        raise ValueError("invalid VLA dataset action")
    if not isinstance(action.get("commands"), list) or not action["commands"]:
        raise ValueError("VLA dataset action chunk must not be empty")
    values = []
    for command_value in action["commands"]:
        command = _object(command_value)
        if set(command) != {"vx", "vy", "yaw_rate", "duration_ms"}:
            raise ValueError("invalid VLA dataset command")
        duration = command["duration_ms"]
        if type(duration) is not int or duration <= 0:
            raise ValueError("invalid VLA dataset action duration")
        values.append([*(_number(command[name]) for name in ("vx", "vy", "yaw_rate")), duration])
    return values


def _pose(value: object) -> list[float]:
    pose = _object(value)
    if set(pose) != {"x", "y", "yaw"}:
        raise ValueError("invalid VLA dataset pose")
    return [_number(pose[name]) for name in ("x", "y", "yaw")]


def _object(value: object) -> JSON_OBJECT:
    if not isinstance(value, dict):
        raise ValueError("VLA dataset field must be an object")
    return value


def _number(value: object) -> float:
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("VLA dataset numeric field is invalid")
    return float(value)


def _write_jsonl(path: Path, samples: list[JSON_OBJECT]) -> None:
    lines = [json.dumps(sample, sort_keys=True, separators=(",", ":"), allow_nan=False) for sample in samples]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
