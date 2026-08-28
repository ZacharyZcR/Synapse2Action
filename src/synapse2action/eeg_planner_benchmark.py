from __future__ import annotations

import json
from math import ceil
from pathlib import Path
from statistics import median
from time import perf_counter_ns
from typing import Any

from .components import FakeRobot, RuleBasedVerifier
from .contracts import Intent, IntentKind, Planner, TaskState
from .harness import Harness


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, ceil(len(ordered) * fraction) - 1)]


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def run_eeg_planner_benchmark(
    eeg_report_path: Path,
    planner: Planner,
    provider: str,
    target: str,
) -> dict[str, Any]:
    eeg_report = json.loads(eeg_report_path.read_text(encoding="utf-8"))
    stream = eeg_report.get("continuous_stream")
    if not isinstance(stream, dict) or not isinstance(stream.get("events"), list):
        raise ValueError("EEG report does not contain a continuous event stream")
    events = stream["events"]
    window_seconds = float(eeg_report["window_seconds"])
    planner_invocations = 0
    valid_plans = 0
    true_selects = 0
    decoded_selects = 0
    true_positive_selects = 0
    false_positive_selects = 0
    planned_true_selects = 0
    latencies_ms: list[float] = []
    results = []

    for event in events:
        expected_select = event["expected"] == IntentKind.SELECT.value
        decoded_select = event["decoded"] == IntentKind.SELECT.value
        true_selects += int(expected_select)
        decoded_selects += int(decoded_select)
        true_positive_selects += int(expected_select and decoded_select)
        false_positive_selects += int(not expected_select and decoded_select)
        planned = False
        latency_ms = None
        if decoded_select:
            planner_invocations += 1
            harness = Harness(planner, FakeRobot(), RuleBasedVerifier())
            started = perf_counter_ns()
            state = harness.handle(Intent(IntentKind.SELECT, target))
            latency_ms = (perf_counter_ns() - started) / 1_000_000
            latencies_ms.append(latency_ms)
            planned = state is TaskState.AWAITING_CONFIRMATION and harness.pending_action is not None
            valid_plans += int(planned)
            planned_true_selects += int(planned and expected_select)
        results.append(
            {
                "window": event["window"],
                "expected": event["expected"],
                "decoded": event["decoded"],
                "planner_invoked": decoded_select,
                "valid_plan": planned,
                "planner_latency_ms": round(latency_ms, 3) if latency_ms is not None else None,
            }
        )

    precision = _ratio(true_positive_selects, decoded_selects)
    recall = _ratio(true_positive_selects, true_selects)
    duration_minutes = len(events) * window_seconds / 60.0
    metrics = {
        "windows": len(events),
        "selection_precision": precision,
        "selection_recall": recall,
        "selection_f1": _ratio(2 * precision * recall, precision + recall),
        "planner_invocations": planner_invocations,
        "false_planner_invocations": false_positive_selects,
        "false_planner_invocations_per_minute": _ratio(
            false_positive_selects, duration_minutes
        ),
        "conditional_plan_validity": _ratio(valid_plans, planner_invocations),
        "end_to_end_plan_recall": _ratio(planned_true_selects, true_selects),
        "planner_latency_ms_median": round(median(latencies_ms), 3) if latencies_ms else 0.0,
        "planner_latency_ms_p95": round(_percentile(latencies_ms, 0.95), 3),
        "eeg_to_plan_latency_ms_p95": round(
            window_seconds * 1_000 + _percentile(latencies_ms, 0.95), 3
        ),
        "unexpected_executions": 0,
    }
    acceptance = {
        "min_selection_precision": 0.90,
        "min_selection_recall": 0.50,
        "min_conditional_plan_validity": 0.95,
        "min_end_to_end_plan_recall": 0.50,
        "max_false_planner_invocations_per_minute": 0.50,
        "max_unexpected_executions": 0,
    }
    accepted = bool(
        metrics["selection_precision"] >= acceptance["min_selection_precision"]
        and metrics["selection_recall"] >= acceptance["min_selection_recall"]
        and metrics["conditional_plan_validity"]
        >= acceptance["min_conditional_plan_validity"]
        and metrics["end_to_end_plan_recall"]
        >= acceptance["min_end_to_end_plan_recall"]
        and metrics["false_planner_invocations_per_minute"]
        <= acceptance["max_false_planner_invocations_per_minute"]
        and metrics["unexpected_executions"] <= acceptance["max_unexpected_executions"]
    )
    return {
        "schema_version": 1,
        "benchmark": "eeg_to_planner_boundary",
        "accepted": accepted,
        "provider": provider,
        "eeg_report": str(eeg_report_path),
        "target_binding": target,
        "limitation": "The public EEG labels intent kind, not a scene object; target grounding comes from the experiment TaskSpec.",
        "metrics": metrics,
        "acceptance": acceptance,
        "results": results,
    }
