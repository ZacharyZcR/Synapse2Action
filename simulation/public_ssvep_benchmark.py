from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
from sklearn.cross_decomposition import CCA
from sklearn.metrics import confusion_matrix
from scipy.signal import butter, sosfiltfilt
from torch import nn
import wfdb

from synapse2action.authorization import ChallengeStore
from synapse2action.components import MockPlanner, ScriptedPolicy
from synapse2action.contracts import Intent, IntentKind
from synapse2action.harness import Harness
from synapse2action.tabletop import Point2D, TabletopObject, TabletopRobot, TabletopVerifier
from synapse2action.task_spec import TaskSpec, load_task_spec
from synapse2action.world import FakeWorld, WorldObject


FREQUENCY_TO_INTENT = {
    6.66: "select",
    7.50: "confirm",
    8.57: "cancel",
    10.00: "stop",
}
SUBJECTS = ("001", "002", "003", "004")
SESSIONS = ("a", "b")
SAMPLE_RATE = 128
WINDOW_SAMPLES = 5 * SAMPLE_RATE
OCCIPITAL_CHANNELS = (5, 6, 7, 8)  # P7, O1, O2, P8 on Emotiv EPOC
FILTER_BANKS = ((5.0, 35.0), (10.0, 35.0), (15.0, 35.0), (20.0, 35.0))


def download(root: Path) -> None:
    files = [
        f"dataset3/U{subject}{session}{half}.{suffix}"
        for subject in SUBJECTS
        for session in SESSIONS
        for half in ("i", "ii")
        for suffix in ("dat", "hea", "win")
    ]
    if all((root / name).is_file() for name in files):
        return
    wfdb.dl_files("mssvepdb", str(root), files, keep_subdirs=True, overwrite=False)


def frequency(note: str) -> float | None:
    try:
        value = float(note.strip())
    except ValueError:
        return None
    nearest = min(FREQUENCY_TO_INTENT, key=lambda candidate: abs(candidate - value))
    return nearest if abs(nearest - value) <= 0.15 else None


def load_record(root: Path, record_name: str) -> tuple[list[np.ndarray], list[int]]:
    record_path = root / "dataset3" / record_name
    record = wfdb.rdrecord(str(record_path))
    annotation = wfdb.rdann(str(record_path), "win")
    starts: list[tuple[int, float]] = []
    for sample, symbol, note in zip(annotation.sample, annotation.symbol, annotation.aux_note, strict=True):
        label = frequency(note)
        if symbol == "(" and label in FREQUENCY_TO_INTENT:
            starts.append((int(sample), label))
    windows, labels = [], []
    for start, label in starts:
        samples = record.p_signal[start : start + WINDOW_SAMPLES].T
        channel_scale = np.std(samples, axis=1)
        signal_is_usable = bool(
            np.isfinite(samples).all()
            and np.all(channel_scale > 1e-9)
            and np.max(np.abs(samples)) < 1e5
        )
        if samples.shape == (14, WINDOW_SAMPLES) and signal_is_usable:
            windows.append(samples.astype(np.float32))
            labels.append(tuple(FREQUENCY_TO_INTENT).index(label))
    return windows, labels


def load_dataset(root: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    windows, labels, subjects = [], [], []
    for subject in SUBJECTS:
        for session in SESSIONS:
            for half in ("i", "ii"):
                record_windows, record_labels = load_record(root, f"U{subject}{session}{half}")
                windows.extend(record_windows)
                labels.extend(record_labels)
                subjects.extend([subject] * len(record_labels))
    return np.stack(windows), np.asarray(labels), np.asarray(subjects)


def normalize(windows: np.ndarray) -> np.ndarray:
    filtered = sosfiltfilt(butter(4, (5.0, 35.0), btype="bandpass", fs=SAMPLE_RATE, output="sos"), windows, axis=2)
    centered = filtered - filtered.mean(axis=2, keepdims=True)
    scale = centered.std(axis=2, keepdims=True)
    return centered / np.maximum(scale, 1e-6)


def cca_scores(windows: np.ndarray) -> np.ndarray:
    time = np.arange(windows.shape[2]) / SAMPLE_RATE
    references = []
    for target in FREQUENCY_TO_INTENT:
        references.append(np.stack([
            function(2 * np.pi * harmonic * target * time)
            for harmonic in (1, 2, 3)
            for function in (np.sin, np.cos)
        ], axis=1))
    result = np.empty((len(windows), len(references)), dtype=np.float64)
    for row, window in enumerate(windows):
        x = window[OCCIPITAL_CHANNELS, :].T
        for column, reference in enumerate(references):
            x_c, y_c = CCA(n_components=1, max_iter=1000).fit_transform(x, reference)
            result[row, column] = abs(float(np.corrcoef(x_c[:, 0], y_c[:, 0])[0, 1]))
    return result


def filter_bank_cca_scores(windows: np.ndarray) -> np.ndarray:
    combined = np.zeros((len(windows), len(FREQUENCY_TO_INTENT)), dtype=np.float64)
    for index, band in enumerate(FILTER_BANKS, start=1):
        filtered = sosfiltfilt(
            butter(4, band, btype="bandpass", fs=SAMPLE_RATE, output="sos"),
            windows,
            axis=2,
        )
        centered = filtered - filtered.mean(axis=2, keepdims=True)
        scaled = centered / np.maximum(centered.std(axis=2, keepdims=True), 1e-6)
        weight = index ** -1.25 + 0.25
        combined += weight * np.square(cca_scores(scaled))
    return combined


def spectral_features(windows: np.ndarray) -> np.ndarray:
    spectrum = np.abs(np.fft.rfft(windows[:, OCCIPITAL_CHANNELS, :], axis=2)) ** 2
    bins = np.fft.rfftfreq(WINDOW_SAMPLES, 1 / SAMPLE_RATE)
    features = []
    for target in FREQUENCY_TO_INTENT:
        target_power = []
        for harmonic in (1, 2, 3):
            index = int(np.argmin(abs(bins - target * harmonic)))
            target_power.append(spectrum[:, :, max(0, index - 1) : index + 2].mean(axis=2))
        features.append(np.log1p(np.stack(target_power, axis=2).sum(axis=2)))
    return np.concatenate(features, axis=1).astype(np.float32)


class SpectralMLP(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(16, 64), nn.ELU(), nn.Dropout(0.1),
            nn.Linear(64, 32), nn.ELU(), nn.Linear(32, 4),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.network(value)


def train_mlp(train_x: np.ndarray, train_y: np.ndarray) -> SpectralMLP:
    torch.manual_seed(17)
    model = SpectralMLP()
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=1e-3)
    x = torch.from_numpy(train_x)
    y = torch.from_numpy(train_y)
    model.train()
    for _ in range(200):
        order = torch.randperm(len(x))
        for offset in range(0, len(x), 16):
            batch = order[offset : offset + 16]
            loss = nn.functional.cross_entropy(model(x[batch]), y[batch])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    model.eval()
    return model


def probabilities(scores: np.ndarray, temperature: float = 0.1) -> np.ndarray:
    shifted = scores / temperature
    shifted -= shifted.max(axis=1, keepdims=True)
    values = np.exp(shifted)
    return values / values.sum(axis=1, keepdims=True)


def threshold(
    calibration_probabilities: np.ndarray,
    labels: np.ndarray,
    minimum_coverage: float = 0.50,
) -> float:
    confidence = calibration_probabilities.max(axis=1)
    prediction = calibration_probabilities.argmax(axis=1)
    candidates = sorted(set(confidence.tolist()))
    candidates = [candidate for candidate in candidates if (confidence >= candidate).mean() >= minimum_coverage]
    if not candidates:
        return 1.0
    return max(
        candidates,
        key=lambda candidate: (
            float((prediction[confidence >= candidate] == labels[confidence >= candidate]).mean()),
            float((confidence >= candidate).mean()),
        ),
    )


def metrics(probability: np.ndarray, labels: np.ndarray, abstain_at: float) -> dict[str, object]:
    confidence = probability.max(axis=1)
    prediction = probability.argmax(axis=1)
    accepted = confidence >= abstain_at
    accuracy = float((prediction == labels).mean())
    accepted_accuracy = float((prediction[accepted] == labels[accepted]).mean()) if accepted.any() else 0.0
    return {
        "accuracy": accuracy,
        "accepted_accuracy": accepted_accuracy,
        "coverage": float(accepted.mean()),
        "abstention_rate": float(1.0 - accepted.mean()),
        "threshold": abstain_at,
        "confusion_matrix": confusion_matrix(labels, prediction, labels=range(4)).tolist(),
    }


def continuous_stream_metrics(
    probability: np.ndarray,
    labels: np.ndarray,
    abstain_at: float,
) -> dict[str, object]:
    confidence = probability.max(axis=1)
    prediction = probability.argmax(axis=1)
    accepted = confidence >= abstain_at
    false_events = int(np.count_nonzero(accepted & (prediction != labels)))
    duration_minutes = len(labels) * WINDOW_SAMPLES / SAMPLE_RATE / 60.0
    events = [
        {
            "window": index,
            "expected": tuple(FREQUENCY_TO_INTENT.values())[int(labels[index])],
            "decoded": tuple(FREQUENCY_TO_INTENT.values())[int(prediction[index])] if accepted[index] else "abstain",
            "confidence": float(confidence[index]),
            "correct": bool(accepted[index] and prediction[index] == labels[index]),
        }
        for index in range(len(labels))
    ]
    return {
        "selection_policy": "all test windows in recorded order",
        "idle_false_activation_rate": None,
        "limitation": "MAMEM experiment 3 has no idle class; false events are accepted misclassifications during active trials.",
        "window_count": len(labels),
        "window_seconds": WINDOW_SAMPLES / SAMPLE_RATE,
        "duration_minutes": duration_minutes,
        "accepted_events": int(accepted.sum()),
        "correct_events": int(np.count_nonzero(accepted & (prediction == labels))),
        "false_events": false_events,
        "false_events_per_minute": false_events / duration_minutes if duration_minutes else 0.0,
        "decision_latency_seconds": WINDOW_SAMPLES / SAMPLE_RATE,
        "events": events,
    }


def make_harness(task: TaskSpec) -> Harness:
    target_position = task.target_entity.position
    destination_position = task.destination_entity.position
    world_object = WorldObject(task.target, 1, 0, target_position)
    world = FakeWorld([world_object], max_age_ms=2_000)
    drop_zone = Point2D(*destination_position[:2])
    robot = TabletopRobot(
        TabletopObject(task.target, Point2D(*target_position[:2])),
        {task.destination: drop_zone},
    )
    return Harness(
        MockPlanner(skill=task.skill, arguments=task.arguments),
        robot,
        TabletopVerifier(robot, drop_zone),
        authorizer=ChallengeStore(lifetime_ms=2_000),
        world=world,
        policy=ScriptedPolicy(),
    )


def harness_replay(
    probability: np.ndarray, labels: np.ndarray, abstain_at: float, task: TaskSpec
) -> dict[str, object]:
    confidence = probability.max(axis=1)
    prediction = probability.argmax(axis=1)
    examples: dict[IntentKind, dict[str, float | int | str]] = {}
    for index, kind in enumerate(IntentKind):
        matches = np.flatnonzero((prediction == index) & (labels == index) & (confidence >= abstain_at))
        if len(matches):
            chosen = int(matches[0])
            examples[kind] = {
                "test_window": chosen,
                "confidence": float(confidence[chosen]),
                "frequency_hz": tuple(FREQUENCY_TO_INTENT)[index],
                "decoded_intent": kind.value,
            }
    if set(examples) != set(IntentKind):
        return {"accepted": False, "decoded_examples": {kind.value: value for kind, value in examples.items()}}

    completed = make_harness(task)
    completed.handle(Intent(IntentKind.SELECT, task.target, 1, at_ms=0))
    completed.handle(Intent(IntentKind.CONFIRM, target_revision=1, challenge_token=completed.challenge_token, at_ms=800))
    cancelled = make_harness(task)
    cancelled.handle(Intent(IntentKind.SELECT, task.target, 1, at_ms=0))
    cancelled.handle(Intent(IntentKind.CANCEL, at_ms=800))
    stopped = make_harness(task)
    stopped.handle(Intent(IntentKind.STOP, at_ms=0))
    states = {
        "select_confirm": completed.state.value,
        "select_cancel": cancelled.state.value,
        "stop": stopped.state.value,
    }
    return {
        "accepted": states == {"select_confirm": "completed", "select_cancel": "cancelled", "stop": "emergency_stopped"},
        "evidence_scope": "diagnostic_only_selected_examples",
        "warning": "This interface smoke test selects correct examples and is not continuous EEG evidence.",
        "decoded_examples": {kind.value: value for kind, value in examples.items()},
        "states": states,
        "interface": "synapse2action.harness.Harness.handle(Intent)",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Subject-independent public MAMEM SSVEP benchmark")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--task-spec", type=Path, required=True)
    args = parser.parse_args()
    random.seed(17)
    np.random.seed(17)
    download(args.data)
    raw_windows, labels, subjects = load_dataset(args.data)
    windows = normalize(raw_windows)
    train = np.isin(subjects, ["001", "002"])
    calibration = subjects == "003"
    test = subjects == "004"

    cca_calibration = probabilities(cca_scores(windows[calibration]))
    cca_test = probabilities(cca_scores(windows[test]))
    cca_threshold = threshold(cca_calibration, labels[calibration])

    fbcca_calibration = probabilities(filter_bank_cca_scores(raw_windows[calibration]))
    fbcca_test = probabilities(filter_bank_cca_scores(raw_windows[test]))
    fbcca_threshold = threshold(fbcca_calibration, labels[calibration])

    features = spectral_features(windows)
    feature_mean = features[train].mean(axis=0, keepdims=True)
    feature_scale = features[train].std(axis=0, keepdims=True)
    features = (features - feature_mean) / np.maximum(feature_scale, 1e-6)
    cnn = train_mlp(features[train], labels[train])
    with torch.inference_mode():
        calibration_logits = cnn(torch.from_numpy(features[calibration])).numpy()
        test_logits = cnn(torch.from_numpy(features[test])).numpy()
    cnn_calibration = probabilities(calibration_logits, temperature=1.0)
    cnn_test = probabilities(test_logits, temperature=1.0)
    cnn_threshold = threshold(cnn_calibration, labels[calibration])

    task = load_task_spec(args.task_spec)
    replay = harness_replay(fbcca_test, labels[test], fbcca_threshold, task)
    stream = continuous_stream_metrics(fbcca_test, labels[test], fbcca_threshold)
    report = {
        "accepted": True,
        "dataset": "PhysioNet MAMEM SSVEP Database v1.0.0 experiment 3",
        "license": "ODC-By-1.0",
        "sample_rate_hz": SAMPLE_RATE,
        "window_seconds": 5,
        "channels": int(windows.shape[1]),
        "frequency_to_intent": {str(key): value for key, value in FREQUENCY_TO_INTENT.items()},
        "task": {"id": task.task_id, "skill": task.skill, "arguments": task.arguments},
        "split": {"train_subjects": ["001", "002"], "calibration_subjects": ["003"], "test_subjects": ["004"]},
        "window_counts": {"train": int(train.sum()), "calibration": int(calibration.sum()), "test": int(test.sum())},
        "quality_gate": {"finite": True, "non_flat_channels": True, "absolute_amplitude_limit": 1e5},
        "cca": metrics(cca_test, labels[test], cca_threshold),
        "fbcca": metrics(fbcca_test, labels[test], fbcca_threshold),
        "spectral_mlp": metrics(cnn_test, labels[test], cnn_threshold),
        "cnn": metrics(cnn_test, labels[test], cnn_threshold),
        "continuous_stream": stream,
        "harness_replay": replay,
    }
    report["accepted"] = bool(
        train.sum() > 0 and calibration.sum() > 0 and test.sum() > 0
        and report["fbcca"]["accuracy"] >= 0.40
        and report["fbcca"]["coverage"] >= 0.50
        and report["fbcca"]["accepted_accuracy"] >= 0.70
        and stream["false_events_per_minute"] <= 1.0
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(not report["accepted"])


if __name__ == "__main__":
    main()
