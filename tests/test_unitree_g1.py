from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
import unittest

from synapse2action.unitree_g1 import (
    G1FixStandController,
    G1Joint,
    G1JointTarget,
    G1Observation,
    G1_FIX_STAND_KD,
    G1_FIX_STAND_KP,
    G1_FIX_STAND_POSITION_RAD,
    G1_POLICY_TO_SDK_JOINT,
    _projected_gravity,
    G1_MOTOR_COUNT,
    UnitreeG1Sdk,
)


@dataclass
class MotorState:
    q: float
    dq: float
    tau_est: float


class UnitreeG1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.sdk = UnitreeG1Sdk()
        state = SimpleNamespace(
            mode_machine=11,
            motor_state=[MotorState(i / 100, i / 10, i) for i in range(G1_MOTOR_COUNT)],
            imu_state=SimpleNamespace(
                rpy=[0.1, 0.2, 0.3],
                quaternion=[0.0, 0.0, 0.0, 0.0],
                gyroscope=[0.0, 0.0, 0.0],
            ),
        )
        self.sdk._on_low_state(state)

    def test_low_state_is_normalized_to_29_dof_observation(self) -> None:
        observation = self.sdk.observation()
        self.assertEqual(observation.mode_machine, 11)
        self.assertEqual(len(observation.joint_position_rad), 29)
        self.assertEqual(observation.joint_position_rad[G1Joint.RIGHT_WRIST_YAW], 0.28)
        self.assertEqual(observation.imu_rpy_rad, (0.1, 0.2, 0.3))

    def test_quaternion_is_used_when_simulator_does_not_publish_rpy(self) -> None:
        state = SimpleNamespace(
            mode_machine=11,
            motor_state=[MotorState(0.0, 0.0, 0.0) for _ in range(G1_MOTOR_COUNT)],
            imu_state=SimpleNamespace(
                rpy=[0.0, 0.0, 0.0],
                quaternion=[0.7071068, 0.7071068, 0.0, 0.0],
                gyroscope=[0.0, 0.0, 0.0],
            ),
        )
        self.sdk._on_low_state(state)
        self.assertAlmostEqual(self.sdk.observation().imu_rpy_rad[0], 1.5707963, places=5)

    def test_rejects_non_loopback_interface_for_simulation(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            UnitreeG1Sdk(interface="eth0")

    def test_accepts_explicit_isolated_container_network(self) -> None:
        sdk = UnitreeG1Sdk(interface="eth0", container_network=True)
        self.assertEqual(sdk.interface, "eth0")

    def test_joint_target_limits_are_enforced(self) -> None:
        self.sdk._validate_target(G1JointTarget(1.0, 40.0, 1.0))
        with self.assertRaisesRegex(ValueError, "position"):
            self.sdk._validate_target(G1JointTarget(4.0, 40.0, 1.0))
        with self.assertRaisesRegex(ValueError, "gain"):
            self.sdk._validate_target(G1JointTarget(1.0, 201.0, 1.0))
        with self.assertRaisesRegex(ValueError, "torque"):
            self.sdk._validate_target(G1JointTarget(1.0, 40.0, 1.0, feedforward_torque_nm=11.0))

    def test_official_fixstand_profile_covers_every_sdk_joint(self) -> None:
        self.assertEqual(len(G1_FIX_STAND_POSITION_RAD), G1_MOTOR_COUNT)
        self.assertEqual(len(G1_FIX_STAND_KP), G1_MOTOR_COUNT)
        self.assertEqual(len(G1_FIX_STAND_KD), G1_MOTOR_COUNT)
        self.assertEqual(G1_FIX_STAND_POSITION_RAD[G1Joint.LEFT_KNEE], 0.3)
        self.assertEqual(G1_FIX_STAND_KP[G1Joint.WAIST_YAW], 200.0)

    def test_official_policy_mapping_is_a_29_joint_permutation(self) -> None:
        self.assertEqual(sorted(G1_POLICY_TO_SDK_JOINT), list(range(G1_MOTOR_COUNT)))
        self.assertEqual(_projected_gravity((1.0, 0.0, 0.0, 0.0)), (0.0, 0.0, -1.0))

    def test_fixstand_interpolates_all_joints_to_official_posture(self) -> None:
        sdk = RecordingSdk(roll=0.1, pitch=-0.2)
        result = G1FixStandController(sdk, frequency_hz=100).run(0.01, 0)
        self.assertEqual(result.commands_sent, 1)
        self.assertEqual(len(sdk.targets), 1)
        final = sdk.targets[0]
        self.assertEqual(final[G1Joint.RIGHT_ELBOW].position_rad, 0.97)
        self.assertEqual(final[G1Joint.RIGHT_KNEE].kp, 150.0)
        self.assertEqual(result.maximum_pitch_rad, 0.2)

    def test_fixstand_tilt_abort_sends_neutral_frame(self) -> None:
        sdk = RecordingSdk(roll=0.8, pitch=0.0)
        with self.assertRaisesRegex(RuntimeError, "tilt"):
            G1FixStandController(sdk, frequency_hz=100).run(0.01, 0)
        self.assertEqual(sdk.neutral_count, 1)


class RecordingSdk:
    def __init__(self, *, roll: float, pitch: float) -> None:
        self.state = G1Observation(
            1,
            11,
            (0.0,) * G1_MOTOR_COUNT,
            (0.0,) * G1_MOTOR_COUNT,
            (0.0,) * G1_MOTOR_COUNT,
            (roll, pitch, 0.0),
        )
        self.targets: list[dict[G1Joint, G1JointTarget]] = []
        self.neutral_count = 0

    def assert_state_fresh(self, max_age_ms: int) -> G1Observation:
        return self.state

    def send_targets(self, targets: dict[G1Joint, G1JointTarget]) -> None:
        self.targets.append(targets)

    def send_neutral(self) -> None:
        self.neutral_count += 1


if __name__ == "__main__":
    unittest.main()
