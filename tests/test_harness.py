import unittest

from synapse2action.components import FakeRobot, MockPlanner, RuleBasedVerifier
from synapse2action.contracts import Intent, IntentKind, TaskState
from synapse2action.harness import Harness, InvalidTransition


def make_harness() -> tuple[Harness, FakeRobot]:
    robot = FakeRobot()
    return Harness(MockPlanner(), robot, RuleBasedVerifier()), robot


class HarnessTests(unittest.TestCase):
    def test_confirmed_target_executes_once(self) -> None:
        harness, robot = make_harness()

        harness.handle(Intent(IntentKind.SELECT, "red_cube"))
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
        harness.handle(Intent(IntentKind.SELECT, "red_cube"))

        state = harness.handle(Intent(IntentKind.CONFIRM))

        self.assertEqual(state, TaskState.FAILED)
        self.assertEqual(robot.executed, [])


if __name__ == "__main__":
    unittest.main()
