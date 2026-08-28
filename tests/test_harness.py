import unittest

from synapse2action.components import FakeRobot, MockPlanner, RuleBasedVerifier
from synapse2action.contracts import ExecutionResult, Intent, IntentKind, PlannerRefused, TaskState
from synapse2action.harness import Harness, InvalidTransition


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
