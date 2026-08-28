from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt
from sklearn.cross_decomposition import CCA
from sklearn.metrics import confusion_matrix
import wfdb


FREQUENCIES = (6.66, 7.50, 8.57, 10.00)
INTENTS = ("select", "confirm", "cancel", "stop")
SUBJECTS = ("001", "002", "003", "004")
SAMPLE_RATE = 250
WINDOW_SECONDS = 2
WINDOW_SAMPLES = SAMPLE_RATE * WINDOW_SECONDS
STIMULUS_OFFSET = 3 * SAMPLE_RATE
REST_OFFSET = 3 * SAMPLE_RATE // 2
CHANNEL_NAMES = ("P7", "O1", "Oz", "O2", "P8")
FILTER_BANKS = ((5.0, 45.0), (10.0, 45.0), (15.0, 45.0), (20.0, 45.0))


def download(root: Path) -> None:
    files = [
        f"dataset2/T{subject}a.{suffix}"
        for subject in SUBJECTS
        for suffix in ("dat", "hea", "win")
    ]
    if all((root / name).is_file() for name in files):
        return
    wfdb.dl_files("mssvepdb", str(root), files, keep_subdirs=True, overwrite=False)


def target_frequency(note: str) -> float | None:
    try:
        value = float(note.strip())
    except ValueError:
        return None
    nearest = min(FREQUENCIES, key=lambda candidate: abs(candidate - value))
    return nearest if abs(nearest - value) <= 0.60 else None


def trials(annotation: wfdb.Annotation) -> list[tuple[int, int, float | None]]:
    result: list[tuple[int, int, float | None]] = []
    active: tuple[int, float | None] | None = None
    for sample, symbol, note in zip(
        annotation.sample,
        annotation.symbol,
        annotation.aux_note,
        strict=True,
    ):
        if symbol == "(":
            active = int(sample), target_frequency(note)
        elif symbol == ")" and active is not None:
            result.append((active[0], int(sample), active[1]))
            active = None
    return result


def channel_indices(record: wfdb.Record) -> tuple[int, ...]:
    names = {name: index for index, name in enumerate(record.sig_name)}
    missing = [name for name in CHANNEL_NAMES if name not in names]
    if missing:
        raise ValueError(f"missing occipital channels: {missing}")
    return tuple(names[name] for name in CHANNEL_NAMES)


def usable(samples: np.ndarray) -> bool:
    return bool(
        samples.shape[1] == WINDOW_SAMPLES
        and np.isfinite(samples).all()
        and np.all(samples.std(axis=1) > 1e-9)
        and np.max(np.abs(samples)) < 1e5
    )


def load_record(root: Path, subject: str) -> tuple[list[np.ndarray], list[int], list[np.ndarray]]:
    path = root / "dataset2" / f"T{subject}a"
    record = wfdb.rdrecord(str(path))
    annotation = wfdb.rdann(str(path), "win")
    channels = channel_indices(record)
    annotated = trials(annotation)
    active_windows: list[np.ndarray] = []
    labels: list[int] = []
    rest_windows: list[np.ndarray] = []
    for start, _, frequency in annotated:
        if frequency not in FREQUENCIES:
            continue
        samples = record.p_signal[
            start + STIMULUS_OFFSET : start + STIMULUS_OFFSET + WINDOW_SAMPLES,
            channels,
        ].T
        if usable(samples):
            active_windows.append(samples.astype(np.float32))
            labels.append(FREQUENCIES.index(frequency))
    for (_, end, _), (next_start, _, _) in zip(annotated, annotated[1:], strict=False):
        start = end + REST_OFFSET
        samples = record.p_signal[start : start + WINDOW_SAMPLES, channels].T
        if start + WINDOW_SAMPLES <= next_start and usable(samples):
            rest_windows.append(samples.astype(np.float32))
    return active_windows, labels, rest_windows


def references() -> list[np.ndarray]:
    time = np.arange(WINDOW_SAMPLES) / SAMPLE_RATE
    return [
        np.stack(
            [
                function(2 * np.pi * harmonic * frequency * time)
                for harmonic in (1, 2, 3, 4)
                for function in (np.sin, np.cos)
            ],
            axis=1,
        )
        for frequency in FREQUENCIES
    ]


def fbcca_scores(windows: np.ndarray) -> np.ndarray:
    result = np.zeros((len(windows), len(FREQUENCIES)), dtype=np.float64)
    reference_signals = references()
    for bank, band in enumerate(FILTER_BANKS, start=1):
        filtered = sosfiltfilt(
            butter(4, band, btype="bandpass", fs=SAMPLE_RATE, output="sos"),
            windows,
            axis=2,
        )
        filtered -= filtered.mean(axis=2, keepdims=True)
        filtered /= np.maximum(filtered.std(axis=2, keepdims=True), 1e-6)
        weight = bank ** -1.25 + 0.25
        for row, window in enumerate(filtered):
            x = window.T
            for column, reference in enumerate(reference_signals):
                x_c, y_c = CCA(n_components=1, max_iter=1000).fit_transform(x, reference)
                correlation = np.corrcoef(x_c[:, 0], y_c[:, 0])[0, 1]
                result[row, column] += weight * correlation * correlation
    return result


def probabilities(scores: np.ndarray, temperature: float = 0.1) -> np.ndarray:
    shifted = scores / temperature
    shifted -= shifted.max(axis=1, keepdims=True)
    values = np.exp(shifted)
    return values / values.sum(axis=1, keepdims=True)


def choose_threshold(active: np.ndarray, labels: np.ndarray, idle: np.ndarray) -> float:
    active_confidence = active.max(axis=1)
    active_prediction = active.argmax(axis=1)
    idle_confidence = idle.max(axis=1)
    candidates = sorted(set(np.concatenate((active_confidence, idle_confidence)).tolist()))
    eligible = []
    for candidate in candidates:
        accepted = active_confidence >= candidate
        coverage = float(accepted.mean())
        accuracy = float((active_prediction[accepted] == labels[accepted]).mean()) if accepted.any() else 0.0
        if coverage >= 0.50 and accuracy >= 0.70:
            eligible.append((float((idle_confidence >= candidate).mean()), -accuracy, -coverage, candidate))
    return min(eligible)[3] if eligible else 1.0


def evaluate(active: np.ndarray, labels: np.ndarray, idle: np.ndarray, threshold: float) -> dict[str, object]:
    confidence = active.max(axis=1)
    prediction = active.argmax(axis=1)
    accepted = confidence >= threshold
    false_idle = int(np.count_nonzero(idle.max(axis=1) >= threshold))
    idle_minutes = len(idle) * WINDOW_SECONDS / 60.0
    return {
        "accuracy": float((prediction == labels).mean()),
        "accepted_accuracy": float((prediction[accepted] == labels[accepted]).mean()) if accepted.any() else 0.0,
        "coverage": float(accepted.mean()),
        "threshold": threshold,
        "idle_windows": len(idle),
        "idle_false_activations": false_idle,
        "idle_false_activations_per_minute": false_idle / idle_minutes if idle_minutes else 0.0,
        "confusion_matrix": confusion_matrix(labels, prediction, labels=range(4)).tolist(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="MAMEM 256-channel two-second SSVEP and idle benchmark")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    download(args.data)
    loaded = {subject: load_record(args.data, subject) for subject in SUBJECTS}
    development_accuracy = {}
    for subject in ("001", "002"):
        subject_windows, subject_labels, _ = loaded[subject]
        subject_prediction = fbcca_scores(np.stack(subject_windows)).argmax(axis=1)
        development_accuracy[subject] = float(
            (subject_prediction == np.asarray(subject_labels)).mean()
        )
    calibration_windows, calibration_labels, calibration_idle = loaded["003"]
    test_windows, test_labels, test_idle = loaded["004"]
    calibration_probability = probabilities(fbcca_scores(np.stack(calibration_windows)))
    calibration_idle_probability = probabilities(fbcca_scores(np.stack(calibration_idle)))
    test_probability = probabilities(fbcca_scores(np.stack(test_windows)))
    test_idle_probability = probabilities(fbcca_scores(np.stack(test_idle)))
    threshold = choose_threshold(
        calibration_probability,
        np.asarray(calibration_labels),
        calibration_idle_probability,
    )
    metrics = evaluate(
        test_probability,
        np.asarray(test_labels),
        test_idle_probability,
        threshold,
    )
    report = {
        "accepted": bool(
            metrics["accuracy"] >= 0.70
            and metrics["accepted_accuracy"] >= 0.80
            and metrics["coverage"] >= 0.50
            and metrics["idle_false_activations_per_minute"] <= 1.0
        ),
        "dataset": "PhysioNet MAMEM SSVEP Database v1.0.0 experiment 2",
        "license": "ODC-By-1.0",
        "channels": list(CHANNEL_NAMES),
        "source_channel_count": 256,
        "sample_rate_hz": SAMPLE_RATE,
        "window_seconds": WINDOW_SECONDS,
        "split": {
            "development_subjects": ["001", "002"],
            "calibration_subjects": ["003"],
            "test_subjects": ["004"],
            "session": "a",
        },
        "idle_source": "protocol-defined five-second rest intervals",
        "development_accuracy": development_accuracy,
        "metrics": metrics,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(not report["accepted"])


if __name__ == "__main__":
    main()
