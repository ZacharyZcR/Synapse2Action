from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def run_llm_vla_benchmark(
    report_path: Path,
    counterfactual_path: Path | None = None,
) -> dict[str, Any]:
    source = json.loads(report_path.read_text(encoding="utf-8"))
    planner = source.get("planner")
    simulator = source.get("unitree_simulator")
    if not isinstance(planner, dict) or not isinstance(simulator, dict):
        raise ValueError("report does not contain Planner and VLA simulator evidence")
    plan = planner.get("output")
    runtime = simulator.get("vla_runtime")
    plan_available = bool(
        planner.get("status") == "completed"
        and isinstance(plan, dict)
        and plan.get("skill") == "pick_and_place"
        and isinstance(plan.get("arguments"), dict)
    )
    arguments = plan.get("arguments", {}) if isinstance(plan, dict) else {}
    binding = simulator.get("vla_task_binding")
    task_binding_proven = bool(
        plan_available
        and isinstance(binding, dict)
        and binding.get("skill") == plan.get("skill")
        and binding.get("arguments") == arguments
        and binding.get("source") == "planner_action"
    )
    chunks_received = (
        int(runtime.get("chunks_received", 0))
        if isinstance(runtime, dict)
        else 0
    )
    first_chunk_latency = simulator.get("vla_first_chunk_latency_ms")
    chunk_coverage = (
        runtime.get("minimum_chunk_coverage_ms")
        if isinstance(runtime, dict)
        else None
    )
    latency_observable = isinstance(first_chunk_latency, (int, float))
    latency_within_budget = bool(
        latency_observable
        and isinstance(chunk_coverage, (int, float))
        and first_chunk_latency <= chunk_coverage
    )
    stale_fallbacks = (
        int(runtime.get("stale_fallbacks", 0))
        if isinstance(runtime, dict)
        else 0
    )
    counterfactual = simulator.get("vla_plan_counterfactual")
    if counterfactual_path is not None:
        counterfactual = json.loads(counterfactual_path.read_text(encoding="utf-8"))
    counterfactual_measured = bool(
        isinstance(counterfactual, dict)
        and counterfactual.get("changed") is True
        and counterfactual.get("same_observation") is True
        and counterfactual.get("same_seed") is True
    )
    metrics = {
        "plan_contract_valid": plan_available,
        "task_binding_proven": task_binding_proven,
        "vla_chunks_received": chunks_received,
        "chunk_stream_available": chunks_received > 0,
        "first_chunk_latency_observable": latency_observable,
        "first_chunk_latency_ms": first_chunk_latency,
        "minimum_chunk_coverage_ms": chunk_coverage,
        "first_chunk_latency_within_coverage": latency_within_budget,
        "stale_fallbacks": stale_fallbacks,
        "runtime_accepted": bool(isinstance(runtime, dict) and runtime.get("accepted") is True),
        "counterfactual_plan_responsiveness_measured": counterfactual_measured,
    }
    acceptance = {
        "require_plan_contract": True,
        "require_task_binding": True,
        "min_chunks_received": 1,
        "require_first_chunk_latency": True,
        "max_stale_fallbacks": 0,
        "require_counterfactual_plan_responsiveness": True,
    }
    accepted = bool(
        metrics["plan_contract_valid"]
        and metrics["task_binding_proven"]
        and metrics["vla_chunks_received"] >= acceptance["min_chunks_received"]
        and metrics["first_chunk_latency_within_coverage"]
        and metrics["stale_fallbacks"] <= acceptance["max_stale_fallbacks"]
        and metrics["runtime_accepted"]
        and metrics["counterfactual_plan_responsiveness_measured"]
    )
    return {
        "schema_version": 1,
        "benchmark": "llm_to_vla_boundary",
        "accepted": accepted,
        "source_report": str(report_path),
        "counterfactual_report": str(counterfactual_path) if counterfactual_path else None,
        "planner": {
            "provider": planner.get("provider"),
            "model": planner.get("model"),
            "plan": plan,
        },
        "metrics": metrics,
        "acceptance": acceptance,
        "diagnosis": {
            "task_binding": (
                "proven from structured plan arguments"
                if task_binding_proven
                else "missing structured proof that the Planner output became the VLA task"
            ),
            "latency": (
                "measured"
                if latency_observable
                else "only aggregate/max chunk latency is present; first-chunk latency is missing"
            ),
            "counterfactual": (
                "measured"
                if metrics["counterfactual_plan_responsiveness_measured"]
                else "no paired plan-change experiment proves that VLA output responds to the plan"
            ),
        },
    }
