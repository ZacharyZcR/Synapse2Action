from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .contracts import Action, ExecutionResult


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class SkillContext:
    selected_target: str


@dataclass(frozen=True, slots=True)
class SkillDecision:
    accepted: bool
    reason: str


@dataclass(frozen=True, slots=True)
class SkillSpec:
    name: str
    arguments: Mapping[str, type]
    timeout_ms: int
    risk: RiskLevel
    precondition: Callable[[Action, SkillContext], str | None]
    success_condition: Callable[[ExecutionResult], bool]


class SkillRegistry:
    def __init__(self, specs: list[SkillSpec]) -> None:
        self._specs = MappingProxyType({spec.name: spec for spec in specs})

    def validate(self, action: Action, context: SkillContext) -> SkillDecision:
        spec = self._specs.get(action.skill)
        if spec is None:
            return SkillDecision(False, f"unknown skill: {action.skill}")
        expected = set(spec.arguments)
        supplied = set(action.arguments)
        if supplied != expected:
            return SkillDecision(False, "skill arguments do not match schema")
        for name, expected_type in spec.arguments.items():
            if not isinstance(action.arguments[name], expected_type):
                return SkillDecision(False, f"invalid type for argument: {name}")
        failure = spec.precondition(action, context)
        if failure:
            return SkillDecision(False, failure)
        return SkillDecision(True, "skill valid")

    def evaluate(self, action: Action, result: ExecutionResult) -> SkillDecision:
        spec = self._specs[action.skill]
        if result.duration_ms > spec.timeout_ms:
            return SkillDecision(False, "skill timeout")
        if not spec.success_condition(result):
            return SkillDecision(False, "skill success condition failed")
        return SkillDecision(True, "skill result valid")


def _pick_and_place_precondition(action: Action, context: SkillContext) -> str | None:
    if action.arguments["target"] != context.selected_target:
        return "planner changed selected target"
    if not action.arguments["destination"]:
        return "destination is empty"
    return None


def _navigate_to_precondition(action: Action, context: SkillContext) -> str | None:
    if action.arguments["destination"] != context.selected_target:
        return "planner changed selected destination"
    return None


def default_skill_registry() -> SkillRegistry:
    return SkillRegistry(
        [
            SkillSpec(
                "pick_and_place",
                MappingProxyType({"target": str, "destination": str}),
                timeout_ms=5_000,
                risk=RiskLevel.MEDIUM,
                precondition=_pick_and_place_precondition,
                success_condition=lambda result: bool(result.process_compliance),
            ),
            SkillSpec(
                "navigate_to",
                MappingProxyType({"destination": str}),
                timeout_ms=30_000,
                risk=RiskLevel.MEDIUM,
                precondition=_navigate_to_precondition,
                success_condition=lambda result: bool(result.process_compliance),
            ),
        ]
    )
