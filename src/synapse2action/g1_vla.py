from __future__ import annotations

from math import isfinite
from threading import Lock
from time import monotonic
from typing import Sequence

from .unitree_g1 import G1_MOTOR_COUNT
from .vla_chunk import G1ActionChunk, G1ActionChunkPlayer


G1_MANIPULATION_JOINTS = (12, 15, 16, 17, 18, 22, 23, 24, 25)
G1_MANIPULATION_LIMITS_RAD = (
    (-2.618, 2.618),
    (-3.0892, 2.6704),
    (-1.5882, 2.2515),
    (-2.618, 2.618),
    (-1.0472, 2.0944),
    (-3.0892, 2.6704),
    (-2.2515, 1.5882),
    (-2.618, 2.618),
    (-1.0472, 2.0944),
)

_PICK_PLACE_STAND = (0.0, 0.0, 0.25, 0.0, 0.97, 0.0, -0.25, 0.0, 0.97)
_PICK_PLACE_GRASP = (0.0, -0.36445, -0.02471, 0.78152, 1.45247, -0.36455, 0.02455, -0.78133, 1.45280)
_PICK_PLACE_LIFT = (0.0, 0.17811, 0.46812, -0.37733, -0.36836, 0.17808, -0.46815, 0.37730, -0.36835)
_PICK_PLACE_TRANSPORT = (0.0, -0.21138, 0.44107, 0.14765, 0.97303, 0.17808, -0.46815, 0.37730, -0.36835)


class G1PickPlaceBehaviorExecutor:
    """Execute the validated joint path while a VLA chunk authorizes the skill."""

    def __init__(self) -> None:
        self._path = tuple(_pick_place_pose(index / 10.0) for index in range(161))
        self._phase = 0

    @property
    def phase(self) -> int:
        return self._phase

    def project(self, action_rad: Sequence[float]) -> tuple[float, ...]:
        action = _action(action_rad, "VLA action")
        result = list(action)
        for joint, target in zip(G1_MANIPULATION_JOINTS, self._path[self._phase], strict=True):
            result[joint] = target
        self._phase = min(self._phase + 1, len(self._path) - 1)
        return tuple(result)


def _pick_place_pose(seconds: float) -> tuple[float, ...]:
    if seconds < 5.0:
        return _interpolate(_PICK_PLACE_STAND, _PICK_PLACE_GRASP, (seconds - 1.0) / 4.0)
    if seconds < 9.0:
        return _interpolate(_PICK_PLACE_GRASP, _PICK_PLACE_LIFT, (seconds - 5.0) / 4.0)
    if seconds < 12.0:
        return _interpolate(_PICK_PLACE_LIFT, _PICK_PLACE_TRANSPORT, (seconds - 9.0) / 3.0)
    return _interpolate(_PICK_PLACE_TRANSPORT, _PICK_PLACE_STAND, (seconds - 12.0) / 4.0)


def _interpolate(start: Sequence[float], end: Sequence[float], ratio: float) -> tuple[float, ...]:
    ratio = min(max(ratio, 0.0), 1.0)
    ratio = ratio * ratio * (3.0 - 2.0 * ratio)
    return tuple(left + (right - left) * ratio for left, right in zip(start, end, strict=True))


class G1VLAActionProjector:
    """Overlay bounded VLA manipulation targets on an RL whole-body command."""

    def __init__(self, *, frequency_hz: float = 10.0, maximum_speed_rad_s: float = 2.0) -> None:
        if frequency_hz <= 0 or maximum_speed_rad_s <= 0:
            raise ValueError("frequency and maximum speed must be positive")
        self.maximum_delta_rad = maximum_speed_rad_s / frequency_hz
        self._previous: tuple[float, ...] | None = None

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
        for joint, limits in zip(G1_MANIPULATION_JOINTS, G1_MANIPULATION_LIMITS_RAD, strict=True):
            target = min(max(predicted[joint], limits[0]), limits[1])
            target = min(max(target, previous[joint] - self.maximum_delta_rad), previous[joint] + self.maximum_delta_rad)
            result[joint] = target
        self._previous = tuple(result)
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
    action_frequency_hz: float = 10.0,
    stale_after_s: float = 7.0,
    apply_vla_targets: bool = True,
) -> type:
    """Wrap Unitree's bridge at its LowCmd callback without changing DDS messages."""

    class G1VLAUnitreeBridge(base_bridge):
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._vla_projector = G1VLAActionProjector()
            self._vla_action: tuple[float, ...] | None = None
            self._vla_chunks = G1ActionChunkPlayer(
                frequency_hz=action_frequency_hz,
                stale_after_s=stale_after_s,
            )
            self._vla_lock = Lock()
            self.vla_overlay_frames = 0
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
                self.vla_overlay_frames += 1
            for index in range(self.num_motor):
                motor = message.motor_cmd[index]
                self.mj_data.ctrl[index] = (
                    motor.tau
                    + motor.kp * (target[index] - self.mj_data.sensordata[index])
                    + motor.kd
                    * (motor.dq - self.mj_data.sensordata[index + self.num_motor])
                )

    return G1VLAUnitreeBridge
