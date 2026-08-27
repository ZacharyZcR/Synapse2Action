import unittest

from synapse2action.world import FakeWorld, WorldObject


class FakeWorldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = FakeWorld([WorldObject("red_cube", 7, 0, (0, 0, 0))], max_age_ms=1000)

    def test_current_object_is_valid(self) -> None:
        self.assertTrue(self.world.validate("red_cube", 7, 500).accepted)

    def test_move_increments_revision(self) -> None:
        self.world.move("red_cube", (1, 0, 0), 200)

        decision = self.world.validate("red_cube", 7, 500)

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "target revision changed")

    def test_missing_object_is_invalid(self) -> None:
        self.world.remove("red_cube")

        self.assertEqual(self.world.validate("red_cube", 7, 500).reason, "target missing")

    def test_stale_observation_is_invalid(self) -> None:
        self.assertEqual(self.world.validate("red_cube", 7, 1001).reason, "world observation stale")


if __name__ == "__main__":
    unittest.main()
