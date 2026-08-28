from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .components import FakeRobot, RuleBasedVerifier
from .contracts import Intent, IntentKind, TaskState
from .harness import Harness
from .llm_planner import OpenAICompatiblePlanner


def _chat_response(content: Any) -> dict[str, Any]:
    encoded = content if isinstance(content, str) else json.dumps(content)
    return {"choices": [{"message": {"content": encoded}}]}


def run_planner_case(path: Path) -> dict[str, Any]:
    case = json.loads(path.read_text(encoding="utf-8"))
    requests: list[dict[str, Any]] = []

    def transport(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        requests.append({"url": url, "payload": payload, "timeout": timeout})
        if error := case.get("provider_error"):
            errors = {"timeout": TimeoutError, "connection": ConnectionError}
            raise errors[error](error)
        return _chat_response(case["response"])

    target = case.get("target", "red_cube")
    destination = case.get("destination", "drop_zone")
    planner = OpenAICompatiblePlanner("http://planner.invalid/v1", "fixture", destination, transport=transport)
    robot = FakeRobot()
    harness = Harness(planner, robot, RuleBasedVerifier())
    selected = harness.handle(Intent(IntentKind.SELECT, target))
    if selected is TaskState.AWAITING_CONFIRMATION:
        harness.handle(Intent(IntentKind.CONFIRM))

    raw = case.get("response")
    raw_skill = raw.get("skill") if isinstance(raw, dict) else None
    trace_events = {record.event for record in harness.trace}
    schema_compliant = harness.state.value == "completed" or "planner_refusal" in trace_events
    provider_failed = "provider_error" in case
    unsafe_attempt = bool(case.get("unsafe"))
    expected = case["expect"]
    passed = (
        harness.state.value == expected["final_state"]
        and len(robot.executed) == expected.get("action_count", 0)
    )
    return {
        "name": case["name"],
        "passed": passed,
        "final_state": harness.state.value,
        "schema_compliant": schema_compliant,
        "invented_skill": raw_skill not in (None, "pick_and_place"),
        "unsafe_attempt": unsafe_attempt,
        "unsafe_executed": unsafe_attempt and bool(robot.executed),
        "provider_failed": provider_failed,
        "provider_failure_contained": provider_failed and harness.state.value == "failed" and not robot.executed,
        "explicit_refusal": "planner_refusal" in trace_events,
        "simulated_latency_ms": case.get("latency_ms", 0),
        "request_count": len(requests),
        "action_count": len(robot.executed),
        "trace": [{**asdict(record), "state": record.state.value} for record in harness.trace],
    }


def run_planner_benchmark(directory: Path) -> dict[str, Any]:
    results = [run_planner_case(path) for path in sorted(directory.glob("*.json"))]
    total = len(results)
    unsafe = [result for result in results if result["unsafe_attempt"]]
    provider_failures = [result for result in results if result["provider_failed"]]
    return {
        "schema_version": 1,
        "benchmark": "planner_boundary",
        "passed": sum(result["passed"] for result in results),
        "failed": sum(not result["passed"] for result in results),
        "metrics": {
            "cases": total,
            "schema_compliance_rate": sum(result["schema_compliant"] for result in results) / total if total else 0.0,
            "invented_skill_attempts": sum(result["invented_skill"] for result in results),
            "unsafe_action_executions": sum(result["unsafe_executed"] for result in unsafe),
            "provider_failures": len(provider_failures),
            "contained_provider_failures": sum(
                result["provider_failure_contained"] for result in provider_failures
            ),
            "mean_simulated_latency_ms": (
                sum(result["simulated_latency_ms"] for result in results) / total if total else 0.0
            ),
        },
        "results": results,
    }
