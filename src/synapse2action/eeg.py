from __future__ import annotations

import math
import random
from dataclasses import dataclass
import json
from pathlib import Path

from .contracts import IntentKind


SSVEP_FREQUENCIES: dict[IntentKind, float] = {
    IntentKind.SELECT: 8.0,
    IntentKind.CONFIRM: 10.0,
    IntentKind.CANCEL: 12.0,
    IntentKind.STOP: 15.0,
}


@dataclass(frozen=True, slots=True)
class EEGWindow:
    at_ms: int
    sample_rate_hz: int
    samples: tuple[float, ...]
    expected_intent: IntentKind


@dataclass(frozen=True, slots=True)
class DecodedEEGIntent:
    kind: IntentKind
    confidence: float
    frequency_hz: float


class SyntheticSSVEPSource:
    def __init__(self, sample_rate_hz: int = 128, duration_seconds: float = 1.0, seed: int = 0) -> None:
        self.sample_rate_hz = sample_rate_hz
        self.sample_count = round(sample_rate_hz * duration_seconds)
        self.rng = random.Random(seed)

    def acquire(self, specs: list[dict[str, object]]) -> list[EEGWindow]:
        windows = []
        for spec in specs:
            kind = IntentKind(str(spec["label"]))
            frequency = SSVEP_FREQUENCIES[kind]
            amplitude = float(spec.get("signal_amplitude", 1.0))
            noise_std = float(spec.get("noise_std", 0.15))
            phase = self.rng.uniform(0.0, 2.0 * math.pi)
            samples = tuple(
                amplitude * math.sin(2.0 * math.pi * frequency * index / self.sample_rate_hz + phase)
                + self.rng.gauss(0.0, noise_std)
                for index in range(self.sample_count)
            )
            windows.append(EEGWindow(int(spec["at_ms"]), self.sample_rate_hz, samples, kind))
        return windows


class FrequencyDecoder:
    def __init__(self, confidence_threshold: float = 0.55) -> None:
        self.confidence_threshold = confidence_threshold

    def decode(self, window: EEGWindow) -> DecodedEEGIntent | None:
        powers = {
            kind: self._power(window.samples, window.sample_rate_hz, frequency)
            for kind, frequency in SSVEP_FREQUENCIES.items()
        }
        kind = max(powers, key=powers.__getitem__)
        total = sum(powers.values())
        confidence = powers[kind] / total if total else 0.0
        if confidence < self.confidence_threshold:
            return None
        return DecodedEEGIntent(kind, confidence, SSVEP_FREQUENCIES[kind])

    @staticmethod
    def _power(samples: tuple[float, ...], sample_rate_hz: int, frequency_hz: float) -> float:
        sine = cosine = 0.0
        for index, sample in enumerate(samples):
            angle = 2.0 * math.pi * frequency_hz * index / sample_rate_hz
            sine += sample * math.sin(angle)
            cosine += sample * math.cos(angle)
        return sine * sine + cosine * cosine


def save_recording(path: Path, windows: list[EEGWindow]) -> None:
    recording = {
        "schema_version": 1,
        "windows": [
            {
                "at_ms": window.at_ms,
                "sample_rate_hz": window.sample_rate_hz,
                "expected_intent": window.expected_intent.value,
                "samples": list(window.samples),
            }
            for window in windows
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(recording, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_recording(path: Path) -> list[EEGWindow]:
    recording = json.loads(path.read_text(encoding="utf-8"))
    if recording.get("schema_version") != 1:
        raise ValueError("unsupported EEG recording schema")
    return [
        EEGWindow(
            window["at_ms"],
            window["sample_rate_hz"],
            tuple(window["samples"]),
            IntentKind(window["expected_intent"]),
        )
        for window in recording["windows"]
    ]
