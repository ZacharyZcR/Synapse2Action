from __future__ import annotations

from dataclasses import dataclass, field, replace

from .authorization import ChallengeStore
from .components import ScriptedPolicy
from .contracts import Action, ExecutionResult, Intent, IntentKind, Planner, PlannerRefused, Policy, Robot, TaskState, TraceRecord, Verifier
from .skills import SkillContext, SkillRegistry, default_skill_registry
from .recovery import BoundedRecoveryPolicy, RecoveryProposal
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
    pending_action: Action | None = None
    last_result: ExecutionResult | None = None
    recovery_policy: BoundedRecoveryPolicy = field(default_factory=BoundedRecoveryPolicy)
    last_recovery: RecoveryProposal | None = None
    recovery_history: list[RecoveryProposal] = field(default_factory=list)
    last_confirmed_action: Action | None = None
    recovery_attempts: int = 0

    def handle(self, intent: Intent) -> TaskState:
        if intent.kind is IntentKind.STOP:
            if self.authorizer:
                self.authorizer.revoke()
            self.pending_action = None
            self.last_recovery = None
            self.last_confirmed_action = None
            self.challenge_token = None
            self.robot.stop()
            return self._transition(TaskState.EMERGENCY_STOPPED, "stop", "global stop")

        if intent.kind is IntentKind.CANCEL:
            self._require(
                TaskState.AWAITING_CONFIRMATION,
                TaskState.AWAITING_RECOVERY_CONFIRMATION,
                TaskState.ARMED,
            )
            if self.authorizer:
                self.authorizer.revoke()
            self.target = None
            self.target_revision = None
            self.challenge_token = None
            self.pending_action = None
            self.last_recovery = None
            self.last_confirmed_action = None
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
            self.last_recovery = None
            self.last_confirmed_action = None
            self.recovery_attempts = 0
            self.recovery_history.clear()
            self.target_revision = intent.target_revision
            self._transition(TaskState.TARGET_SELECTED, "select", intent.target)
            planned_action = self._plan_selected_target()
            if planned_action is None:
                return self.state
            self.pending_action = planned_action
            if self.authorizer:
                assert intent.target_revision is not None and intent.at_ms is not None
                challenge = self.authorizer.issue(intent.target, intent.target_revision, intent.at_ms)
                self.challenge_token = challenge.token
                self._transition(TaskState.TARGET_SELECTED, "issue_challenge", challenge.token)
            return self._transition(TaskState.AWAITING_CONFIRMATION, "await_confirmation")

        if intent.kind is IntentKind.CONFIRM:
            self._require(
                TaskState.AWAITING_CONFIRMATION,
                TaskState.AWAITING_RECOVERY_CONFIRMATION,
            )
            confirmation_state = self.state
            if self.world:
                if self.target_revision is None or intent.at_ms is None:
                    self._transition(confirmation_state, "reject_world", "missing world context")
                    return self.state
                if intent.target_revision != self.target_revision:
                    self._transition(
                        confirmation_state,
                        "reject_world",
                        "target revision changed",
                    )
                    return self.state
                assert self.target is not None
                decision = self.world.validate(self.target, self.target_revision, intent.at_ms)
                if not decision.accepted:
                    self._transition(confirmation_state, "reject_world", decision.reason)
                    return self.state
            if self.authorizer:
                if intent.challenge_token is None or intent.target_revision is None or intent.at_ms is None:
                    self._transition(
                        confirmation_state,
                        "reject_confirmation",
                        "missing challenge context",
                    )
                    return self.state
                assert self.target is not None
                decision = self.authorizer.consume(
                    intent.challenge_token, self.target, intent.target_revision, intent.at_ms
                )
                if not decision.accepted:
                    self._transition(confirmation_state, "reject_confirmation", decision.reason)
                    return self.state
                self.challenge_token = None
            return self._execute_confirmed_target(
                recovery=confirmation_state is TaskState.AWAITING_RECOVERY_CONFIRMATION
            )

        raise ValueError(f"unsupported intent: {intent.kind}")

    def request_recovery(
        self,
        *,
        target_revision: int | None = None,
        at_ms: int | None = None,
    ) -> TaskState:
        self._require(TaskState.FAILED)
        proposal = self.last_recovery
        if (
            proposal is None
            or "retry_confirmed_plan" not in proposal.allowed_skills
            or self.last_confirmed_action is None
        ):
            raise InvalidTransition("failed execution has no retryable recovery proposal")
        if self.world:
            if target_revision is None or at_ms is None:
                raise ValueError("recovery requires a fresh world revision and timestamp")
            assert self.target is not None
            decision = self.world.validate(self.target, target_revision, at_ms)
            if not decision.accepted:
                self._transition(TaskState.FAILED, "reject_recovery_world", decision.reason)
                return self.state
            self.target_revision = target_revision
        if self.authorizer:
            if target_revision is None or at_ms is None:
                raise ValueError("authorized recovery requires world revision and timestamp")
            if self.world is None and target_revision != self.target_revision:
                self._transition(
                    TaskState.FAILED,
                    "reject_recovery_world",
                    "target revision changed",
                )
                return self.state
            assert self.target is not None
            challenge = self.authorizer.issue(self.target, target_revision, at_ms)
            self.challenge_token = challenge.token
            self._transition(TaskState.FAILED, "issue_recovery_challenge", challenge.token)
        self.pending_action = self.last_confirmed_action
        return self._transition(
            TaskState.AWAITING_RECOVERY_CONFIRMATION,
            "await_recovery_confirmation",
            proposal.failure_class.value,
        )

    def _execute_confirmed_target(self, *, recovery: bool = False) -> TaskState:
        assert self.target is not None
        assert self.pending_action is not None
        planned_action = self.pending_action
        self.pending_action = None
        if recovery:
            self.recovery_attempts += 1
        else:
            self.last_confirmed_action = planned_action
        self._transition(
            TaskState.ARMED,
            "confirm_recovery" if recovery else "confirm",
            planned_action.skill,
        )
        action = self.policy.prepare(planned_action)
        decision = self.skills.validate(action, SkillContext(self.target))
        if not decision.accepted:
            self.last_result = ExecutionResult(
                False,
                decision.reason,
                outcome_success=False,
                process_compliance=False,
                safety_passed=True,
            )
            self.last_recovery = self._record_recovery(self.last_result)
            return self._transition(TaskState.FAILED, "reject_policy", decision.reason)
        self._transition(TaskState.ARMED, "policy", f"{action.skill}:{len(action.steps)}_steps")
        self._transition(TaskState.EXECUTING, "execute", action.skill)
        result = self.robot.execute(action)
        self._transition(TaskState.VERIFYING, "verify", result.detail)
        skill_result = self.skills.evaluate(action, result)
        if not skill_result.accepted and skill_result.reason == "skill timeout":
            self.robot.stop()
        outcome_success = self.verifier.verify(result)
        process_compliance = skill_result.accepted
        safety_passed = bool(result.safety_passed)
        success = outcome_success and process_compliance and safety_passed
        self.last_result = replace(
            result,
            success=success,
            outcome_success=outcome_success,
            process_compliance=process_compliance,
            safety_passed=safety_passed,
        )
        final_state = TaskState.COMPLETED if success else TaskState.FAILED
        self.last_recovery = (
            None
            if success
            else self._record_recovery(self.last_result)
        )
        detail = result.detail
        if not process_compliance:
            detail = skill_result.reason
        elif not safety_passed:
            detail = "safety gate failed"
        return self._transition(final_state, "result", detail)

    def _record_recovery(self, result: ExecutionResult) -> RecoveryProposal:
        proposal = self.recovery_policy.propose(
            result,
            attempts=self.recovery_attempts,
        )
        self.recovery_history.append(proposal)
        return proposal

    def _plan_selected_target(self) -> Action | None:
        assert self.target is not None
        try:
            planned_action = self.planner.plan(self.target)
        except PlannerRefused as exc:
            self._transition(TaskState.FAILED, "planner_refusal", str(exc))
            return None
        except Exception as exc:
            self._transition(TaskState.FAILED, "planner_failure", type(exc).__name__)
            return None
        decision = self.skills.validate(planned_action, SkillContext(self.target))
        if not decision.accepted:
            self._transition(TaskState.FAILED, "reject_plan", decision.reason)
            return None
        self._transition(TaskState.TARGET_SELECTED, "plan", planned_action.skill)
        return planned_action

    def _require(self, *allowed: TaskState) -> None:
        if self.state not in allowed:
            expected = ", ".join(state.value for state in allowed)
            raise InvalidTransition(f"{self.state.value} does not allow this intent; expected {expected}")

    def _transition(self, state: TaskState, event: str, detail: str = "") -> TaskState:
        self.state = state
        self.trace.append(TraceRecord(len(self.trace) + 1, event, state, detail))
        return state
