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
        "provider",
        "model",
        "output_mode",
        "accepted",
        "passed",
        "failed",
        "metrics",
        "acceptance",
        "results",
    }
    if not isinstance(report, dict) or set(report) != required:
        raise ValueError(f"planner report has unexpected fields: {path}")
    if report["schema_version"] != 2 or report["benchmark"] != "live_planner_provider":
        raise ValueError(f"unsupported planner report: {path}")
    if not all(isinstance(report[key], str) and report[key] for key in ("provider", "model")):
        raise ValueError(f"planner report has no provider or model: {path}")
    if report["output_mode"] not in {"json-schema", "prompt-json"}:
        raise ValueError(f"planner report has invalid output mode: {path}")
    if type(report["accepted"]) is not bool:
        raise ValueError(f"planner report has invalid acceptance: {path}")
    return {
        "provider": report["provider"],
        "model": report["model"],
        "identity": f'{report["provider"]}/{report["model"].lstrip("/")}',
        "output_mode": report["output_mode"],
        "accepted": report["accepted"],
        "passed": report["passed"],
        "failed": report["failed"],
        "schema_compliance_rate": report["metrics"]["schema_compliance_rate"],
        "unsafe_action_executions": report["metrics"]["unsafe_action_executions"],
        "provider_errors": report["metrics"]["provider_errors"],
        "normalized_outputs": report["metrics"]["normalized_outputs"],
        "latency_ms_p95": report["metrics"]["latency_ms_p95"],
        "artifact": str(path),
        "sha256": sha256(raw).hexdigest(),
    }


def summarize_planner_providers(
    paths: list[Path],
    required_models: list[str] | None = None,
) -> dict[str, Any]:
    providers = [_load_report(path) for path in paths]
    identities = [provider["identity"] for provider in providers]
    if len(identities) != len(set(identities)):
        raise ValueError("planner provider reports must use unique identities")
    required = sorted(set(required_models or ()))
    missing = sorted(set(required) - set(identities))
    rejected = sorted(provider["identity"] for provider in providers if not provider["accepted"])
    accepted = bool(providers) and not missing and not rejected
    return {
        "schema_version": 1,
        "benchmark": "planner_provider_summary",
        "accepted": accepted,
        "required_models": required,
        "missing_models": missing,
        "rejected_models": rejected,
        "providers": sorted(providers, key=lambda provider: provider["identity"]),
    }
