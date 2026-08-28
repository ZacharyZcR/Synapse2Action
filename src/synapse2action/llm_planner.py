from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.request import Request, urlopen

from .contracts import Action


Transport = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "skill": {"type": "string", "enum": ["pick_and_place"]},
        "arguments": {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "destination": {"type": "string"},
            },
            "required": ["target", "destination"],
            "additionalProperties": False,
        },
    },
    "required": ["skill", "arguments"],
    "additionalProperties": False,
}


def _decode_plan(response: dict[str, Any], target: str, destination: str) -> Action:
    try:
        content = response["choices"][0]["message"]["content"]
        plan = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("planner returned an invalid Chat Completions response") from exc
    if not isinstance(plan, dict) or set(plan) != {"skill", "arguments"}:
        raise ValueError("planner response does not match plan schema")
    arguments = plan["arguments"]
    if plan["skill"] != "pick_and_place" or not isinstance(arguments, dict):
        raise ValueError("planner response does not match plan schema")
    if set(arguments) != {"target", "destination"}:
        raise ValueError("planner response does not match plan schema")
    if not all(type(arguments[key]) is str for key in ("target", "destination")):
        raise ValueError("planner response does not match plan schema")
    if arguments["target"] != target or arguments["destination"] != destination:
        raise ValueError("planner changed the authorized task context")
    return Action(plan["skill"], arguments)


def _urllib_transport(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


@dataclass(slots=True)
class OpenAICompatiblePlanner:
    base_url: str
    model: str
    destination: str = "drop_zone"
    api_key: str | None = None
    timeout_seconds: float = 30.0
    transport: Transport = _urllib_transport

    def plan(self, target: str) -> Action:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Select exactly one registered robot skill. Return only the requested JSON object.",
                },
                {
                    "role": "user",
                    "content": f"Move target {target!r} to destination {self.destination!r}.",
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "robot_plan",
                    "strict": True,
                    "schema": PLAN_SCHEMA,
                },
            },
            "temperature": 0,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = self.transport(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers,
            payload,
            self.timeout_seconds,
        )
        return _decode_plan(response, target, self.destination)
