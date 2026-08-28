from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any


def _load_report(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        report = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid planner report: {path}") from exc
    required = {
        "schema_version",
        "benchmark",
        "model",
        "accepted",
        "passed",
        "failed",
        "metrics",
        "acceptance",
        "results",
    }
    if not isinstance(report, dict) or set(report) != required:
        raise ValueError(f"planner report has unexpected fields: {path}")
    if report["schema_version"] != 1 or report["benchmark"] != "live_planner_provider":
        raise ValueError(f"unsupported planner report: {path}")
    if not isinstance(report["model"], str) or not report["model"]:
        raise ValueError(f"planner report has no model: {path}")
    if type(report["accepted"]) is not bool:
        raise ValueError(f"planner report has invalid acceptance: {path}")
    return {
        "model": report["model"],
        "accepted": report["accepted"],
        "passed": report["passed"],
        "failed": report["failed"],
        "schema_compliance_rate": report["metrics"]["schema_compliance_rate"],
        "unsafe_action_executions": report["metrics"]["unsafe_action_executions"],
        "provider_errors": report["metrics"]["provider_errors"],
        "latency_ms_p95": report["metrics"]["latency_ms_p95"],
        "artifact": str(path),
        "sha256": sha256(raw).hexdigest(),
    }


def summarize_planner_providers(
    paths: list[Path],
    required_models: list[str] | None = None,
) -> dict[str, Any]:
    providers = [_load_report(path) for path in paths]
    models = [provider["model"] for provider in providers]
    if len(models) != len(set(models)):
        raise ValueError("planner provider reports must use unique model names")
    required = sorted(set(required_models or ()))
    missing = sorted(set(required) - set(models))
    rejected = sorted(provider["model"] for provider in providers if not provider["accepted"])
    accepted = bool(providers) and not missing and not rejected
    return {
        "schema_version": 1,
        "benchmark": "planner_provider_summary",
        "accepted": accepted,
        "required_models": required,
        "missing_models": missing,
        "rejected_models": rejected,
        "providers": sorted(providers, key=lambda provider: provider["model"]),
    }
