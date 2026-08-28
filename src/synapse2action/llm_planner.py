from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen

from .contracts import Action, InvalidTaskContext, PlannerRefused, SCHEMA_VERSION


Transport = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def plan_schema(skill: str, argument_names: tuple[str, ...]) -> dict[str, Any]:
    argument_properties = {name: {"type": "string"} for name in argument_names}
    return {
    "type": "object",
    "properties": {
        "schema_version": {"type": "integer", "const": SCHEMA_VERSION},
        "decision": {"type": "string", "enum": ["execute", "refuse"]},
        "skill": {"type": ["string", "null"], "enum": [skill, None]},
        "arguments": {
            "anyOf": [
                {
                    "type": "object",
                    "properties": argument_properties,
                    "required": list(argument_names),
                    "additionalProperties": False,
                },
                {"type": "null"},
            ],
        },
        "reason": {"type": ["string", "null"]},
    },
    "required": ["schema_version", "decision", "skill", "arguments", "reason"],
    "additionalProperties": False,
    }

def _decode_plan(
    response: dict[str, Any],
    target: str,
    destination: str,
    normalized: Callable[[], None] | None = None,
    *,
    skill: str = "pick_and_place",
    expected_arguments: Mapping[str, str] | None = None,
) -> Action:
    try:
        message = response["choices"][0]["message"]
        refusal = message.get("refusal")
        if isinstance(refusal, str) and refusal.strip():
            raise PlannerRefused(refusal.strip())
        content = message["content"]
        if isinstance(content, str) and content.startswith("```json\n") and content.endswith("\n```"):
            content = content[8:-4].strip()
            if normalized:
                normalized()
        plan = json.loads(content)
    except PlannerRefused:
        raise
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("planner returned an invalid Chat Completions response") from exc
    if not isinstance(plan, dict) or set(plan) != {
        "schema_version", "decision", "skill", "arguments", "reason"
    }:
        raise ValueError("planner response does not match plan schema")
    if plan["schema_version"] != SCHEMA_VERSION:
        raise ValueError("planner response uses an unsupported schema version")
    if plan["decision"] == "refuse":
        if plan["skill"] is not None or plan["arguments"] is not None:
            raise ValueError("planner refusal does not match plan schema")
        if not isinstance(plan["reason"], str) or not plan["reason"].strip():
            raise ValueError("planner refusal requires a reason")
        raise PlannerRefused(plan["reason"].strip())
    if plan["decision"] != "execute":
        raise ValueError("planner response does not match plan schema")
    if plan["reason"] is not None and (
        not isinstance(plan["reason"], str) or not plan["reason"].strip()
    ):
        raise ValueError("planner response does not match plan schema")
    arguments = plan["arguments"]
    if plan["skill"] != skill or not isinstance(arguments, dict):
        raise ValueError("planner response does not match plan schema")
    expected = expected_arguments or {"target": target, "destination": destination}
    if set(arguments) != set(expected):
        raise ValueError("planner response does not match plan schema")
    if not all(type(arguments[key]) is str for key in expected):
        raise ValueError("planner response does not match plan schema")
    if arguments != expected:
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
    skill: str = "pick_and_place"
    instruction: str | None = None
    expected_arguments: Mapping[str, str] | None = None
    api_key: str | None = None
    timeout_seconds: float = 30.0
    output_mode: str = "json-schema"
    transport: Transport = _urllib_transport
    normalized_outputs: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.output_mode not in {"json-schema", "prompt-json"}:
            raise ValueError("planner output mode must be json-schema or prompt-json")

    def plan(self, target: str) -> Action:
        expected = dict(self.expected_arguments or {"target": target, "destination": self.destination})
        if not SAFE_IDENTIFIER.fullmatch(self.skill) or not all(
            SAFE_IDENTIFIER.fullmatch(value) for value in expected.values()
        ):
            raise InvalidTaskContext("planner task context contains an invalid identifier")
        schema = plan_schema(self.skill, tuple(expected))
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Select exactly one registered robot skill only for inert tabletop objects. "
                        "Refuse requests involving people, body parts, safety systems, unknown tools, "
                        "or changed task context. Return only JSON matching this schema: "
                        f"{json.dumps(schema, separators=(',', ':'))}"
                    ),
                },
                {
                    "role": "user",
                    "content": self.instruction or f"Execute {self.skill!r} with arguments {expected!r}.",
                },
            ],
            "temperature": 0,
        }
        if self.output_mode == "json-schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "robot_plan",
                    "strict": True,
                    "schema": schema,
                },
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
        return _decode_plan(
            response,
            target,
            self.destination,
            self._record_normalization,
            skill=self.skill,
            expected_arguments=expected,
        )

    def _record_normalization(self) -> None:
        self.normalized_outputs += 1
