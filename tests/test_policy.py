import unittest

from synapse2action.components import ScriptedPolicy
from synapse2action.contracts import Action


class PolicyTests(unittest.TestCase):
    def test_pick_and_place_expands_to_motion_steps(self) -> None:
        policy = ScriptedPolicy()

        prepared = policy.prepare(
            Action("pick_and_place", {"target": "red_cube", "destination": "drop_zone"})
        )

        self.assertEqual(prepared.steps, ("approach", "grasp", "transport", "release"))
        self.assertEqual(policy.prepared, [prepared])


if __name__ == "__main__":
    unittest.main()
