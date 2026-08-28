from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
import json
from math import isfinite
from typing import Callable, Mapping, Sequence
from urllib.request import Request, urlopen

from .unitree_g1 import G1_MOTOR_COUNT


@dataclass(frozen=True, slots=True)
class G1ActionChunk:
    session_id: str
    sequence: int
    actions: tuple[tuple[float, ...], ...]
    inference_ms: float


class SmolVLAChunkClient:
    def __init__(
        self,
        endpoint: str,
        *,
        timeout_s: float = 30.0,
        opener: Callable[..., object] = urlopen,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout_s = timeout_s
        self._opener = opener

    def infer(
        self,
        *,
        session_id: str,
        sequence: int,
        task: str,
        state: Sequence[float],
        images: Mapping[str, bytes],
    ) -> G1ActionChunk:
        if len(state) != G1_MOTOR_COUNT or set(images) != {"camera1", "camera2", "camera3"}:
            raise ValueError("G1 chunk request requires 29 state values and camera1/camera2/camera3")
        payload = json.dumps({
            "session_id": session_id,
            "sequence": sequence,
            "task": task,
            "state": [float(value) for value in state],
            "images": {name: b64encode(value).decode("ascii") for name, value in images.items()},
        }).encode()
        request = Request(
            f"{self.endpoint}/infer",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self._opener(request, timeout=self.timeout_s) as response:
            result = json.loads(response.read())
        return parse_g1_action_chunk(result, session_id=session_id, sequence=sequence)


def parse_g1_action_chunk(
    payload: Mapping[str, object],
    *,
    session_id: str,
    sequence: int,
) -> G1ActionChunk:
    if payload.get("session_id") != session_id or payload.get("sequence") != sequence:
        raise ValueError("stale or mismatched VLA action chunk")
    raw_actions = payload.get("actions")
    if not isinstance(raw_actions, list) or not 1 <= len(raw_actions) <= 50:
        raise ValueError("VLA response must contain 1..50 actions")
    actions = tuple(tuple(float(value) for value in action) for action in raw_actions)
    if any(len(action) != G1_MOTOR_COUNT for action in actions):
        raise ValueError("VLA action must contain 29 joints")
    inference_ms = float(payload.get("inference_ms", -1))
    if inference_ms < 0 or not isfinite(inference_ms) or not all(isfinite(value) for action in actions for value in action):
        raise ValueError("VLA response contains invalid numeric values")
    return G1ActionChunk(session_id, sequence, actions, inference_ms)
