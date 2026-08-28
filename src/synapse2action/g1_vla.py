from __future__ import annotations

from math import isfinite
from threading import Lock
from time import monotonic
from typing import Sequence

from .unitree_g1 import G1_MOTOR_COUNT
from .vla_chunk import G1ActionChunk, G1ActionChunkPlayer


class G1VLAActionProjector:
    """Blend bounded VLA residuals into an RL/behavior whole-body command."""

    def __init__(
        self,
        *,
        joint_indices: Sequence[int],
        joint_limits_rad: Sequence[tuple[float, float]],
        frequency_hz: float = 10.0,
        maximum_speed_rad_s: float = 2.0,
        blend_weight: float = 0.1,
        maximum_residual_rad: float = 0.05,
    ) -> None:
        if frequency_hz <= 0 or maximum_speed_rad_s <= 0 or maximum_residual_rad <= 0:
            raise ValueError("frequency, speed, and residual limit must be positive")
        if not 0 < blend_weight <= 1:
            raise ValueError("blend weight must be in (0, 1]")
        self.maximum_delta_rad = maximum_speed_rad_s / frequency_hz
        self.blend_weight = blend_weight
        self.maximum_residual_rad = maximum_residual_rad
        self.joint_indices = tuple(int(index) for index in joint_indices)
        self.joint_limits_rad = tuple(joint_limits_rad)
        if len(self.joint_indices) != len(self.joint_limits_rad):
            raise ValueError("joint indices and limits must have equal length")
        self._previous: tuple[float, ...] | None = None
        self.last_contribution_rad = 0.0

    def reset(self, joint_position_rad: Sequence[float]) -> None:
        self._previous = _action(joint_position_rad, "joint position")

    def project(
        self,
        rl_command_rad: Sequence[float],
        vla_action_rad: Sequence[float],
    ) -> tuple[float, ...]:
        base = _action(rl_command_rad, "RL command")
        predicted = _action(vla_action_rad, "VLA action")
        previous = self._previous or base
        result = list(base)
        contribution = 0.0
        for joint, limits in zip(self.joint_indices, self.joint_limits_rad, strict=True):
            residual = self.blend_weight * (predicted[joint] - base[joint])
            residual = min(max(residual, -self.maximum_residual_rad), self.maximum_residual_rad)
            target = min(max(base[joint] + residual, limits[0]), limits[1])
            target = min(max(target, previous[joint] - self.maximum_delta_rad), previous[joint] + self.maximum_delta_rad)
            baseline = min(max(base[joint], limits[0]), limits[1])
            baseline = min(max(baseline, previous[joint] - self.maximum_delta_rad), previous[joint] + self.maximum_delta_rad)
            contribution = max(contribution, abs(target - baseline))
            result[joint] = target
        self._previous = tuple(result)
        self.last_contribution_rad = contribution
        return self._previous


def _action(values: Sequence[float], label: str) -> tuple[float, ...]:
    action = tuple(float(value) for value in values)
    if len(action) != G1_MOTOR_COUNT:
        raise ValueError(f"{label} must contain {G1_MOTOR_COUNT} joints")
    if not all(isfinite(value) for value in action):
        raise ValueError(f"{label} contains a non-finite value")
    return action


def make_g1_vla_bridge(
    base_bridge: type,
    *,
    joint_indices: Sequence[int],
    joint_limits_rad: Sequence[tuple[float, float]],
    action_frequency_hz: float = 10.0,
    control_frequency_hz: float = 500.0,
    stale_after_s: float = 7.0,
    apply_vla_targets: bool = True,
) -> type:
    """Wrap Unitree's bridge at its LowCmd callback without changing DDS messages."""

    class G1VLAUnitreeBridge(base_bridge):
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._vla_projector = G1VLAActionProjector(
                frequency_hz=control_frequency_hz,
                joint_indices=joint_indices,
                joint_limits_rad=joint_limits_rad,
            )
            self._vla_action: tuple[float, ...] | None = None
            self._vla_chunks = G1ActionChunkPlayer(
                frequency_hz=action_frequency_hz,
                stale_after_s=stale_after_s,
            )
            self._vla_lock = Lock()
            self.vla_overlay_frames = 0
            self.maximum_vla_joint_delta_rad = 0.0
            self.vla_authorized_frames = 0
            self.vla_stale_fallbacks = 0
            self._vla_was_active = False
            super().__init__(*args, **kwargs)

        def set_vla_action(self, action_rad: Sequence[float]) -> None:
            action = _action(action_rad, "VLA action")
            with self._vla_lock:
                if self._vla_action is None:
                    self._vla_projector.reset(self.mj_data.sensordata[: self.num_motor])
                self._vla_action = action

        def set_vla_chunk(self, chunk: G1ActionChunk) -> None:
            with self._vla_lock:
                if self._vla_action is None and self._vla_chunks.chunk is None:
                    self._vla_projector.reset(self.mj_data.sensordata[: self.num_motor])
                self._vla_action = None
                self._vla_chunks.load(chunk, now_s=self._vla_now())

        def _vla_now(self) -> float:
            return float(getattr(self.mj_data, "time", monotonic()))

        def needs_vla_chunk(self, *, lookahead_actions: int = 5) -> bool:
            with self._vla_lock:
                return self._vla_chunks.needs_refresh(
                    now_s=self._vla_now(),
                    lookahead_actions=lookahead_actions,
                )

        def clear_vla_action(self) -> None:
            with self._vla_lock:
                self._vla_action = None
                self._vla_chunks = G1ActionChunkPlayer(
                    frequency_hz=action_frequency_hz,
                    stale_after_s=stale_after_s,
                )

        def LowCmdHandler(self, message: object) -> None:  # noqa: N802 - official SDK callback name
            with self._vla_lock:
                action = self._vla_action or self._vla_chunks.current(now_s=self._vla_now())
                if action is None and self._vla_was_active and self._vla_chunks.chunk is not None:
                    self.vla_stale_fallbacks += 1
                self._vla_was_active = action is not None
                if action is None:
                    return super().LowCmdHandler(message)
                self.vla_authorized_frames += 1
                if not apply_vla_targets:
                    return super().LowCmdHandler(message)
                rl_command = tuple(float(message.motor_cmd[i].q) for i in range(self.num_motor))
                target = self._vla_projector.project(rl_command, action)
                contribution = self._vla_projector.last_contribution_rad
                if contribution > 1e-6:
                    self.vla_overlay_frames += 1
                    self.maximum_vla_joint_delta_rad = max(self.maximum_vla_joint_delta_rad, contribution)
            for index in range(self.num_motor):
                motor = message.motor_cmd[index]
                self.mj_data.ctrl[index] = (
                    motor.tau
                    + motor.kp * (target[index] - self.mj_data.sensordata[index])
                    + motor.kd
                    * (motor.dq - self.mj_data.sensordata[index + self.num_motor])
                )

    return G1VLAUnitreeBridge
