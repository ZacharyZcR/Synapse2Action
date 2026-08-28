from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import monotonic, sleep

from brainflow.board_shim import BoardIds, BoardShim, BrainFlowInputParams
import numpy as np
from pylsl import StreamInfo, StreamInlet, StreamOutlet, local_clock, resolve_byprop


FREQUENCIES = {"select": 8.0, "confirm": 10.0, "cancel": 12.0, "stop": 15.0}
WINDOW_SECONDS = 1.5


def power(samples: np.ndarray, sample_rate: int, frequency: float) -> float:
    time = np.arange(samples.shape[1]) / sample_rate
    reference = np.exp(-2j * np.pi * frequency * time)
    return float(np.mean(np.abs(samples @ reference) ** 2))


def decode(samples: np.ndarray, sample_rate: int, threshold: float) -> tuple[str | None, float]:
    scores = np.asarray([power(samples, sample_rate, value) for value in FREQUENCIES.values()])
    probabilities = scores / max(float(scores.sum()), 1e-9)
    index = int(probabilities.argmax())
    confidence = float(probabilities[index])
    return (tuple(FREQUENCIES)[index] if confidence >= threshold else None), confidence


def main() -> None:
    parser = argparse.ArgumentParser(description="BrainFlow Synthetic Board to LSL live SSVEP gate")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    board_id = BoardIds.SYNTHETIC_BOARD.value
    board = BoardShim(board_id, BrainFlowInputParams())
    sample_rate = BoardShim.get_sampling_rate(board_id)
    eeg_channels = BoardShim.get_eeg_channels(board_id)
    channel_count = len(eeg_channels)
    source_id = f"synapse2action-{int(monotonic() * 1e6)}"
    eeg_info = StreamInfo("Synapse2ActionEEG", "EEG", channel_count, sample_rate, "float32", source_id)
    marker_info = StreamInfo("Synapse2ActionMarkers", "Markers", 1, 0, "string", source_id + "-markers")
    eeg_outlet = StreamOutlet(eeg_info, chunk_size=25, max_buffered=30)
    marker_outlet = StreamOutlet(marker_info)
    eeg_stream = resolve_byprop("source_id", source_id, timeout=2.0)
    marker_stream = resolve_byprop("source_id", source_id + "-markers", timeout=2.0)
    if not eeg_stream or not marker_stream:
        raise RuntimeError("LSL streams could not be resolved")
    eeg_inlet = StreamInlet(eeg_stream[0], max_buflen=30)
    marker_inlet = StreamInlet(marker_stream[0], max_buflen=30)
    eeg_inlet.open_stream(timeout=2.0)
    marker_inlet.open_stream(timeout=2.0)
    sleep(0.2)
    eeg_inlet.flush()
    marker_inlet.flush()

    records: list[dict[str, object]] = []
    threshold: float | None = None
    board.prepare_session()
    board.start_stream()
    try:
        sleep(0.2)
        sample_index = 0
        sequence = (
            ("calibration", "select"), ("calibration", "noise"),
            ("evaluation", "select"), ("evaluation", "confirm"),
            ("evaluation", "cancel"), ("evaluation", "stop"), ("evaluation", "noise"),
        )
        signal_window_index = 0
        for phase, intended in sequence:
            started = monotonic()
            marker_outlet.push_sample([f"window_start:{intended}"], local_clock())
            received: list[list[float]] = []
            timestamps: list[float] = []
            while monotonic() - started < WINDOW_SECONDS:
                sleep(0.1)
                board_data = board.get_current_board_data(25)
                if board_data.shape[1] < 25:
                    continue
                noise = board_data[eeg_channels, -25:].T
                noise = (noise - noise.mean(axis=0, keepdims=True)) / np.maximum(noise.std(axis=0, keepdims=True), 1e-6)
                indices = np.arange(sample_index, sample_index + 25)
                sample_index += 25
                if intended == "noise":
                    chunk = noise * 0.08
                else:
                    signal = np.sin(2 * np.pi * FREQUENCIES[intended] * indices / sample_rate)[:, None]
                    amplitude = 1.0 - 0.06 * signal_window_index
                    chunk = amplitude * signal + noise * 0.08
                now = local_clock()
                chunk_timestamps = (now - np.arange(24, -1, -1) / sample_rate).tolist()
                eeg_outlet.push_chunk(chunk.astype(np.float32).tolist(), chunk_timestamps)
                sleep(0.01)
                samples, stamps = eeg_inlet.pull_chunk(timeout=0.0, max_samples=256)
                received.extend(samples)
                timestamps.extend(stamps)
            marker_outlet.push_sample([f"window_end:{intended}"], local_clock())
            sleep(0.05)
            while True:
                samples, stamps = eeg_inlet.pull_chunk(timeout=0.0, max_samples=256)
                if not samples:
                    break
                received.extend(samples)
                timestamps.extend(stamps)
            markers, marker_timestamps = marker_inlet.pull_chunk(timeout=0.5, max_samples=8)
            window = np.asarray(received, dtype=np.float32).T
            usable = bool(
                window.shape[0] == channel_count
                and window.shape[1] >= round(sample_rate * WINDOW_SECONDS * 0.8)
                and np.isfinite(window).all()
                and np.all(window.std(axis=1) > 1e-4)
            )
            active_threshold = threshold if threshold is not None else 0.0
            decoded, confidence = decode(window, sample_rate, active_threshold) if usable else (None, 0.0)
            records.append({
                "phase": phase,
                "intended": intended,
                "decoded": decoded,
                "confidence": confidence,
                "quality_accepted": usable,
                "samples": int(window.shape[1]) if window.ndim == 2 else 0,
                "latency_seconds": monotonic() - started,
                "lsl_timestamp_monotonic": all(b > a for a, b in zip(timestamps, timestamps[1:])),
                "markers": [value[0] for value in markers],
                "marker_timestamps": marker_timestamps,
                "rms": float(np.sqrt(np.mean(window**2))) if usable else 0.0,
            })
            if intended != "noise":
                signal_window_index += 1
            if phase == "calibration" and intended == "noise":
                signal_confidence = float(records[0]["confidence"])
                noise_confidence = confidence
                if signal_confidence <= noise_confidence:
                    raise RuntimeError("session calibration could not separate SSVEP from noise")
                threshold = (signal_confidence + noise_confidence) / 2
    finally:
        board.stop_stream()
        board.release_session()

    assert threshold is not None
    calibration = records[:2]
    evaluation = records[2:]
    classified = evaluation[:-1]
    drift_ratio = float(classified[-1]["rms"] / classified[0]["rms"])
    checks = {
        "brainflow_samples": all(record["samples"] > 0 for record in records),
        "lsl_timestamps": all(record["lsl_timestamp_monotonic"] for record in records),
        "separate_select_confirm_windows": classified[0]["decoded"] == "select" and classified[1]["decoded"] == "confirm",
        "four_intents": all(record["decoded"] == record["intended"] for record in classified),
        "session_calibration": calibration[0]["confidence"] > threshold > calibration[1]["confidence"],
        "uncertain_abstention": evaluation[-1]["decoded"] is None,
        "quality_gate": all(record["quality_accepted"] for record in records),
        "markers": all(len(record["markers"]) >= 2 for record in records),
        "drift_within_limit": drift_ratio >= 0.60,
    }
    examples = {
        record["intended"]: {
            "decoded_intent": record["decoded"],
            "confidence": record["confidence"],
            "frequency_hz": FREQUENCIES[record["intended"]],
        }
        for record in classified
    }
    report = {
        "accepted": all(checks.values()),
        "checks": checks,
        "board": "BrainFlow Synthetic Board",
        "board_id": board_id,
        "sample_rate_hz": sample_rate,
        "eeg_channels": channel_count,
        "lsl": {"eeg_stream": eeg_info.name(), "marker_stream": marker_info.name(), "source_id": source_id},
        "threshold": threshold,
        "calibration": {
            "signal_confidence": calibration[0]["confidence"],
            "noise_confidence": calibration[1]["confidence"],
            "threshold": threshold,
        },
        "drift": {"last_to_first_rms_ratio": drift_ratio, "minimum_ratio": 0.60},
        "windows": records,
        "harness_replay": {"accepted": checks["four_intents"], "decoded_examples": examples},
        "metrics": {
            "mean_latency_seconds": float(np.mean([record["latency_seconds"] for record in evaluation])),
            "false_activations": int(evaluation[-1]["decoded"] is not None),
            "abstention_rate": float(sum(record["decoded"] is None for record in evaluation) / len(evaluation)),
            "protocol_active_seconds": len(evaluation) * WINDOW_SECONDS,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(not report["accepted"])


if __name__ == "__main__":
    main()
