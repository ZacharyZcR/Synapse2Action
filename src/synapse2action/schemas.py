from __future__ import annotations

from copy import deepcopy
from typing import Any

from .contracts import RESULT_SCHEMA_VERSION, SCHEMA_VERSION


def _object(properties: dict[str, Any], required: tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


CONTRACT_SCHEMAS: dict[str, dict[str, Any]] = {
    "intent": _object(
        {
            "schema_version": {"const": SCHEMA_VERSION},
            "kind": {"enum": ["select", "confirm", "cancel", "stop"]},
            "target": {"type": ["string", "null"]},
            "target_revision": {"type": ["integer", "null"], "minimum": 0},
            "challenge_token": {"type": ["string", "null"]},
            "at_ms": {"type": ["integer", "null"], "minimum": 0},
        },
        ("schema_version", "kind", "target", "target_revision", "challenge_token", "at_ms"),
    ),
    "world_state": _object(
        {
            "schema_version": {"const": SCHEMA_VERSION},
            "observed_at_ms": {"type": "integer", "minimum": 0},
            "objects": {
                "type": "array",
                "items": _object(
                    {
                        "object_id": {"type": "string", "minLength": 1},
                        "revision": {"type": "integer", "minimum": 0},
                        "position": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 3,
                            "maxItems": 3,
                        },
                        "occupied": {"type": "boolean"},
                        "reachable": {"type": "boolean"},
                    },
                    ("object_id", "revision", "position", "occupied", "reachable"),
                ),
            },
        },
        ("schema_version", "observed_at_ms", "objects"),
    ),
    "plan": _object(
        {
            "schema_version": {"const": SCHEMA_VERSION},
            "decision": {"enum": ["execute", "refuse"]},
            "skill": {"type": ["string", "null"]},
            "arguments": {"type": ["object", "null"]},
            "reason": {"type": ["string", "null"]},
        },
        ("schema_version", "decision", "skill", "arguments", "reason"),
    ),
    "skill": _object(
        {
            "schema_version": {"const": SCHEMA_VERSION},
            "name": {"type": "string", "minLength": 1},
            "risk": {"enum": ["low", "medium", "high"]},
            "timeout_ms": {"type": "integer", "minimum": 1},
            "arguments": {"type": "object"},
        },
        ("schema_version", "name", "risk", "timeout_ms", "arguments"),
    ),
    "action": _object(
        {
            "schema_version": {"const": SCHEMA_VERSION},
            "skill": {"type": "string", "minLength": 1},
            "arguments": {"type": "object"},
            "steps": {"type": "array", "items": {"type": "string"}},
        },
        ("schema_version", "skill", "arguments", "steps"),
    ),
    "result": _object(
        {
            "schema_version": {"const": RESULT_SCHEMA_VERSION},
            "success": {"type": "boolean"},
            "outcome_success": {"type": "boolean"},
            "process_compliance": {"type": "boolean"},
            "safety_passed": {"type": "boolean"},
            "detail": {"type": "string"},
            "duration_ms": {"type": "integer", "minimum": 0},
        },
        (
            "schema_version",
            "success",
            "outcome_success",
            "process_compliance",
            "safety_passed",
            "detail",
            "duration_ms",
        ),
    ),
}


def contract_catalog() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "format": "synapse2action.contract_catalog",
        "schemas": deepcopy(CONTRACT_SCHEMAS),
    }
