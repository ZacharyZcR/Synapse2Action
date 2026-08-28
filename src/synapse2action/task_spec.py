from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping


def _tuple(values: Any, length: int, label: str) -> tuple[float, ...]:
    if not isinstance(values, list) or len(values) != length:
        raise ValueError(f"{label} must contain {length} values")
    return tuple(float(value) for value in values)


@dataclass(frozen=True, slots=True)
class SceneEntity:
    name: str
    position: tuple[float, float, float]
    size: tuple[float, float, float]
    rgba: tuple[float, float, float, float]
    mass: float | None = None


@dataclass(frozen=True, slots=True)
class VerificationSpec:
    minimum_lift_m: float
    minimum_base_height_m: float
    grasp_distance_m: float
    release_height_m: float
    grasp_after_s: float
    release_after_s: float


@dataclass(frozen=True, slots=True)
class ControllerSpec:
    joint_indices: tuple[int, ...]
    joint_limits_rad: tuple[tuple[float, float], ...]
    stand: tuple[float, ...]
    grasp: tuple[float, ...]
    lift: tuple[float, ...]
    transport: tuple[float, ...]
    phase_end_s: tuple[float, float, float, float]
    start_delay_s: float


@dataclass(frozen=True, slots=True)
class TaskSpec:
    task_id: str
    skill: str
    target: str
    destination: str
    instruction: str
    counterfactual_instruction: str
    target_entity: SceneEntity
    destination_entity: SceneEntity
    cameras: Mapping[str, tuple[float, float, float]]
    verification: VerificationSpec
    controller: ControllerSpec
    display: Mapping[str, Mapping[str, str]]

    @property
    def arguments(self) -> dict[str, str]:
        return {"target": self.target, "destination": self.destination}

    def action_text(self) -> str:
        return f"{self.skill}({self.target}, {self.destination})"

    def validate_action(self, skill: str, arguments: Mapping[str, object]) -> None:
        if skill != self.skill or dict(arguments) != self.arguments:
            raise ValueError(f"action does not match task spec {self.task_id}")


def load_task_spec(path: Path) -> TaskSpec:
    raw = json.loads(path.read_text(encoding="utf-8"))
    target = raw["scene"]["target"]
    destination = raw["scene"]["destination"]
    controller = raw["controller"]
    indices = tuple(int(value) for value in controller["joint_indices"])
    poses = {
        name: _tuple(controller[name], len(indices), f"controller.{name}")
        for name in ("stand", "grasp", "lift", "transport")
    }
    spec = TaskSpec(
        task_id=str(raw["task_id"]),
        skill=str(raw["skill"]),
        target=str(raw["arguments"]["target"]),
        destination=str(raw["arguments"]["destination"]),
        instruction=str(raw["vla"]["instruction"]),
        counterfactual_instruction=str(raw["vla"]["counterfactual_instruction"]),
        target_entity=SceneEntity(
            str(target["name"]),
            _tuple(target["position_xyz_m"], 3, "scene.target.position"),
            _tuple(target["half_size_xyz_m"], 3, "scene.target.size"),
            _tuple(target["rgba"], 4, "scene.target.rgba"),
            float(target["mass_kg"]),
        ),
        destination_entity=SceneEntity(
            str(destination["name"]),
            _tuple(destination["position_xyz_m"], 3, "scene.destination.position"),
            _tuple(destination["half_size_xyz_m"], 3, "scene.destination.size"),
            _tuple(destination["rgba"], 4, "scene.destination.rgba"),
        ),
        cameras={
            str(name): _tuple(position, 3, f"scene.cameras.{name}")
            for name, position in raw["scene"]["cameras"].items()
        },
        verification=VerificationSpec(**{
            key: float(value) for key, value in raw["verification"].items()
        }),
        controller=ControllerSpec(
            joint_indices=indices,
            joint_limits_rad=tuple(
                _tuple(limits, 2, "controller.joint_limits_rad")
                for limits in controller["joint_limits_rad"]
            ),
            **poses,
            phase_end_s=_tuple(controller["phase_end_s"], 4, "controller.phase_end_s"),
            start_delay_s=float(controller["start_delay_s"]),
        ),
        display=raw["display"],
    )
    if spec.target_entity.name != spec.target or spec.destination_entity.name != spec.destination:
        raise ValueError("scene entity names must match action arguments")
    if len(spec.controller.joint_limits_rad) != len(spec.controller.joint_indices):
        raise ValueError("controller joint limits must match joint indices")
    if tuple(sorted(spec.controller.phase_end_s)) != spec.controller.phase_end_s:
        raise ValueError("controller phase end times must be ordered")
    if any(end <= start for start, end in zip(spec.controller.phase_end_s, spec.controller.phase_end_s[1:])):
        raise ValueError("controller phases must have positive duration")
    return spec
