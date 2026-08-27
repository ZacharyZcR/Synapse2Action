import unittest

from synapse2action.contracts import Intent, IntentKind
from synapse2action.safety import IntentGate


class IntentGateTests(unittest.TestCase):
    def test_valid_confirmation_window(self) -> None:
        gate = IntentGate()
        gate.admit(Intent(IntentKind.SELECT, "red_cube"), 0)

        self.assertTrue(gate.admit(Intent(IntentKind.CONFIRM), 500).accepted)

    def test_too_early_confirmation_is_rejected(self) -> None:
        gate = IntentGate()
        gate.admit(Intent(IntentKind.SELECT, "red_cube"), 0)

        self.assertFalse(gate.admit(Intent(IntentKind.CONFIRM), 100).accepted)

    def test_expired_confirmation_is_rejected(self) -> None:
        gate = IntentGate()
        gate.admit(Intent(IntentKind.SELECT, "red_cube"), 0)

        self.assertFalse(gate.admit(Intent(IntentKind.CONFIRM), 4000).accepted)

    def test_duplicate_event_is_rejected(self) -> None:
        gate = IntentGate()
        gate.admit(Intent(IntentKind.SELECT, "red_cube"), 0)

        self.assertFalse(gate.admit(Intent(IntentKind.SELECT, "red_cube"), 100).accepted)

    def test_stop_is_never_rejected(self) -> None:
        gate = IntentGate()

        self.assertTrue(gate.admit(Intent(IntentKind.STOP), 0).accepted)
        self.assertTrue(gate.admit(Intent(IntentKind.STOP), 1).accepted)

    def test_multiple_confirmations_can_be_required(self) -> None:
        gate = IntentGate(confirmations_required=2)
        gate.admit(Intent(IntentKind.SELECT, "red_cube"), 0)

        self.assertFalse(gate.admit(Intent(IntentKind.CONFIRM), 500).accepted)
        self.assertTrue(gate.admit(Intent(IntentKind.CONFIRM), 800).accepted)


if __name__ == "__main__":
    unittest.main()
