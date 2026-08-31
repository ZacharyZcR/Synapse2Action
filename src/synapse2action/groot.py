from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import Action
from .task_spec import TaskSpec


@dataclass(slots=True)
class GrootPolicy:
    """Bind an approved Harness action to the public GR00T G1 policy."""

    task: TaskSpec
    prepared: list[Action] = field(default_factory=list)

    def prepare(self, action: Action) -> Action:
        self.task.validate_action(action.skill, action.arguments)
        prepared = Action(
            action.skill,
            action.arguments,
            ("groot_vla", "whole_body_control", "strict_physical_verification"),
        )
        self.prepared.append(prepared)
        return prepared


@dataclass(slots=True)
class ExternalVLAPolicy:
    """Bind an approved action to a named external VLA runtime without scripted steps."""

    task: TaskSpec
    runtime: str
    prepared: list[Action] = field(default_factory=list)

    def prepare(self, action: Action) -> Action:
        if not self.runtime:
            raise ValueError("external VLA runtime must be named")
        self.task.validate_action(action.skill, action.arguments)
        prepared = Action(action.skill, action.arguments, (self.runtime,))
        self.prepared.append(prepared)
        return prepared
