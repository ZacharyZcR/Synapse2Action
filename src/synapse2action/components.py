from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .contracts import Action, ExecutionResult


@dataclass(slots=True)
class MockPlanner:
    skill: str = "pick_and_place"
    arguments: Mapping[str, Any] | None = None

    def plan(self, target: str) -> Action:
        arguments = self.arguments or {"target": target, "destination": "drop_zone"}
        return Action(self.skill, arguments)


@dataclass(slots=True)
class ScriptedPolicy:
    prepared: list[Action] = field(default_factory=list)

    def prepare(self, action: Action) -> Action:
        self.prepared.append(action)
        return action


@dataclass(slots=True)
class FakeRobot:
    allowed_skills: frozenset[str] = frozenset({"pick_and_place"})
    result: ExecutionResult = ExecutionResult(True, "simulated action completed")
    executed: list[Action] = field(default_factory=list)
    stopped: bool = False

    def execute(self, action: Action) -> ExecutionResult:
        if self.stopped:
            return ExecutionResult(False, "robot is stopped")
        if action.skill not in self.allowed_skills:
            return ExecutionResult(False, f"unknown skill: {action.skill}")
        self.executed.append(action)
        return self.result

    def stop(self) -> None:
        self.stopped = True


class RuleBasedVerifier:
    def verify(self, result: ExecutionResult) -> bool:
        return result.success
