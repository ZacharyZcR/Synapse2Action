import unittest

from synapse2action.contracts import Action
from synapse2action.tabletop import Point2D, TabletopObject, TabletopRobot, TabletopVerifier


class TabletopTests(unittest.TestCase):
    def test_pick_and_place_changes_world_state(self) -> None:
        destination = Point2D(0.8, 0.6)
        robot = TabletopRobot(TabletopObject("red_cube", Point2D(0.4, 0.1)), {"drop_zone": destination})
        verifier = TabletopVerifier(robot, destination)

        result = robot.execute(Action("pick_and_place", {"target": "red_cube", "destination": "drop_zone"}))

        self.assertTrue(verifier.verify(result))
        self.assertEqual(robot.item.position, destination)
        self.assertFalse(robot.item.held)
        self.assertEqual([frame.step for frame in robot.frames], ["initial", "approach", "grasp", "transport", "release"])

    def test_unknown_destination_does_not_move_object(self) -> None:
        start = Point2D(0.4, 0.1)
        robot = TabletopRobot(TabletopObject("red_cube", start), {})

        result = robot.execute(Action("pick_and_place", {"target": "red_cube", "destination": "missing"}))

        self.assertFalse(result.success)
        self.assertEqual(robot.item.position, start)
        self.assertEqual(len(robot.executed), 0)


if __name__ == "__main__":
    unittest.main()
