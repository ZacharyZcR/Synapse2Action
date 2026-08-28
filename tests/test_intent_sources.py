from __future__ import annotations

import unittest

from synapse2action.components import FakeRobot, MockPlanner, RuleBasedVerifier
from synapse2action.contracts import Intent, IntentKind
from synapse2action.harness import Harness
from synapse2action.intent_sources import KeyboardIntentSource, ScriptedIntentSource, run_intent_source


class IntentSourceTests(unittest.TestCase):
    def test_scripted_source_drives_confirmed_action(self) -> None:
        robot = FakeRobot()
        report = run_intent_source(
            ScriptedIntentSource(
                [Intent(IntentKind.SELECT, "red_cube"), Intent(IntentKind.CONFIRM)]
            ),
            Harness(MockPlanner(), robot, RuleBasedVerifier()),
        )

        self.assertEqual(report["final_state"], "completed")
        self.assertEqual(report["handled_intents"], 2)
        self.assertEqual(len(robot.executed), 1)

    def test_keyboard_source_parses_commands_and_recovers_from_bad_input(self) -> None:
        inputs = iter(["", "select", "nonsense", "s red_cube", "c"])
        messages = []
        source = KeyboardIntentSource(lambda _: next(inputs), messages.append)

        self.assertEqual(source.next_intent(), Intent(IntentKind.SELECT, "red_cube"))
        self.assertEqual(source.next_intent(), Intent(IntentKind.CONFIRM))
        self.assertEqual(messages, ["select requires a target", "unknown intent command"])

    def test_keyboard_eof_ends_without_action(self) -> None:
        source = KeyboardIntentSource(lambda _: (_ for _ in ()).throw(EOFError()))
        robot = FakeRobot()

        report = run_intent_source(source, Harness(MockPlanner(), robot, RuleBasedVerifier()))

        self.assertEqual(report["final_state"], "idle")
        self.assertEqual(robot.executed, [])


if __name__ == "__main__":
    unittest.main()
