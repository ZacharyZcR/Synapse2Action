from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping, Sequence

from .unitree_g1 import G1_MOTOR_COUNT


LEFT_ARM = tuple(range(15, 22))
RIGHT_ARM = tuple(range(22, 29))
WAIST = (12, 13, 14)


@dataclass(frozen=True, slots=True)
class G1GrootProposal:
    joint_position_rad: tuple[float, ...]
    navigation_command: tuple[float, float, float]
    base_height_command: float
    unsupported_hand_dimensions: int


def map_groot_unitree_action(
    action: Mapping[str, Sequence[float]],
    joint_position_rad: Sequence[float],
) -> G1GrootProposal:
    """Map GR00T's Unitree G1 embodiment into the SDK2 29-DoF boundary.

    GR00T arm actions are relative, waist actions are absolute, and hand actions
    have no actuator in Unitree's 29-DoF MJCF. Legs remain owned by the official
    locomotion policy.
    """

    current = _vector(joint_position_rad, G1_MOTOR_COUNT, "joint position")
    left_arm = _field(action, "left_arm", 7)
    right_arm = _field(action, "right_arm", 7)
    waist = _field(action, "waist", 3)
    navigation = _field(action, "navigate_command", 3)
    base_height = _field(action, "base_height_command", 1)[0]
    left_hand = _field(action, "left_hand", 7)
    right_hand = _field(action, "right_hand", 7)

    result = list(current)
    for index, delta in zip(LEFT_ARM, left_arm, strict=True):
        result[index] += delta
    for index, delta in zip(RIGHT_ARM, right_arm, strict=True):
        result[index] += delta
    for index, target in zip(WAIST, waist, strict=True):
        result[index] = target
    return G1GrootProposal(tuple(result), navigation, base_height, len(left_hand) + len(right_hand))


def _field(action: Mapping[str, Sequence[float]], name: str, width: int) -> tuple[float, ...]:
    if name not in action:
        raise ValueError(f"GR00T action is missing {name}")
    return _vector(action[name], width, f"GR00T {name}")


def _vector(values: Sequence[float], width: int, label: str) -> tuple[float, ...]:
    vector = tuple(float(value) for value in values)
    if len(vector) != width:
        raise ValueError(f"{label} must contain {width} values")
    if not all(isfinite(value) for value in vector):
        raise ValueError(f"{label} contains a non-finite value")
    return vector
