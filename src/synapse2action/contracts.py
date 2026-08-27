from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Protocol


class IntentKind(StrEnum):
    SELECT = "select"
    CONFIRM = "confirm"
    CANCEL = "cancel"
    STOP = "stop"


class TaskState(StrEnum):
    IDLE = "idle"
    TARGET_SELECTED = "target_selected"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    ARMED = "armed"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EMERGENCY_STOPPED = "emergency_stopped"


@dataclass(frozen=True, slots=True)
class Intent:
    kind: IntentKind
    target: str | None = None


@dataclass(frozen=True, slots=True)
class Action:
    skill: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    success: bool
    detail: str


@dataclass(frozen=True, slots=True)
class TraceRecord:
    sequence: int
    event: str
    state: TaskState
    detail: str = ""


class Planner(Protocol):
    def plan(self, target: str) -> Action: ...


class Robot(Protocol):
    def execute(self, action: Action) -> ExecutionResult: ...

    def stop(self) -> None: ...


class Verifier(Protocol):
    def verify(self, result: ExecutionResult) -> bool: ...
