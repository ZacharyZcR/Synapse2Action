import unittest

from types import SimpleNamespace
from pathlib import Path

from synapse2action.g1_vla import (
    G1VLAActionProjector,
    make_g1_vla_bridge,
)
from synapse2action.vla_chunk import G1ActionChunk
from synapse2action.task_spec import load_task_spec

TASK = load_task_spec(Path(__file__).resolve().parents[1] / "experiments/tasks/g1_pick_place.json")
G1_MANIPULATION_JOINTS = TASK.controller.joint_indices
PROJECTOR_ARGS = {
    "joint_indices": TASK.controller.joint_indices,
    "joint_limits_rad": TASK.controller.joint_limits_rad,
}


class G1VLAActionProjectorTests(unittest.TestCase):
    def test_only_manipulation_joints_override_rl_command(self) -> None:
        rl = tuple(index / 100 for index in range(29))
        predicted = tuple(-value for value in rl)
        projector = G1VLAActionProjector(**PROJECTOR_ARGS, maximum_speed_rad_s=100, blend_weight=1, maximum_residual_rad=10)
        result = projector.project(rl, predicted)
        for index in range(29):
            self.assertEqual(result[index], predicted[index] if index in G1_MANIPULATION_JOINTS else rl[index])

    def test_projection_clamps_joint_range_and_step_speed(self) -> None:
        projector = G1VLAActionProjector(
            **PROJECTOR_ARGS,
            frequency_hz=10,
            maximum_speed_rad_s=2,
            blend_weight=1,
            maximum_residual_rad=10,
        )
        projector.reset((0.0,) * 29)
        result = projector.project((0.0,) * 29, (10.0,) * 29)
        self.assertTrue(all(result[index] == 0.2 for index in G1_MANIPULATION_JOINTS))
        self.assertTrue(all(result[index] == 0.0 for index in set(range(29)) - set(G1_MANIPULATION_JOINTS)))

    def test_projection_rejects_bad_action(self) -> None:
        projector = G1VLAActionProjector(**PROJECTOR_ARGS)
        with self.assertRaisesRegex(ValueError, "29 joints"):
            projector.project((0.0,) * 29, (0.0,) * 28)
        with self.assertRaisesRegex(ValueError, "non-finite"):
            projector.project((0.0,) * 29, (float("nan"),) * 29)

    def test_default_projection_is_a_bounded_residual_over_behavior(self) -> None:
        base = (0.5,) * 29
        projector = G1VLAActionProjector(**PROJECTOR_ARGS, maximum_speed_rad_s=100)
        result = projector.project(base, (2.0,) * 29)
        for index in G1_MANIPULATION_JOINTS:
            self.assertAlmostEqual(result[index], 0.55)
        self.assertAlmostEqual(projector.last_contribution_rad, 0.05)

    def test_bridge_applies_overlay_at_official_lowcmd_boundary(self) -> None:
        class BaseBridge:
            def __init__(self) -> None:
                self.num_motor = 29
                self.mj_data = SimpleNamespace(sensordata=[0.0] * 58, ctrl=[0.0] * 29)

            def LowCmdHandler(self, message: object) -> None:
                for index, motor in enumerate(message.motor_cmd):
                    self.mj_data.ctrl[index] = motor.kp * motor.q

        motor = lambda q: SimpleNamespace(q=q, dq=0.0, tau=0.0, kp=1.0, kd=0.0)
        message = SimpleNamespace(
            motor_cmd=[motor(0.0 if index in G1_MANIPULATION_JOINTS else index / 10) for index in range(29)]
        )
        bridge = make_g1_vla_bridge(BaseBridge, **PROJECTOR_ARGS)()
        bridge.set_vla_action((1.0,) * 29)
        bridge.LowCmdHandler(message)
        self.assertEqual(bridge.vla_overlay_frames, 1)
        self.assertGreater(bridge.maximum_vla_joint_delta_rad, 0.0)
        for index in range(29):
            base = 0.0 if index in G1_MANIPULATION_JOINTS else index / 10
            expected = 0.004 if index in G1_MANIPULATION_JOINTS else base
            self.assertAlmostEqual(bridge.mj_data.ctrl[index], expected)

    def test_bridge_falls_back_to_unmodified_official_handler(self) -> None:
        class BaseBridge:
            def __init__(self) -> None:
                self.num_motor = 29
                self.mj_data = SimpleNamespace(sensordata=[0.0] * 58, ctrl=[0.0] * 29)

            def LowCmdHandler(self, message: object) -> None:
                self.mj_data.ctrl[:] = [7.0] * 29

        bridge = make_g1_vla_bridge(BaseBridge, **PROJECTOR_ARGS)()
        bridge.LowCmdHandler(SimpleNamespace())
        self.assertEqual(bridge.mj_data.ctrl, [7.0] * 29)

    def test_bridge_rejects_unsafe_chunk_before_loading_it(self) -> None:
        class BaseBridge:
            def __init__(self) -> None:
                self.num_motor = 29
                self.mj_data = SimpleNamespace(
                    time=0.0,
                    sensordata=[0.0] * 58,
                    ctrl=[0.0] * 29,
                )

        bridge = make_g1_vla_bridge(BaseBridge, **PROJECTOR_ARGS)()
        unsafe = G1ActionChunk("run", 0, ((1.0,) * 29,), 1.0)

        with self.assertRaisesRegex(ValueError, "velocity"):
            bridge.set_vla_chunk(unsafe)

        self.assertIsNone(bridge._vla_chunks.chunk)

    def test_typed_skill_passthrough_authorizes_official_command(self) -> None:
        class BaseBridge:
            def __init__(self) -> None:
                self.num_motor = 29
                self.mj_data = SimpleNamespace(time=0.0, sensordata=[0.0] * 58, ctrl=[0.0] * 29)

            def LowCmdHandler(self, message: object) -> None:
                self.mj_data.ctrl[:] = [motor.q for motor in message.motor_cmd]

        motors = [SimpleNamespace(q=float(index)) for index in range(29)]
        bridge = make_g1_vla_bridge(BaseBridge, **PROJECTOR_ARGS, apply_vla_targets=False)()
        bridge.set_vla_action((1.0,) * 29)
        bridge.LowCmdHandler(SimpleNamespace(motor_cmd=motors))
        self.assertEqual(bridge.mj_data.ctrl, [float(index) for index in range(29)])
        self.assertEqual(bridge.vla_authorized_frames, 1)
        self.assertEqual(bridge.vla_overlay_frames, 0)
        self.assertEqual(bridge.maximum_vla_joint_delta_rad, 0.0)

    def test_real_bridge_smoke_uses_fixed_unitree_image(self) -> None:
        root = Path(__file__).resolve().parents[1]
        runner = (root / "simulation/run_g1_vla_bridge_smoke.sh").read_text()
        smoke = (root / "simulation/g1_vla_bridge_smoke.py").read_text()
        self.assertIn("synapse2action-unitree-render:locked-v3", runner)
        self.assertIn("task.controller.joint_indices", smoke)


if __name__ == "__main__":
    unittest.main()
