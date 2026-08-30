import unittest

from synapse2action.authorization import ChallengeStore
from synapse2action.components import FakeRobot, MockPlanner, RuleBasedVerifier
from synapse2action.contracts import ExecutionResult, Intent, IntentKind, TaskState
from synapse2action.harness import Harness


def make_authorized_harness() -> tuple[Harness, FakeRobot]:
    robot = FakeRobot()
    return Harness(MockPlanner(), robot, RuleBasedVerifier(), authorizer=ChallengeStore()), robot


class AuthorizationTests(unittest.TestCase):
    def test_recovery_issues_a_new_challenge_and_rejects_the_consumed_token(self) -> None:
        class ResultSequenceRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.results = [
                    ExecutionResult(
                        False,
                        "missed",
                        outcome_success=False,
                        process_compliance=True,
                        safety_passed=True,
                    ),
                    ExecutionResult(True, "recovered"),
                ]

            def execute(self, action):
                self.executed.append(action)
                return self.results.pop(0)

        robot = ResultSequenceRobot()
        harness = Harness(
            MockPlanner(),
            robot,
            RuleBasedVerifier(),
            authorizer=ChallengeStore(),
        )
        harness.handle(Intent(IntentKind.SELECT, "red_cube", target_revision=7, at_ms=0))
        original_token = harness.challenge_token
        harness.handle(
            Intent(
                IntentKind.CONFIRM,
                target_revision=7,
                challenge_token=original_token,
                at_ms=500,
            )
        )

        harness.request_recovery(target_revision=7, at_ms=1_000)
        recovery_token = harness.challenge_token
        rejected = harness.handle(
            Intent(
                IntentKind.CONFIRM,
                target_revision=7,
                challenge_token=original_token,
                at_ms=1_100,
            )
        )

        self.assertNotEqual(original_token, recovery_token)
        self.assertEqual(rejected, TaskState.AWAITING_RECOVERY_CONFIRMATION)
        self.assertEqual(len(robot.executed), 1)
        accepted = harness.handle(
            Intent(
                IntentKind.CONFIRM,
                target_revision=7,
                challenge_token=recovery_token,
                at_ms=1_200,
            )
        )
        self.assertEqual(accepted, TaskState.COMPLETED)
        self.assertEqual(len(robot.executed), 2)

    def test_matching_challenge_executes(self) -> None:
        harness, robot = make_authorized_harness()
        harness.handle(Intent(IntentKind.SELECT, "red_cube", target_revision=7, at_ms=0))

        state = harness.handle(
            Intent(IntentKind.CONFIRM, target_revision=7, challenge_token=harness.challenge_token, at_ms=500)
        )

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(len(robot.executed), 1)

    def test_expired_challenge_is_rejected(self) -> None:
        harness, robot = make_authorized_harness()
        harness.handle(Intent(IntentKind.SELECT, "red_cube", target_revision=7, at_ms=0))

        state = harness.handle(
            Intent(IntentKind.CONFIRM, target_revision=7, challenge_token=harness.challenge_token, at_ms=3001)
        )

        self.assertEqual(state, TaskState.AWAITING_CONFIRMATION)
        self.assertEqual(robot.executed, [])

    def test_changed_target_revision_is_rejected(self) -> None:
        harness, robot = make_authorized_harness()
        harness.handle(Intent(IntentKind.SELECT, "red_cube", target_revision=7, at_ms=0))

        state = harness.handle(
            Intent(IntentKind.CONFIRM, target_revision=8, challenge_token=harness.challenge_token, at_ms=500)
        )

        self.assertEqual(state, TaskState.AWAITING_CONFIRMATION)
        self.assertEqual(robot.executed, [])

    def test_consumed_challenge_cannot_be_replayed(self) -> None:
        store = ChallengeStore()
        challenge = store.issue("red_cube", 7, 0)

        first = store.consume(challenge.token, "red_cube", 7, 500)
        replay = store.consume(challenge.token, "red_cube", 7, 600)

        self.assertTrue(first.accepted)
        self.assertFalse(replay.accepted)
        self.assertEqual(replay.reason, "challenge already consumed")

    def test_unknown_challenge_is_rejected(self) -> None:
        store = ChallengeStore()
        store.issue("red_cube", 7, 0)

        decision = store.consume("forged", "red_cube", 7, 500)

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "unknown challenge")

    def test_target_mismatch_is_rejected(self) -> None:
        store = ChallengeStore()
        challenge = store.issue("red_cube", 7, 0)

        decision = store.consume(challenge.token, "blue_cube", 7, 500)

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "target mismatch")

    def test_invalid_selection_does_not_mutate_state(self) -> None:
        harness, _ = make_authorized_harness()

        with self.assertRaises(ValueError):
            harness.handle(Intent(IntentKind.SELECT, "red_cube"))

        self.assertEqual(harness.state, TaskState.IDLE)
        self.assertEqual(harness.trace, [])


if __name__ == "__main__":
    unittest.main()
