from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import Action, ExecutionResult


@dataclass(slots=True)
class MockPlanner:
    skill: str = "pick_and_place"

    def plan(self, target: str) -> Action:
        return Action(self.skill, {"target": target, "destination": "drop_zone"})


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
