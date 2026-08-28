from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from enum import IntEnum
from math import asin, atan2, copysign, isfinite, pi
from threading import Event, Lock
from time import monotonic, monotonic_ns, sleep
from typing import Any, Mapping, Sequence


G1_MOTOR_COUNT = 29
LOWCMD_TOPIC = "rt/lowcmd"
LOWSTATE_TOPIC = "rt/lowstate"

# Unitree unitree_rl_lab G1 29-DOF FixStand profile. Joint order is SDK2 order.
G1_FIX_STAND_POSITION_RAD = (
    -0.1, 0.0, 0.0, 0.3, -0.2, 0.0,
    -0.1, 0.0, 0.0, 0.3, -0.2, 0.0,
    0.0, 0.0, 0.0,
    0.0, 0.25, 0.0, 0.97, 0.15, 0.0, 0.0,
    0.0, -0.25, 0.0, 0.97, -0.15, 0.0, 0.0,
)
G1_FIX_STAND_KP = (
    100.0, 100.0, 100.0, 150.0, 40.0, 40.0,
    100.0, 100.0, 100.0, 150.0, 40.0, 40.0,
    200.0, 200.0, 200.0,
    40.0, 40.0, 40.0, 40.0, 40.0, 40.0, 40.0,
    40.0, 40.0, 40.0, 40.0, 40.0, 40.0, 40.0,
)
G1_FIX_STAND_KD = (
    2.0, 2.0, 2.0, 4.0, 2.0, 2.0,
    2.0, 2.0, 2.0, 4.0, 2.0, 2.0,
    5.0, 5.0, 5.0,
    10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0,
    10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0,
)

# Policy order and parameters from unitree_rl_lab's G1 29-DOF velocity v0 deploy.yaml.
G1_POLICY_TO_SDK_JOINT = (
    0, 6, 12, 1, 7, 13, 2, 8, 14, 3, 9, 15, 22, 4, 10, 16, 23, 5, 11,
    17, 24, 18, 25, 19, 26, 20, 27, 21, 28,
)
G1_POLICY_DEFAULT_POSITION_RAD = (
    -0.1, -0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.3, 0.3, 0.3,
    0.3, -0.2, -0.2, 0.25, -0.25, 0.0, 0.0, 0.0, 0.0, 0.97, 0.97,
    0.15, -0.15, 0.0, 0.0, 0.0, 0.0,
)


class G1Joint(IntEnum):
    LEFT_HIP_PITCH = 0
    LEFT_HIP_ROLL = 1
    LEFT_HIP_YAW = 2
    LEFT_KNEE = 3
    LEFT_ANKLE_PITCH = 4
    LEFT_ANKLE_ROLL = 5
    RIGHT_HIP_PITCH = 6
    RIGHT_HIP_ROLL = 7
    RIGHT_HIP_YAW = 8
    RIGHT_KNEE = 9
    RIGHT_ANKLE_PITCH = 10
    RIGHT_ANKLE_ROLL = 11
    WAIST_YAW = 12
    WAIST_ROLL = 13
    WAIST_PITCH = 14
    LEFT_SHOULDER_PITCH = 15
    LEFT_SHOULDER_ROLL = 16
    LEFT_SHOULDER_YAW = 17
    LEFT_ELBOW = 18
    LEFT_WRIST_ROLL = 19
    LEFT_WRIST_PITCH = 20
    LEFT_WRIST_YAW = 21
    RIGHT_SHOULDER_PITCH = 22
    RIGHT_SHOULDER_ROLL = 23
    RIGHT_SHOULDER_YAW = 24
    RIGHT_ELBOW = 25
    RIGHT_WRIST_ROLL = 26
    RIGHT_WRIST_PITCH = 27
    RIGHT_WRIST_YAW = 28


@dataclass(frozen=True, slots=True)
class G1Observation:
    captured_at_ns: int
    mode_machine: int
    joint_position_rad: tuple[float, ...]
    joint_velocity_rad_s: tuple[float, ...]
    joint_torque_nm: tuple[float, ...]
    imu_rpy_rad: tuple[float, float, float]
    imu_quaternion_wxyz: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)
    imu_angular_velocity_rad_s: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True, slots=True)
class G1JointTarget:
    position_rad: float
    kp: float
    kd: float
    velocity_rad_s: float = 0.0
    feedforward_torque_nm: float = 0.0


class UnitreeSdkUnavailable(RuntimeError):
    pass


class UnitreeG1Sdk:
    """Thin adapter over the official unitree_sdk2_python DDS API.

    This transport is deliberately low-level: the same LowCmd/LowState contract
    is consumed by Unitree's MuJoCo bridge and by a physical G1.
    """

    def __init__(
        self,
        *,
        domain_id: int = 1,
        interface: str = "lo",
        container_network: bool = False,
        max_abs_position_rad: float = 3.2,
        max_kp: float = 200.0,
        max_kd: float = 10.0,
        max_abs_torque_nm: float = 10.0,
    ) -> None:
        if interface != "lo" and not container_network:
            raise ValueError("simulation adapter requires the loopback interface 'lo'")
        self.domain_id = domain_id
        self.interface = interface
        self.max_abs_position_rad = max_abs_position_rad
        self.max_kp = max_kp
        self.max_kd = max_kd
        self.max_abs_torque_nm = max_abs_torque_nm
        self._state: G1Observation | None = None
        self._state_ready = Event()
        self._lock = Lock()
        self._publisher: Any = None
        self._subscriber: Any = None
        self._low_cmd: Any = None
        self._crc: Any = None

    def connect(self) -> None:
        try:
            from unitree_sdk2py.core.channel import (
                ChannelFactoryInitialize,
                ChannelPublisher,
                ChannelSubscriber,
            )
            from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
            from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
            from unitree_sdk2py.utils.crc import CRC
        except ImportError as exc:
            raise UnitreeSdkUnavailable(
                "official unitree_sdk2_python is not installed; run simulation/bootstrap_unitree.sh"
            ) from exc

        ChannelFactoryInitialize(self.domain_id, self.interface)
        self._low_cmd = unitree_hg_msg_dds__LowCmd_()
        self._crc = CRC()
        self._publisher = ChannelPublisher(LOWCMD_TOPIC, LowCmd_)
        self._publisher.Init()
        self._subscriber = ChannelSubscriber(LOWSTATE_TOPIC, LowState_)
        self._subscriber.Init(self._on_low_state, 10)

    def wait_for_state(self, timeout_s: float = 5.0) -> G1Observation:
        if not self._state_ready.wait(timeout_s):
            raise TimeoutError(f"no G1 LowState received on {LOWSTATE_TOPIC}")
        return self.observation()

    def observation(self) -> G1Observation:
        with self._lock:
            if self._state is None:
                raise RuntimeError("G1 LowState is not available")
            return self._state

    def send_targets(self, targets: Mapping[G1Joint, G1JointTarget]) -> None:
        if self._publisher is None or self._low_cmd is None:
            raise RuntimeError("Unitree SDK transport is not connected")
        state = self.observation()
        self._low_cmd.mode_pr = 0
        self._low_cmd.mode_machine = state.mode_machine
        for joint in G1Joint:
            target = targets.get(joint)
            motor = self._low_cmd.motor_cmd[joint.value]
            motor.mode = 1
            motor.tau = 0.0
            motor.q = state.joint_position_rad[joint.value]
            motor.dq = 0.0
            motor.kp = 0.0
            motor.kd = 0.0
            if target is not None:
                self._validate_target(target)
                motor.tau = target.feedforward_torque_nm
                motor.q = target.position_rad
                motor.dq = target.velocity_rad_s
                motor.kp = target.kp
                motor.kd = target.kd
        self._low_cmd.crc = self._crc.Crc(self._low_cmd)
        self._publisher.Write(self._low_cmd)

    def send_neutral(self) -> None:
        self.send_targets({})

    def assert_state_fresh(self, max_age_ms: int = 100) -> G1Observation:
        state = self.observation()
        age_ns = monotonic_ns() - state.captured_at_ns
        if age_ns > max_age_ms * 1_000_000:
            raise TimeoutError(f"G1 LowState is stale by {age_ns / 1_000_000:.1f} ms")
        return state

    def stream_neutral(self, duration_s: float, frequency_hz: float = 200.0) -> int:
        if duration_s <= 0 or not 1 <= frequency_hz <= 500:
            raise ValueError("duration must be positive and frequency must be within [1, 500] Hz")
        period_s = 1.0 / frequency_hz
        deadline = monotonic_ns() + int(duration_s * 1_000_000_000)
        count = 0
        while monotonic_ns() < deadline:
            self.send_targets({})
            count += 1
            sleep(period_s)
        return count

    def _on_low_state(self, message: Any) -> None:
        motor_state = message.motor_state
        if len(motor_state) < G1_MOTOR_COUNT:
            return
        quaternion = tuple(float(value) for value in message.imu_state.quaternion)
        rpy = _quaternion_to_rpy(quaternion)
        if rpy is None:
            rpy = tuple(float(value) for value in message.imu_state.rpy)
        observation = G1Observation(
            captured_at_ns=monotonic_ns(),
            mode_machine=int(message.mode_machine),
            joint_position_rad=tuple(float(motor_state[i].q) for i in range(G1_MOTOR_COUNT)),
            joint_velocity_rad_s=tuple(float(motor_state[i].dq) for i in range(G1_MOTOR_COUNT)),
            joint_torque_nm=tuple(float(motor_state[i].tau_est) for i in range(G1_MOTOR_COUNT)),
            imu_rpy_rad=rpy,
            imu_quaternion_wxyz=quaternion,
            imu_angular_velocity_rad_s=tuple(
                float(value) for value in message.imu_state.gyroscope
            ),
        )
        with self._lock:
            self._state = observation
        self._state_ready.set()

    def _validate_target(self, target: G1JointTarget) -> None:
        values = (
            target.position_rad,
            target.velocity_rad_s,
            target.kp,
            target.kd,
            target.feedforward_torque_nm,
        )
        if not all(isfinite(value) for value in values):
            raise ValueError("G1 joint target contains a non-finite value")
        if abs(target.position_rad) > self.max_abs_position_rad:
            raise ValueError("G1 joint position exceeds adapter limit")
        if not 0 <= target.kp <= self.max_kp or not 0 <= target.kd <= self.max_kd:
            raise ValueError("G1 joint gain exceeds adapter limit")
        if abs(target.feedforward_torque_nm) > self.max_abs_torque_nm:
            raise ValueError("G1 feedforward torque exceeds adapter limit")


def _quaternion_to_rpy(
    quaternion_wxyz: tuple[float, ...],
) -> tuple[float, float, float] | None:
    if len(quaternion_wxyz) != 4 or sum(value * value for value in quaternion_wxyz) < 0.5:
        return None
    w, x, y, z = quaternion_wxyz
    roll = atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    sin_pitch = 2 * (w * y - z * x)
    pitch = copysign(pi / 2, sin_pitch) if abs(sin_pitch) >= 1 else asin(sin_pitch)
    yaw = atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return roll, pitch, yaw


@dataclass(frozen=True, slots=True)
class G1StandResult:
    commands_sent: int
    maximum_roll_rad: float
    maximum_pitch_rad: float


class G1FixStandController:
    """SDK2 implementation of Unitree's linear FixStand transition."""

    def __init__(
        self,
        sdk: UnitreeG1Sdk,
        *,
        frequency_hz: float = 200.0,
        state_timeout_ms: int = 100,
        maximum_tilt_rad: float = 0.7,
    ) -> None:
        if not 1 <= frequency_hz <= 500:
            raise ValueError("control frequency must be within [1, 500] Hz")
        if state_timeout_ms <= 0 or not 0 < maximum_tilt_rad < 1.57:
            raise ValueError("invalid G1 stand safety limit")
        self.sdk = sdk
        self.frequency_hz = frequency_hz
        self.state_timeout_ms = state_timeout_ms
        self.maximum_tilt_rad = maximum_tilt_rad

    def run(self, transition_s: float = 3.0, hold_s: float = 2.0) -> G1StandResult:
        if transition_s <= 0 or hold_s < 0:
            raise ValueError("stand transition must be positive and hold must be non-negative")
        initial = self.sdk.assert_state_fresh(self.state_timeout_ms)
        start = initial.joint_position_rad
        transition_steps = max(1, round(transition_s * self.frequency_hz))
        hold_steps = round(hold_s * self.frequency_hz)
        period_s = 1.0 / self.frequency_hz
        maximum_roll = 0.0
        maximum_pitch = 0.0

        try:
            for step in range(1, transition_steps + hold_steps + 1):
                state = self.sdk.assert_state_fresh(self.state_timeout_ms)
                roll, pitch, _ = state.imu_rpy_rad
                maximum_roll = max(maximum_roll, abs(roll))
                maximum_pitch = max(maximum_pitch, abs(pitch))
                if maximum_roll > self.maximum_tilt_rad or maximum_pitch > self.maximum_tilt_rad:
                    raise RuntimeError("G1 tilt limit exceeded during FixStand")
                ratio = min(step / transition_steps, 1.0)
                positions = tuple(
                    current + (target - current) * ratio
                    for current, target in zip(start, G1_FIX_STAND_POSITION_RAD, strict=True)
                )
                targets = {
                    joint: G1JointTarget(
                        positions[joint.value],
                        G1_FIX_STAND_KP[joint.value],
                        G1_FIX_STAND_KD[joint.value],
                    )
                    for joint in G1Joint
                }
                self.sdk.send_targets(targets)
                sleep(period_s)
        except (RuntimeError, TimeoutError):
            self.sdk.send_neutral()
            raise

        return G1StandResult(
            transition_steps + hold_steps,
            maximum_roll,
            maximum_pitch,
        )


@dataclass(frozen=True, slots=True)
class G1BalanceResult:
    policy_steps: int
    maximum_roll_rad: float
    maximum_pitch_rad: float


class G1OfficialVelocityPolicy:
    """Runs Unitree's exported G1 velocity-v0 ONNX policy over SDK2 state."""

    def __init__(
        self,
        sdk: UnitreeG1Sdk,
        policy_path: str,
        *,
        state_timeout_ms: int = 100,
        maximum_tilt_rad: float = 1.0,
    ) -> None:
        try:
            import numpy as np
            import onnxruntime as ort
        except ImportError as exc:
            raise UnitreeSdkUnavailable("onnxruntime and numpy are required for G1 balance") from exc
        self.sdk = sdk
        self.np = np
        self.session = ort.InferenceSession(policy_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        self.state_timeout_ms = state_timeout_ms
        self.maximum_tilt_rad = maximum_tilt_rad
        self.last_action = [0.0] * G1_MOTOR_COUNT
        self.history: dict[str, deque[list[float]]] = {}

    def run(self, duration_s: float = 5.0) -> G1BalanceResult:
        if duration_s <= 0:
            raise ValueError("balance duration must be positive")
        steps = round(duration_s / 0.02)
        maximum_roll = 0.0
        maximum_pitch = 0.0
        last_max_action = 0.0
        next_step = monotonic()
        try:
            for step in range(steps):
                state = self.sdk.assert_state_fresh(self.state_timeout_ms)
                roll, pitch, _ = state.imu_rpy_rad
                maximum_roll = max(maximum_roll, abs(roll))
                maximum_pitch = max(maximum_pitch, abs(pitch))
                if maximum_roll > self.maximum_tilt_rad or maximum_pitch > self.maximum_tilt_rad:
                    raise RuntimeError(
                        f"G1 tilt limit exceeded during official velocity policy at step {step}: "
                        f"roll={roll:.3f}, pitch={pitch:.3f}, last_max_action={last_max_action:.3f}"
                    )
                observation = self._policy_observation(state)
                output = self.session.run(
                    [self.output_name],
                    {self.input_name: self.np.asarray([observation], dtype=self.np.float32)},
                )[0]
                action = [float(value) for value in output.reshape(-1)]
                if len(action) != G1_MOTOR_COUNT or not all(isfinite(value) for value in action):
                    raise RuntimeError("Unitree G1 policy returned an invalid action")
                self.last_action = action
                last_max_action = max(abs(value) for value in action)
                processed = [
                    action[index] * 0.25 + G1_POLICY_DEFAULT_POSITION_RAD[index]
                    for index in range(G1_MOTOR_COUNT)
                ]
                targets = {
                    G1Joint(sdk_joint): G1JointTarget(
                        processed[policy_index],
                        G1_FIX_STAND_KP[sdk_joint],
                        G1_FIX_STAND_KD[sdk_joint],
                    )
                    for policy_index, sdk_joint in enumerate(G1_POLICY_TO_SDK_JOINT)
                }
                try:
                    self.sdk.send_targets(targets)
                except ValueError as exc:
                    raise RuntimeError(
                        f"invalid official policy target at step {step}: "
                        f"max_action={max(abs(value) for value in action):.3f}, "
                        f"max_position={max(abs(value) for value in processed):.3f}"
                    ) from exc
                next_step += 0.02
                remaining = next_step - monotonic()
                if remaining > 0:
                    sleep(remaining)
        except (RuntimeError, TimeoutError):
            self.sdk.send_neutral()
            raise
        return G1BalanceResult(steps, maximum_roll, maximum_pitch)

    def _policy_observation(self, state: G1Observation) -> list[float]:
        mapped_position = [state.joint_position_rad[index] for index in G1_POLICY_TO_SDK_JOINT]
        mapped_velocity = [state.joint_velocity_rad_s[index] for index in G1_POLICY_TO_SDK_JOINT]
        terms = (
            ("base_ang_vel", [value * 0.2 for value in state.imu_angular_velocity_rad_s]),
            ("projected_gravity", list(_projected_gravity(state.imu_quaternion_wxyz))),
            ("velocity_commands", [0.0, 0.0, 0.0]),
            ("joint_pos_rel", [
                value - G1_POLICY_DEFAULT_POSITION_RAD[index]
                for index, value in enumerate(mapped_position)
            ]),
            ("joint_vel_rel", [value * 0.05 for value in mapped_velocity]),
            ("last_action", self.last_action.copy()),
        )
        observation: list[float] = []
        for name, value in terms:
            history = self.history.setdefault(name, deque((value.copy() for _ in range(5)), maxlen=5))
            history.append(value)
            for entry in history:
                observation.extend(entry)
        return observation


def _projected_gravity(quaternion_wxyz: Sequence[float]) -> tuple[float, float, float]:
    w, x, y, z = quaternion_wxyz
    return (
        -2 * (x * z - w * y),
        -2 * (y * z + w * x),
        -(1 - 2 * (x * x + y * y)),
    )
