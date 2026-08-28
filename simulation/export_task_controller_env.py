from __future__ import annotations

import argparse
from pathlib import Path

from synapse2action.task_spec import load_task_spec


def csv(values) -> str:
    return ",".join(str(value) for value in values)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a TaskSpec for the G1 controller container")
    parser.add_argument("task_spec", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    controller = load_task_spec(args.task_spec).controller
    values = {
        "S2A_MANIPULATION_JOINTS": csv(controller.joint_indices),
        "S2A_MANIPULATION_STAND": csv(controller.stand),
        "S2A_MANIPULATION_GRASP": csv(controller.grasp),
        "S2A_MANIPULATION_LIFT": csv(controller.lift),
        "S2A_MANIPULATION_TRANSPORT": csv(controller.transport),
        "S2A_MANIPULATION_PHASE_END_SECONDS": csv(controller.phase_end_s),
        "S2A_MANIPULATION_START_DELAY_SECONDS": str(controller.start_delay_s),
    }
    args.output.write_text("".join(f"{name}={value}\n" for name, value in values.items()))


if __name__ == "__main__":
    main()
