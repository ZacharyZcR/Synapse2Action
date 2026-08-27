from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from .vla import VLAInferenceBackend


JSON_OBJECT = dict[str, object]


@dataclass(frozen=True, slots=True)
class VLAEpisode:
    task: JSON_OBJECT
    steps: tuple[JSON_OBJECT, ...]
    backend: str
    schema_version: int = 1

    def to_dict(self) -> JSON_OBJECT:
        return {
            "schema_version": self.schema_version,
            "format": "synapse2action.vla_episode",
            "backend": self.backend,
            "task": self.task,
            "steps": list(self.steps),
        }


@dataclass(slots=True)
class RecordingVLABackend:
    backend: VLAInferenceBackend
    task: JSON_OBJECT | None = None
    steps: list[JSON_OBJECT] = field(default_factory=list)

    @property
    def replan_count(self) -> int | None:
        return getattr(self.backend, "replan_count", None)

    @property
    def request_count(self) -> int | None:
        return getattr(self.backend, "request_count", None)

    def reset(self, task_payload: bytes) -> None:
        self.task = _json_object(task_payload)
        self.steps.clear()
        self.backend.reset(task_payload)

    def infer(self, observation_payload: bytes) -> bytes:
        response = self.backend.infer(observation_payload)
        self.steps.append(
            {
                "index": len(self.steps),
                "observation": _json_object(observation_payload),
                "action": _json_object(response),
            }
        )
        return response

    def episode(self) -> VLAEpisode:
        if self.task is None:
            raise ValueError("VLA episode has no task")
        return VLAEpisode(self.task, tuple(self.steps), type(self.backend).__name__)


@dataclass(slots=True)
class ReplayVLABackend:
    episode: VLAEpisode
    index: int = 0
    request_count: int = 0

    def reset(self, task_payload: bytes) -> None:
        if _json_object(task_payload) != self.episode.task:
            raise ValueError("replay task does not match recorded episode")
        self.index = 0
        self.request_count = 1

    def infer(self, observation_payload: bytes) -> bytes:
        if self.index >= len(self.episode.steps):
            raise ValueError("replay episode is exhausted")
        step = self.episode.steps[self.index]
        if step["index"] != self.index or step["observation"] != _json_object(observation_payload):
            raise ValueError(f"replay observation diverged at step {self.index}")
        self.index += 1
        self.request_count += 1
        return _json_bytes(step["action"])

    def assert_complete(self) -> None:
        if self.index != len(self.episode.steps):
            raise ValueError("replay did not consume the complete episode")


def save_episode(path: Path, episode: VLAEpisode) -> None:
    path.write_text(json.dumps(episode.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_episode(path: Path) -> VLAEpisode:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "format", "backend", "task", "steps"}:
        raise ValueError("VLA episode does not match schema")
    if payload["schema_version"] != 1 or payload["format"] != "synapse2action.vla_episode":
        raise ValueError("unsupported VLA episode format")
    if not isinstance(payload["backend"], str) or not isinstance(payload["task"], dict):
        raise ValueError("invalid VLA episode metadata")
    if not isinstance(payload["steps"], list):
        raise ValueError("VLA episode steps must be a list")
    steps = tuple(_validate_step(step, index) for index, step in enumerate(payload["steps"]))
    return VLAEpisode(payload["task"], steps, payload["backend"])


def _validate_step(step: object, index: int) -> JSON_OBJECT:
    if not isinstance(step, dict) or set(step) != {"index", "observation", "action"}:
        raise ValueError("VLA episode step does not match schema")
    if step["index"] != index or not isinstance(step["observation"], dict) or not isinstance(step["action"], dict):
        raise ValueError("invalid VLA episode step")
    return step


def _json_object(payload: bytes) -> JSON_OBJECT:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("VLA episode payload is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("VLA episode payload must be an object")
    return value


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
