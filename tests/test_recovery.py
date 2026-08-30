import unittest

from synapse2action.contracts import ExecutionResult
from synapse2action.recovery import BoundedRecoveryPolicy, FailureClass


class RecoveryPolicyTests(unittest.TestCase):
    def test_attempt_budget_removes_every_recovery_skill(self) -> None:
        policy = BoundedRecoveryPolicy(maximum_attempts=1)
        result = ExecutionResult(
            False,
            "missed",
            outcome_success=False,
            process_compliance=True,
            safety_passed=True,
        )

        proposal = policy.propose(result, attempts=1)

        self.assertEqual(proposal.failure_class, FailureClass.OUTCOME_NOT_REACHED)
        self.assertEqual(proposal.allowed_skills, ())
        self.assertEqual(proposal.remaining_attempts, 0)
        self.assertFalse(proposal.requires_confirmation)

    def test_successful_result_cannot_create_recovery(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not need recovery"):
            BoundedRecoveryPolicy().propose(ExecutionResult(True, "done"))


if __name__ == "__main__":
    unittest.main()
