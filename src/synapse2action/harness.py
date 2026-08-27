from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import Intent, IntentKind, Planner, Robot, TaskState, TraceRecord, Verifier


class InvalidTransition(ValueError):
    pass


@dataclass(slots=True)
class Harness:
    planner: Planner
    robot: Robot
    verifier: Verifier
    state: TaskState = TaskState.IDLE
    target: str | None = None
    trace: list[TraceRecord] = field(default_factory=list)
    allowed_skills: frozenset[str] = frozenset({"pick_and_place"})

    def handle(self, intent: Intent) -> TaskState:
        if intent.kind is IntentKind.STOP:
            self.robot.stop()
            return self._transition(TaskState.EMERGENCY_STOPPED, "stop", "global stop")

        if intent.kind is IntentKind.CANCEL:
            self._require(TaskState.AWAITING_CONFIRMATION, TaskState.ARMED)
            self.target = None
            return self._transition(TaskState.CANCELLED, "cancel")

        if intent.kind is IntentKind.SELECT:
            self._require(TaskState.IDLE, TaskState.CANCELLED, TaskState.COMPLETED, TaskState.FAILED)
            if not intent.target:
                raise ValueError("select intent requires a target")
            self.target = intent.target
            self._transition(TaskState.TARGET_SELECTED, "select", intent.target)
            return self._transition(TaskState.AWAITING_CONFIRMATION, "await_confirmation")

        if intent.kind is IntentKind.CONFIRM:
            self._require(TaskState.AWAITING_CONFIRMATION)
            return self._execute_confirmed_target()

        raise ValueError(f"unsupported intent: {intent.kind}")

    def _execute_confirmed_target(self) -> TaskState:
        assert self.target is not None
        self._transition(TaskState.ARMED, "confirm", self.target)
        action = self.planner.plan(self.target)
        if action.skill not in self.allowed_skills:
            return self._transition(TaskState.FAILED, "reject_plan", f"unknown skill: {action.skill}")
        required = {"target", "destination"}
        if not required.issubset(action.arguments):
            return self._transition(TaskState.FAILED, "reject_plan", "invalid skill arguments")
        self._transition(TaskState.EXECUTING, "execute", action.skill)
        result = self.robot.execute(action)
        self._transition(TaskState.VERIFYING, "verify", result.detail)
        final_state = TaskState.COMPLETED if self.verifier.verify(result) else TaskState.FAILED
        return self._transition(final_state, "result", result.detail)

    def _require(self, *allowed: TaskState) -> None:
        if self.state not in allowed:
            expected = ", ".join(state.value for state in allowed)
            raise InvalidTransition(f"{self.state.value} does not allow this intent; expected {expected}")

    def _transition(self, state: TaskState, event: str, detail: str = "") -> TaskState:
        self.state = state
        self.trace.append(TraceRecord(len(self.trace) + 1, event, state, detail))
        return state
