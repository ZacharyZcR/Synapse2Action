import unittest

from synapse2action.components import FakeRobot, MockPlanner, RuleBasedVerifier
from synapse2action.contracts import ExecutionResult, Intent, IntentKind, PlannerRefused, TaskState
from synapse2action.harness import Harness, InvalidTransition
from synapse2action.recovery import FailureClass
from synapse2action.world import FakeWorld, WorldObject


class ResultSequenceRobot(FakeRobot):
    def __init__(self, results):
        super().__init__()
        self.results = list(results)

    def execute(self, action):
        if self.stopped:
            return ExecutionResult(False, "robot is stopped")
        self.executed.append(action)
        return self.results.pop(0)


def make_harness() -> tuple[Harness, FakeRobot]:
    robot = FakeRobot()
    return Harness(MockPlanner(), robot, RuleBasedVerifier()), robot


class HarnessTests(unittest.TestCase):
    def test_confirmed_target_executes_once(self) -> None:
        harness, robot = make_harness()

        selected = harness.handle(Intent(IntentKind.SELECT, "red_cube"))
        self.assertEqual(selected, TaskState.AWAITING_CONFIRMATION)
        self.assertEqual(harness.pending_action.skill, "pick_and_place")
        self.assertEqual(robot.executed, [])
        state = harness.handle(Intent(IntentKind.CONFIRM))

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(len(robot.executed), 1)
        self.assertEqual(robot.executed[0].arguments["target"], "red_cube")

    def test_execution_without_confirmation_is_impossible(self) -> None:
        harness, robot = make_harness()

        with self.assertRaises(InvalidTransition):
            harness.handle(Intent(IntentKind.CONFIRM))

        self.assertEqual(robot.executed, [])

    def test_cancel_prevents_confirmation(self) -> None:
        harness, robot = make_harness()
        harness.handle(Intent(IntentKind.SELECT, "red_cube"))
        harness.handle(Intent(IntentKind.CANCEL))

        with self.assertRaises(InvalidTransition):
            harness.handle(Intent(IntentKind.CONFIRM))

        self.assertEqual(robot.executed, [])

    def test_stop_preempts_every_state(self) -> None:
        for initial_action in (None, Intent(IntentKind.SELECT, "red_cube")):
            harness, robot = make_harness()
            if initial_action:
                harness.handle(initial_action)

            state = harness.handle(Intent(IntentKind.STOP))

            self.assertEqual(state, TaskState.EMERGENCY_STOPPED)
            self.assertTrue(robot.stopped)

    def test_trace_is_deterministic(self) -> None:
        traces = []
        for _ in range(2):
            harness, _ = make_harness()
            harness.handle(Intent(IntentKind.SELECT, "red_cube"))
            harness.handle(Intent(IntentKind.CONFIRM))
            traces.append(harness.trace)

        self.assertEqual(traces[0], traces[1])

    def test_unknown_skill_never_reaches_robot(self) -> None:
        robot = FakeRobot(allowed_skills=frozenset({"invented_skill"}))
        harness = Harness(MockPlanner("invented_skill"), robot, RuleBasedVerifier())
        state = harness.handle(Intent(IntentKind.SELECT, "red_cube"))

        self.assertEqual(state, TaskState.FAILED)
        self.assertEqual(robot.executed, [])

    def test_timeout_stops_robot(self) -> None:
        robot = FakeRobot(result=ExecutionResult(True, "late", 5001))
        harness = Harness(MockPlanner(), robot, RuleBasedVerifier())
        harness.handle(Intent(IntentKind.SELECT, "red_cube"))

        state = harness.handle(Intent(IntentKind.CONFIRM))

        self.assertEqual(state, TaskState.FAILED)
        self.assertTrue(robot.stopped)
        self.assertTrue(harness.last_result.outcome_success)
        self.assertFalse(harness.last_result.process_compliance)
        self.assertTrue(harness.last_result.safety_passed)
        self.assertFalse(harness.last_result.success)
        self.assertEqual(harness.last_recovery.failure_class, FailureClass.PROCESS_NONCOMPLIANT)
        self.assertEqual(harness.last_recovery.allowed_skills, ("reobserve",))
        self.assertTrue(harness.last_recovery.requires_confirmation)
        self.assertFalse(harness.last_recovery.automatic_execution)

    def test_safety_failure_is_independent_from_outcome_and_process(self) -> None:
        robot = FakeRobot(
            result=ExecutionResult(
                True,
                "task outcome reached",
                safety_passed=False,
            )
        )
        harness = Harness(MockPlanner(), robot, RuleBasedVerifier())
        harness.handle(Intent(IntentKind.SELECT, "red_cube"))

        state = harness.handle(Intent(IntentKind.CONFIRM))

        self.assertEqual(state, TaskState.FAILED)
        self.assertTrue(harness.last_result.outcome_success)
        self.assertTrue(harness.last_result.process_compliance)
        self.assertFalse(harness.last_result.safety_passed)
        self.assertFalse(harness.last_result.success)
        self.assertEqual(harness.last_recovery.failure_class, FailureClass.SAFETY_VIOLATION)
        self.assertEqual(harness.last_recovery.allowed_skills, ())
        self.assertFalse(harness.last_recovery.requires_confirmation)

    def test_missed_outcome_only_proposes_confirmed_bounded_retry(self) -> None:
        class RejectingVerifier:
            def verify(self, result):
                return False

        robot = FakeRobot()
        harness = Harness(MockPlanner(), robot, RejectingVerifier())
        harness.handle(Intent(IntentKind.SELECT, "red_cube"))

        state = harness.handle(Intent(IntentKind.CONFIRM))

        self.assertEqual(state, TaskState.FAILED)
        self.assertEqual(harness.last_recovery.failure_class, FailureClass.OUTCOME_NOT_REACHED)
        self.assertEqual(
            harness.last_recovery.allowed_skills,
            ("reobserve", "retry_confirmed_plan"),
        )
        self.assertEqual(harness.last_recovery.remaining_attempts, 1)
        self.assertFalse(harness.last_recovery.automatic_execution)

    def test_recovery_requires_second_confirmation_and_runs_once(self) -> None:
        missed = ExecutionResult(
            False,
            "object missed destination",
            outcome_success=False,
            process_compliance=True,
            safety_passed=True,
        )
        robot = ResultSequenceRobot([missed, ExecutionResult(True, "recovered")])
        harness = Harness(MockPlanner(), robot, RuleBasedVerifier())
        harness.handle(Intent(IntentKind.SELECT, "red_cube"))
        harness.handle(Intent(IntentKind.CONFIRM))

        state = harness.request_recovery()

        self.assertEqual(state, TaskState.AWAITING_RECOVERY_CONFIRMATION)
        self.assertEqual(len(robot.executed), 1)
        state = harness.handle(Intent(IntentKind.CONFIRM))
        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(len(robot.executed), 2)
        self.assertEqual(harness.recovery_attempts, 1)
        self.assertEqual(len(harness.recovery_history), 1)
        self.assertIn("confirm_recovery", [record.event for record in harness.trace])

    def test_failed_recovery_exhausts_budget(self) -> None:
        missed = ExecutionResult(
            False,
            "still missed",
            outcome_success=False,
            process_compliance=True,
            safety_passed=True,
        )
        robot = ResultSequenceRobot([missed, missed])
        harness = Harness(MockPlanner(), robot, RuleBasedVerifier())
        harness.handle(Intent(IntentKind.SELECT, "red_cube"))
        harness.handle(Intent(IntentKind.CONFIRM))
        harness.request_recovery()
        harness.handle(Intent(IntentKind.CONFIRM))

        self.assertEqual(harness.state, TaskState.FAILED)
        self.assertEqual(harness.last_recovery.remaining_attempts, 0)
        self.assertEqual(harness.last_recovery.allowed_skills, ())
        self.assertEqual(len(harness.recovery_history), 2)
        with self.assertRaisesRegex(InvalidTransition, "no retryable"):
            harness.request_recovery()
        self.assertEqual(len(robot.executed), 2)

    def test_recovery_revalidates_fresh_world_revision(self) -> None:
        missed = ExecutionResult(
            False,
            "missed",
            outcome_success=False,
            process_compliance=True,
            safety_passed=True,
        )
        robot = ResultSequenceRobot([missed, ExecutionResult(True, "recovered")])
        world = FakeWorld([WorldObject("red_cube", 1, 0, (0.0, 0.0, 0.0))])
        harness = Harness(MockPlanner(), robot, RuleBasedVerifier(), world=world)
        harness.handle(Intent(IntentKind.SELECT, "red_cube", target_revision=1, at_ms=0))
        harness.handle(Intent(IntentKind.CONFIRM, target_revision=1, at_ms=100))
        world.move("red_cube", (0.1, 0.0, 0.0), 200)

        rejected = harness.request_recovery(target_revision=1, at_ms=300)
        accepted = harness.request_recovery(target_revision=2, at_ms=300)

        self.assertEqual(rejected, TaskState.FAILED)
        self.assertEqual(accepted, TaskState.AWAITING_RECOVERY_CONFIRMATION)
        self.assertEqual(len(robot.executed), 1)

    def test_stop_preempts_pending_recovery_confirmation(self) -> None:
        missed = ExecutionResult(
            False,
            "missed",
            outcome_success=False,
            process_compliance=True,
            safety_passed=True,
        )
        robot = ResultSequenceRobot([missed])
        harness = Harness(MockPlanner(), robot, RuleBasedVerifier())
        harness.handle(Intent(IntentKind.SELECT, "red_cube"))
        harness.handle(Intent(IntentKind.CONFIRM))
        harness.request_recovery()

        state = harness.handle(Intent(IntentKind.STOP))

        self.assertEqual(state, TaskState.EMERGENCY_STOPPED)
        self.assertTrue(robot.stopped)
        self.assertEqual(len(robot.executed), 1)
        with self.assertRaises(InvalidTransition):
            harness.handle(Intent(IntentKind.CONFIRM))

    def test_planner_failure_is_contained_before_robot(self) -> None:
        class FailedPlanner:
            def plan(self, target):
                raise TimeoutError("provider timeout")

        robot = FakeRobot()
        harness = Harness(FailedPlanner(), robot, RuleBasedVerifier())
        state = harness.handle(Intent(IntentKind.SELECT, "red_cube"))

        self.assertEqual(state, TaskState.FAILED)
        self.assertEqual(robot.executed, [])
        self.assertEqual(harness.trace[-1].event, "planner_failure")
        self.assertEqual(harness.trace[-1].detail, "TimeoutError")

    def test_planner_refusal_is_distinct_from_provider_failure(self) -> None:
        class RefusingPlanner:
            def plan(self, target):
                raise PlannerRefused("unsafe target")

        robot = FakeRobot()
        harness = Harness(RefusingPlanner(), robot, RuleBasedVerifier())
        harness.handle(Intent(IntentKind.SELECT, "human_hand"))

        self.assertEqual(harness.state, TaskState.FAILED)
        self.assertEqual(robot.executed, [])
        self.assertEqual(harness.trace[-1].event, "planner_refusal")


if __name__ == "__main__":
    unittest.main()
