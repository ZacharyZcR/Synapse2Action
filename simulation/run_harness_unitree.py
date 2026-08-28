from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from synapse2action.components import MockPlanner, ScriptedPolicy
from synapse2action.contracts import Intent, IntentKind, TaskState
from synapse2action.harness import Harness
from synapse2action.navigation import Pose2D
from synapse2action.unitree_simulation import (
    NavigateToPlanner,
    UnitreePickPlaceSimulationRobot,
    UnitreePickPlaceVerifier,
    UnitreeSimulationRobot,
    UnitreeSimulationVerifier,
    unitree_pick_place_skill_registry,
)


def decoded_execution_intents(path: Path | None) -> tuple[IntentKind, IntentKind]:
    if path is None:
        return IntentKind.SELECT, IntentKind.CONFIRM
    payload = json.loads(path.read_text())
    replay = payload.get("harness_replay", {})
    examples = replay.get("decoded_examples", {})
    if payload.get("accepted") is not True or replay.get("accepted") is not True:
        raise ValueError("public EEG benchmark was not accepted")
    decoded = tuple(IntentKind(examples[name]["decoded_intent"]) for name in ("select", "confirm"))
    if decoded != (IntentKind.SELECT, IntentKind.CONFIRM):
        raise ValueError("public EEG did not decode the execution authorization sequence")
    return decoded


def main() -> int:
    parser = argparse.ArgumentParser(description="Run confirmed navigation through SDK2 G1 MuJoCo")
    parser.add_argument("--task", choices=("navigation", "pick-place"), default="navigation")
    parser.add_argument("--policy", choices=("scripted", "smolvla"), default="scripted")
    parser.add_argument("--destination", default="point_b")
    parser.add_argument("--target-x", type=float, default=0.8)
    parser.add_argument("--target-y", type=float, default=0.0)
    parser.add_argument("--target-yaw", type=float, default=0.0)
    parser.add_argument("--decoded-intents", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    project = Path(__file__).resolve().parents[1]
    if args.task == "pick-place":
        smolvla = args.policy == "smolvla"
        robot = UnitreePickPlaceSimulationRobot(
            project / "simulation" / (
                "run_smolvla_g1_closed_loop.sh" if smolvla else "run_unitree_pick_place.sh"
            ),
            project / "reports" / "simulation",
            timeout_seconds=120.0 if smolvla else 30.0,
            report_stem="g1-smolvla-closed-loop" if smolvla else "g1-pick-place",
        )
        harness = Harness(
            MockPlanner(arguments={"target": args.destination, "destination": "drop_tray"}),
            robot,
            UnitreePickPlaceVerifier(robot),
            skills=unitree_pick_place_skill_registry(timeout_ms=120_000 if smolvla else 30_000),
            policy=ScriptedPolicy(),
        )
    else:
        robot = UnitreeSimulationRobot(
            project / "simulation" / "run_unitree_headless.sh",
            project / "reports" / "simulation",
            {args.destination: Pose2D(args.target_x, args.target_y, args.target_yaw)},
        )
        harness = Harness(
            NavigateToPlanner(), robot, UnitreeSimulationVerifier(robot), policy=ScriptedPolicy()
        )
    select_kind, confirm_kind = decoded_execution_intents(args.decoded_intents)
    selected = harness.handle(Intent(select_kind, args.destination))
    if selected is not TaskState.AWAITING_CONFIRMATION:
        raise RuntimeError("selection did not reach confirmation gate")
    harness.handle(Intent(confirm_kind))
    report = {
        "accepted": harness.state is TaskState.COMPLETED,
        "final_state": harness.state.value,
        "destination": args.destination,
        "intent_source": str(args.decoded_intents) if args.decoded_intents else "scripted",
        "policy": args.policy,
        "trace": [asdict(record) for record in harness.trace],
        "unitree_acceptance": robot.last_acceptance,
        "unitree_simulator": robot.last_simulator_report,
    }
    if isinstance(robot, UnitreeSimulationRobot):
        report["target_pose"] = asdict(robot.destinations[args.destination])
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return int(not report["accepted"])


if __name__ == "__main__":
    raise SystemExit(main())
