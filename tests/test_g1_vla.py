import unittest

from synapse2action.g1_vla import G1_MANIPULATION_JOINTS, G1VLAActionProjector


class G1VLAActionProjectorTests(unittest.TestCase):
    def test_only_manipulation_joints_override_rl_command(self) -> None:
        rl = tuple(index / 100 for index in range(29))
        predicted = tuple(-value for value in rl)
        projector = G1VLAActionProjector(maximum_speed_rad_s=100)
        result = projector.project(rl, predicted)
        for index in range(29):
            self.assertEqual(result[index], predicted[index] if index in G1_MANIPULATION_JOINTS else rl[index])

    def test_projection_clamps_joint_range_and_step_speed(self) -> None:
        projector = G1VLAActionProjector(frequency_hz=10, maximum_speed_rad_s=2)
        projector.reset((0.0,) * 29)
        result = projector.project((0.0,) * 29, (10.0,) * 29)
        self.assertTrue(all(result[index] == 0.2 for index in G1_MANIPULATION_JOINTS))
        self.assertTrue(all(result[index] == 0.0 for index in set(range(29)) - set(G1_MANIPULATION_JOINTS)))

    def test_projection_rejects_bad_action(self) -> None:
        projector = G1VLAActionProjector()
        with self.assertRaisesRegex(ValueError, "29 joints"):
            projector.project((0.0,) * 29, (0.0,) * 28)
        with self.assertRaisesRegex(ValueError, "non-finite"):
            projector.project((0.0,) * 29, (float("nan"),) * 29)


if __name__ == "__main__":
    unittest.main()
