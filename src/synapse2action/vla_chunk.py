from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
import json
from math import isfinite
from time import monotonic
from typing import Callable, Mapping, Sequence
from urllib.request import Request, urlopen

from .unitree_g1 import G1_MOTOR_COUNT


@dataclass(frozen=True, slots=True)
class G1ActionChunk:
    session_id: str
    sequence: int
    actions: tuple[tuple[float, ...], ...]
    inference_ms: float
    round_trip_ms: float = 0.0


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
        started = monotonic()
        with self._opener(request, timeout=self.timeout_s) as response:
            result = json.loads(response.read())
        chunk = parse_g1_action_chunk(result, session_id=session_id, sequence=sequence)
        return G1ActionChunk(
            chunk.session_id,
            chunk.sequence,
            chunk.actions,
            chunk.inference_ms,
            (monotonic() - started) * 1000,
        )


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


class G1ActionChunkPlayer:
    def __init__(self, *, frequency_hz: float = 10.0, stale_after_s: float = 7.0) -> None:
        if frequency_hz <= 0 or stale_after_s <= 0:
            raise ValueError("frequency and stale timeout must be positive")
        self.frequency_hz = frequency_hz
        self.stale_after_s = stale_after_s
        self.chunk: G1ActionChunk | None = None
        self.started_at_s = 0.0

    def load(self, chunk: G1ActionChunk, *, now_s: float | None = None) -> None:
        if self.chunk is not None:
            if chunk.session_id != self.chunk.session_id or chunk.sequence <= self.chunk.sequence:
                raise ValueError("VLA chunks must be ordered within one session")
        self.chunk = chunk
        self.started_at_s = monotonic() if now_s is None else now_s

    def current(self, *, now_s: float | None = None) -> tuple[float, ...] | None:
        if self.chunk is None:
            return None
        elapsed = max(0.0, (monotonic() if now_s is None else now_s) - self.started_at_s)
        if elapsed > self.stale_after_s:
            return None
        index = min(int(elapsed * self.frequency_hz), len(self.chunk.actions) - 1)
        return self.chunk.actions[index]

    def needs_refresh(self, *, now_s: float | None = None, lookahead_actions: int = 5) -> bool:
        if self.chunk is None:
            return True
        elapsed = max(0.0, (monotonic() if now_s is None else now_s) - self.started_at_s)
        index = int(elapsed * self.frequency_hz)
        return index >= len(self.chunk.actions) - lookahead_actions


class G1ChunkRuntimeMetrics:
    def __init__(self, *, frequency_hz: float = 10.0) -> None:
        self.frequency_hz = frequency_hz
        self.chunks: list[G1ActionChunk] = []
        self.stale_fallbacks = 0

    def record_chunk(self, chunk: G1ActionChunk) -> None:
        self.chunks.append(chunk)

    def record_stale_fallback(self) -> None:
        self.stale_fallbacks += 1

    def report(self) -> dict[str, object]:
        inference = [chunk.inference_ms for chunk in self.chunks]
        round_trip = [chunk.round_trip_ms for chunk in self.chunks]
        coverage = [len(chunk.actions) / self.frequency_hz * 1000 for chunk in self.chunks]
        latency_within_coverage = bool(self.chunks) and all(
            latency <= duration for latency, duration in zip(round_trip, coverage, strict=True)
        )
        checks = {
            "chunks_received": bool(self.chunks),
            "latency_within_chunk_coverage": latency_within_coverage,
            "no_stale_fallback": self.stale_fallbacks == 0,
        }
        return {
            "accepted": all(checks.values()),
            "checks": checks,
            "chunks_received": len(self.chunks),
            "maximum_inference_ms": max(inference, default=None),
            "maximum_round_trip_ms": max(round_trip, default=None),
            "minimum_chunk_coverage_ms": min(coverage, default=None),
            "stale_fallbacks": self.stale_fallbacks,
        }
