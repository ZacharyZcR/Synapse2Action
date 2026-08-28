from __future__ import annotations

from itertools import product
import unittest

from synapse2action.components import FakeRobot, MockPlanner, RuleBasedVerifier
from synapse2action.contracts import Intent, IntentKind
from synapse2action.harness import Harness


EVENTS = (
    Intent(IntentKind.SELECT, "red_cube"),
    Intent(IntentKind.CONFIRM),
    Intent(IntentKind.CANCEL),
    Intent(IntentKind.STOP),
)


class StateMachinePropertyTests(unittest.TestCase):
    def test_no_short_intent_sequence_executes_without_confirmed_selection(self) -> None:
        for length in range(1, 6):
            for sequence in product(EVENTS, repeat=length):
                robot = FakeRobot()
                harness = Harness(MockPlanner(), robot, RuleBasedVerifier())
                valid_confirmation = False
                selected = False
                for intent in sequence:
                    if intent.kind is IntentKind.SELECT and harness.state.value in {
                        "idle", "cancelled", "completed", "failed"
                    }:
                        selected = True
                    elif intent.kind is IntentKind.CONFIRM and selected:
                        valid_confirmation = True
                        selected = False
                    elif intent.kind in {IntentKind.CANCEL, IntentKind.STOP}:
                        selected = False
                    try:
                        harness.handle(intent)
                    except ValueError:
                        pass
                if robot.executed:
                    self.assertTrue(valid_confirmation, sequence)

    def test_stop_preempts_every_reachable_prefix(self) -> None:
        for length in range(5):
            for prefix in product(EVENTS, repeat=length):
                robot = FakeRobot()
                harness = Harness(MockPlanner(), robot, RuleBasedVerifier())
                for intent in prefix:
                    try:
                        harness.handle(intent)
                    except ValueError:
                        pass

                harness.handle(Intent(IntentKind.STOP))

                self.assertEqual(harness.state.value, "emergency_stopped")
                self.assertTrue(robot.stopped)


if __name__ == "__main__":
    unittest.main()
