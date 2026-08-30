from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .contracts import ExecutionResult


class FailureClass(StrEnum):
    OUTCOME_NOT_REACHED = "outcome_not_reached"
    PROCESS_NONCOMPLIANT = "process_noncompliant"
    SAFETY_VIOLATION = "safety_violation"


@dataclass(frozen=True, slots=True)
class RecoveryProposal:
    failure_class: FailureClass
    allowed_skills: tuple[str, ...]
    requires_confirmation: bool
    automatic_execution: bool
    remaining_attempts: int


class BoundedRecoveryPolicy:
    _ALLOWLIST = {
        FailureClass.OUTCOME_NOT_REACHED: ("reobserve", "retry_confirmed_plan"),
        FailureClass.PROCESS_NONCOMPLIANT: ("reobserve",),
        FailureClass.SAFETY_VIOLATION: (),
    }

    def __init__(self, *, maximum_attempts: int = 1) -> None:
        if maximum_attempts < 0:
            raise ValueError("maximum recovery attempts must be non-negative")
        self.maximum_attempts = maximum_attempts

    def propose(self, result: ExecutionResult, *, attempts: int = 0) -> RecoveryProposal:
        if result.success:
            raise ValueError("successful execution does not need recovery")
        if attempts < 0:
            raise ValueError("recovery attempts must be non-negative")
        failure_class = self.classify(result)
        remaining = max(0, self.maximum_attempts - attempts)
        allowed = self._ALLOWLIST[failure_class] if remaining else ()
        return RecoveryProposal(
            failure_class=failure_class,
            allowed_skills=allowed,
            requires_confirmation=bool(allowed),
            automatic_execution=False,
            remaining_attempts=remaining,
        )

    @staticmethod
    def classify(result: ExecutionResult) -> FailureClass:
        if not result.safety_passed:
            return FailureClass.SAFETY_VIOLATION
        if not result.process_compliance:
            return FailureClass.PROCESS_NONCOMPLIANT
        return FailureClass.OUTCOME_NOT_REACHED
