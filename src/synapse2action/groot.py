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
