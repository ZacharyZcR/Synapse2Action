import unittest

from types import SimpleNamespace
from pathlib import Path

from synapse2action.g1_vla import (
    G1_MANIPULATION_JOINTS,
    G1VLAActionProjector,
    make_g1_vla_bridge,
)


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

    def test_bridge_applies_overlay_at_official_lowcmd_boundary(self) -> None:
        class BaseBridge:
            def __init__(self) -> None:
                self.num_motor = 29
                self.mj_data = SimpleNamespace(sensordata=[0.0] * 58, ctrl=[0.0] * 29)

            def LowCmdHandler(self, message: object) -> None:
                for index, motor in enumerate(message.motor_cmd):
                    self.mj_data.ctrl[index] = motor.kp * motor.q

        motor = lambda q: SimpleNamespace(q=q, dq=0.0, tau=0.0, kp=1.0, kd=0.0)
        message = SimpleNamespace(motor_cmd=[motor(index / 10) for index in range(29)])
        bridge = make_g1_vla_bridge(BaseBridge)()
        bridge.set_vla_action((1.0,) * 29)
        bridge.LowCmdHandler(message)
        self.assertEqual(bridge.vla_overlay_frames, 1)
        for index in range(29):
            expected = 0.2 if index in G1_MANIPULATION_JOINTS else index / 10
            self.assertAlmostEqual(bridge.mj_data.ctrl[index], expected)

    def test_bridge_falls_back_to_unmodified_official_handler(self) -> None:
        class BaseBridge:
            def __init__(self) -> None:
                self.num_motor = 29
                self.mj_data = SimpleNamespace(sensordata=[0.0] * 58, ctrl=[0.0] * 29)

            def LowCmdHandler(self, message: object) -> None:
                self.mj_data.ctrl[:] = [7.0] * 29

        bridge = make_g1_vla_bridge(BaseBridge)()
        bridge.LowCmdHandler(SimpleNamespace())
        self.assertEqual(bridge.mj_data.ctrl, [7.0] * 29)

    def test_real_bridge_smoke_uses_fixed_unitree_image(self) -> None:
        root = Path(__file__).resolve().parents[1]
        runner = (root / "simulation/run_g1_vla_bridge_smoke.sh").read_text()
        smoke = (root / "simulation/g1_vla_bridge_smoke.py").read_text()
        self.assertIn("synapse2action-unitree-render:locked-v3", runner)
        self.assertIn("make_g1_vla_bridge(UnitreeSdk2Bridge)", smoke)


if __name__ == "__main__":
    unittest.main()
