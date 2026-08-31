import unittest

from synapse2action.g1_groot import map_groot_unitree_action


class G1GrootMapperTests(unittest.TestCase):
    def test_maps_relative_arms_absolute_waist_and_navigation(self) -> None:
        current = tuple(index / 10 for index in range(29))
        action = {
            "left_arm": [0.1] * 7,
            "right_arm": [-0.2] * 7,
            "left_hand": [0.0] * 7,
            "right_hand": [0.0] * 7,
            "waist": [0.3, -0.1, 0.2],
            "base_height_command": [0.75],
            "navigate_command": [0.5, 0.1, -0.2],
        }
        proposal = map_groot_unitree_action(action, current)
        self.assertEqual(proposal.joint_position_rad[:12], current[:12])
        self.assertEqual(proposal.joint_position_rad[12:15], (0.3, -0.1, 0.2))
        self.assertAlmostEqual(proposal.joint_position_rad[15], current[15] + 0.1)
        self.assertAlmostEqual(proposal.joint_position_rad[22], current[22] - 0.2)
        self.assertEqual(proposal.navigation_command, (0.5, 0.1, -0.2))
        self.assertEqual(proposal.base_height_command, 0.75)
        self.assertEqual(proposal.unsupported_hand_dimensions, 14)

    def test_rejects_missing_or_non_finite_modalities(self) -> None:
        action = {
            "left_arm": [0.0] * 7,
            "right_arm": [0.0] * 7,
            "left_hand": [0.0] * 7,
            "right_hand": [0.0] * 7,
            "waist": [0.0] * 3,
            "navigate_command": [0.0, 0.0, float("nan")],
        }
        with self.assertRaisesRegex(ValueError, "non-finite"):
            map_groot_unitree_action(action, (0.0,) * 29)
        del action["waist"]
        with self.assertRaisesRegex(ValueError, "missing waist"):
            map_groot_unitree_action(action, (0.0,) * 29)


if __name__ == "__main__":
    unittest.main()
