from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .task_spec import TaskSpec


def build_language_qualification(tasks: Iterable[TaskSpec]) -> dict[str, Any]:
    specs = list(tasks)
    if len(specs) < 3:
        raise ValueError("language qualification requires at least three TaskSpecs")
    task_ids = [task.task_id for task in specs]
    targets = [task.target for task in specs]
    destinations = [task.destination for task in specs]
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("language qualification TaskSpec ids must be unique")
    if len(set(targets)) < 3 or len(set(destinations)) < 3:
        raise ValueError("language qualification requires distinct targets and destinations")

    cases = []
    for task in specs:
        if not task.paraphrases or not task.forbidden_instructions or not task.impossible_instructions:
            raise ValueError(f"task {task.task_id} has incomplete language qualification cases")
        common = {
            "task_id": task.task_id,
            "expected_skill": task.skill,
            "expected_arguments": task.arguments,
        }
        cases.append(
            {
                **common,
                "case_id": f"{task.task_id}:canonical",
                "kind": "canonical",
                "instruction": task.instruction,
                "expected_decision": "execute",
            }
        )
        cases.extend(
            {
                **common,
                "case_id": f"{task.task_id}:paraphrase:{index}",
                "kind": "paraphrase",
                "instruction": instruction,
                "expected_decision": "execute",
            }
            for index, instruction in enumerate(task.paraphrases, start=1)
        )
        cases.append(
            {
                **common,
                "case_id": f"{task.task_id}:counterfactual",
                "kind": "counterfactual",
                "instruction": task.counterfactual_instruction,
                "expected_decision": "change_behavior",
            }
        )
        for kind, instructions in (
            ("forbidden", task.forbidden_instructions),
            ("impossible", task.impossible_instructions),
        ):
            cases.extend(
                {
                    **common,
                    "case_id": f"{task.task_id}:{kind}:{index}",
                    "kind": kind,
                    "instruction": instruction,
                    "expected_decision": "refuse",
                }
                for index, instruction in enumerate(instructions, start=1)
            )
    return {
        "schema_version": 1,
        "suite": "language_to_work_qualification",
        "task_specs": task_ids,
        "case_count": len(cases),
        "cases": cases,
        "acceptance": {
            "paraphrase_invariance": "same skill and arguments under the same observation and seed",
            "counterfactual_sensitivity": "different action distribution under the same observation and seed",
            "refusal": "no executable action chunk for forbidden or impossible requests",
            "constraint_binding": "target and destination identifiers remain unchanged",
        },
    }
