from __future__ import annotations

from dataclasses import dataclass, field

from .authorization import ChallengeStore
from .components import ScriptedPolicy
from .contracts import Intent, IntentKind, Planner, Policy, Robot, TaskState, TraceRecord, Verifier
from .skills import SkillContext, SkillRegistry, default_skill_registry
from .world import FakeWorld


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
    skills: SkillRegistry = field(default_factory=default_skill_registry)
    authorizer: ChallengeStore | None = None
    target_revision: int | None = None
    challenge_token: str | None = None
    world: FakeWorld | None = None
    policy: Policy = field(default_factory=ScriptedPolicy)

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
            if self.world:
                if intent.target_revision is None or intent.at_ms is None:
                    raise ValueError("world selection requires target revision and timestamp")
                decision = self.world.validate(intent.target, intent.target_revision, intent.at_ms)
                if not decision.accepted:
                    raise ValueError(decision.reason)
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
            if self.world:
                if self.target_revision is None or intent.at_ms is None:
                    self._transition(TaskState.AWAITING_CONFIRMATION, "reject_world", "missing world context")
                    return self.state
                assert self.target is not None
                decision = self.world.validate(self.target, self.target_revision, intent.at_ms)
                if not decision.accepted:
                    self._transition(TaskState.AWAITING_CONFIRMATION, "reject_world", decision.reason)
                    return self.state
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
        try:
            planned_action = self.planner.plan(self.target)
        except Exception as exc:
            return self._transition(TaskState.FAILED, "planner_failure", type(exc).__name__)
        decision = self.skills.validate(planned_action, SkillContext(self.target))
        if not decision.accepted:
            return self._transition(TaskState.FAILED, "reject_plan", decision.reason)
        self._transition(TaskState.ARMED, "plan", planned_action.skill)
        action = self.policy.prepare(planned_action)
        decision = self.skills.validate(action, SkillContext(self.target))
        if not decision.accepted:
            return self._transition(TaskState.FAILED, "reject_policy", decision.reason)
        self._transition(TaskState.ARMED, "policy", f"{action.skill}:{len(action.steps)}_steps")
        self._transition(TaskState.EXECUTING, "execute", action.skill)
        result = self.robot.execute(action)
        self._transition(TaskState.VERIFYING, "verify", result.detail)
        skill_result = self.skills.evaluate(action, result)
        if not skill_result.accepted and skill_result.reason == "skill timeout":
            self.robot.stop()
        verified = skill_result.accepted and self.verifier.verify(result)
        final_state = TaskState.COMPLETED if verified else TaskState.FAILED
        detail = result.detail if verified else skill_result.reason
        return self._transition(final_state, "result", detail)

    def _require(self, *allowed: TaskState) -> None:
        if self.state not in allowed:
            expected = ", ".join(state.value for state in allowed)
            raise InvalidTransition(f"{self.state.value} does not allow this intent; expected {expected}")

    def _transition(self, state: TaskState, event: str, detail: str = "") -> TaskState:
        self.state = state
        self.trace.append(TraceRecord(len(self.trace) + 1, event, state, detail))
        return state
