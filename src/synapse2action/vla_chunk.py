from __future__ import annotations

from base64 import b64encode
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
import json
from math import isfinite
from time import monotonic
from typing import Callable, Mapping, Protocol, Sequence
from urllib.request import Request, urlopen

from .unitree_g1 import G1_MOTOR_COUNT


@dataclass(frozen=True, slots=True)
class G1ActionChunk:
    session_id: str
    sequence: int
    actions: tuple[tuple[float, ...], ...]
    inference_ms: float
    round_trip_ms: float = 0.0


class PolicyChunkClient(Protocol):
    def infer(
        self,
        *,
        session_id: str,
        sequence: int,
        task: str,
        state: Sequence[float],
        images: Mapping[str, bytes],
    ) -> G1ActionChunk: ...


class OpenPIPolicy(Protocol):
    def infer(self, observation: Mapping[str, object]) -> Mapping[str, object]: ...

    def reset(self) -> None: ...


class OpenPIChunkClient:
    """Adapt OpenPI proposals to the bounded G1 action-chunk contract.

    Observation encoding and embodiment mapping are mandatory because an OpenPI
    checkpoint's camera keys and action space are checkpoint-specific. This
    adapter validates proposals; it never sends commands to a robot.
    """

    def __init__(
        self,
        policy: OpenPIPolicy,
        *,
        observation_encoder: Callable[
            [str, Sequence[float], Mapping[str, bytes]], Mapping[str, object]
        ],
        action_mapper: Callable[[Sequence[float]], Sequence[float]],
        maximum_actions: int = 50,
    ) -> None:
        if maximum_actions <= 0:
            raise ValueError("maximum actions must be positive")
        self.policy = policy
        self.observation_encoder = observation_encoder
        self.action_mapper = action_mapper
        self.maximum_actions = maximum_actions
        self._session_id: str | None = None

    def infer(
        self,
        *,
        session_id: str,
        sequence: int,
        task: str,
        state: Sequence[float],
        images: Mapping[str, bytes],
    ) -> G1ActionChunk:
        if len(state) != G1_MOTOR_COUNT:
            raise ValueError("OpenPI G1 request requires 29 state values")
        if self._session_id != session_id:
            self.policy.reset()
            self._session_id = session_id
        observation = self.observation_encoder(task, state, images)
        started = monotonic()
        response = self.policy.infer(observation)
        round_trip_ms = (monotonic() - started) * 1000
        raw_actions = response.get("actions")
        try:
            actions = list(raw_actions)  # type: ignore[arg-type]
        except TypeError as exc:
            raise ValueError("OpenPI response must contain an action chunk") from exc
        if not 1 <= len(actions) <= self.maximum_actions:
            raise ValueError("OpenPI action chunk has an invalid horizon")
        mapped = [list(self.action_mapper(action)) for action in actions]
        timing = response.get("server_timing", {})
        inference_ms = (
            timing.get("infer_ms", round_trip_ms)
            if isinstance(timing, Mapping)
            else round_trip_ms
        )
        chunk = parse_g1_action_chunk(
            {
                "session_id": session_id,
                "sequence": sequence,
                "actions": mapped,
                "inference_ms": inference_ms,
            },
            session_id=session_id,
            sequence=sequence,
        )
        return G1ActionChunk(
            chunk.session_id,
            chunk.sequence,
            chunk.actions,
            chunk.inference_ms,
            round_trip_ms,
        )


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
        if any(len(image) != 256 * 256 * 3 for image in images.values()):
            raise ValueError("G1 camera images must be 256x256 rgb8 frames")
        payload = json.dumps({
            "session_id": session_id,
            "sequence": sequence,
            "task": task,
            "state": [float(value) for value in state],
            "image_encoding": "rgb8-256x256",
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
            "first_chunk_round_trip_ms": round_trip[0] if round_trip else None,
            "maximum_inference_ms": max(inference, default=None),
            "maximum_round_trip_ms": max(round_trip, default=None),
            "minimum_chunk_coverage_ms": min(coverage, default=None),
            "stale_fallbacks": self.stale_fallbacks,
        }


class G1ChunkCoordinator:
    """Keep model HTTP inference off the simulator stepping thread."""

    def __init__(
        self,
        client: PolicyChunkClient,
        *,
        session_id: str,
        task: str,
        frequency_hz: float = 10.0,
    ) -> None:
        self.client = client
        self.session_id = session_id
        self.task = task
        self.metrics = G1ChunkRuntimeMetrics(frequency_hz=frequency_hz)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="policy-chunk")
        self._future: Future[G1ActionChunk] | None = None
        self._next_sequence = 0

    @property
    def in_flight(self) -> bool:
        return self._future is not None

    def request(
        self,
        state: Sequence[float],
        images: Mapping[str, bytes],
        *,
        request_overhead_ms: float = 0.0,
    ) -> bool:
        if self._future is not None:
            return False
        if request_overhead_ms < 0 or not isfinite(request_overhead_ms):
            raise ValueError("request overhead must be finite and non-negative")
        state_snapshot = tuple(float(value) for value in state)
        image_snapshot = {name: bytes(value) for name, value in images.items()}

        def infer() -> G1ActionChunk:
            chunk = self.client.infer(
                session_id=self.session_id,
                sequence=self._next_sequence,
                task=self.task,
                state=state_snapshot,
                images=image_snapshot,
            )
            return G1ActionChunk(
                chunk.session_id,
                chunk.sequence,
                chunk.actions,
                chunk.inference_ms,
                chunk.round_trip_ms + request_overhead_ms,
            )

        self._future = self._executor.submit(infer)
        return True

    def poll(self, *, timeout_s: float = 0.0) -> G1ActionChunk | None:
        if self._future is None:
            return None
        try:
            chunk = self._future.result(timeout=timeout_s)
        except FutureTimeout:
            return None
        finally:
            if self._future is not None and self._future.done():
                self._future = None
        self._next_sequence += 1
        self.metrics.record_chunk(chunk)
        return chunk

    def close(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)
