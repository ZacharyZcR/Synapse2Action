from __future__ import annotations

from math import isfinite
from typing import Sequence

from .unitree_g1 import G1_MOTOR_COUNT


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
