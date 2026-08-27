from __future__ import annotations

from dataclasses import dataclass, field

from .authorization import ChallengeStore
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
    authorizer: ChallengeStore | None = None
    target_revision: int | None = None
    challenge_token: str | None = None

    def handle(self, intent: Intent) -> TaskState:
        if intent.kind is IntentKind.STOP:
            if self.authorizer:
                self.authorizer.revoke()
            self.robot.stop()
            return self._transition(TaskState.EMERGENCY_STOPPED, "stop", "global stop")

        if intent.kind is IntentKind.CANCEL:
            self._require(TaskState.AWAITING_CONFIRMATION, TaskState.ARMED)
            if self.authorizer:
                self.authorizer.revoke()
            self.target = None
            self.target_revision = None
            self.challenge_token = None
            return self._transition(TaskState.CANCELLED, "cancel")

        if intent.kind is IntentKind.SELECT:
            self._require(TaskState.IDLE, TaskState.CANCELLED, TaskState.COMPLETED, TaskState.FAILED)
            if not intent.target:
                raise ValueError("select intent requires a target")
            if self.authorizer and (intent.target_revision is None or intent.at_ms is None):
                raise ValueError("authorized selection requires target revision and timestamp")
            self.target = intent.target
            self.target_revision = intent.target_revision
            self._transition(TaskState.TARGET_SELECTED, "select", intent.target)
            if self.authorizer:
                assert intent.target_revision is not None and intent.at_ms is not None
                challenge = self.authorizer.issue(intent.target, intent.target_revision, intent.at_ms)
                self.challenge_token = challenge.token
                self._transition(TaskState.TARGET_SELECTED, "issue_challenge", challenge.token)
            return self._transition(TaskState.AWAITING_CONFIRMATION, "await_confirmation")

        if intent.kind is IntentKind.CONFIRM:
            self._require(TaskState.AWAITING_CONFIRMATION)
            if self.authorizer:
                if intent.challenge_token is None or intent.target_revision is None or intent.at_ms is None:
                    self._transition(TaskState.AWAITING_CONFIRMATION, "reject_confirmation", "missing challenge context")
                    return self.state
                assert self.target is not None
                decision = self.authorizer.consume(
                    intent.challenge_token, self.target, intent.target_revision, intent.at_ms
                )
                if not decision.accepted:
                    self._transition(TaskState.AWAITING_CONFIRMATION, "reject_confirmation", decision.reason)
                    return self.state
                self.challenge_token = None
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
