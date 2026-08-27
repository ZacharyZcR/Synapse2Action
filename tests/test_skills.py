import unittest

from synapse2action.contracts import Action, ExecutionResult
from synapse2action.skills import SkillContext, default_skill_registry


class SkillRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = default_skill_registry()
        self.context = SkillContext("red_cube")

    def test_valid_skill(self) -> None:
        action = Action("pick_and_place", {"target": "red_cube", "destination": "drop_zone"})

        self.assertTrue(self.registry.validate(action, self.context).accepted)

    def test_missing_and_extra_arguments_are_rejected(self) -> None:
        missing = Action("pick_and_place", {"target": "red_cube"})
        extra = Action("pick_and_place", {"target": "red_cube", "destination": "drop_zone", "force": 1})

        self.assertFalse(self.registry.validate(missing, self.context).accepted)
        self.assertFalse(self.registry.validate(extra, self.context).accepted)

    def test_timeout_fails_result(self) -> None:
        action = Action("pick_and_place", {"target": "red_cube", "destination": "drop_zone"})

        decision = self.registry.evaluate(action, ExecutionResult(True, "late", 5001))

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "skill timeout")


if __name__ == "__main__":
    unittest.main()
