from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Callable

from synapse2action.components import MockPlanner, ScriptedPolicy
from synapse2action.contracts import Action, Intent, IntentKind, Planner, TaskState
from synapse2action.harness import Harness
from synapse2action.llm_planner import OpenAICompatiblePlanner
from synapse2action.navigation import Pose2D
from synapse2action.unitree_simulation import (
    NavigateToPlanner,
    UnitreePickPlaceSimulationRobot,
    UnitreePickPlaceVerifier,
    UnitreeSimulationRobot,
    UnitreeSimulationVerifier,
    unitree_pick_place_skill_registry,
)


class ObservablePlanner:
    def __init__(self, planner: Planner, metadata: dict[str, Any], on_update: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.planner = planner
        self.on_update = on_update
        self.report = {**metadata, "status": "not_run", "latency_ms": None, "input": None, "output": None}

    def plan(self, target: str) -> Action:
        self.report["input"] = {"target": target}
        started = perf_counter_ns()
        try:
            action = self.planner.plan(target)
        except Exception as exc:
            self.report.update(status="failed", error=type(exc).__name__)
            if self.on_update:
                self.on_update(self.report)
            raise
        finally:
            self.report["latency_ms"] = round((perf_counter_ns() - started) / 1_000_000, 3)
        self.report.update(
            status="completed",
            output={"skill": action.skill, "arguments": dict(action.arguments)},
        )
        if self.on_update:
            self.on_update(self.report)
        return action


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
    parser.add_argument("--planner", choices=("mock", "live"), default="mock")
    parser.add_argument("--planner-base-url")
    parser.add_argument("--planner-model")
    parser.add_argument("--planner-provider", default="unspecified")
    parser.add_argument("--planner-output-mode", choices=("json-schema", "prompt-json"), default="prompt-json")
    parser.add_argument("--planner-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--progress-output", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.planner == "live" and (not args.planner_base_url or not args.planner_model):
        parser.error("--planner live requires --planner-base-url and --planner-model")

    project = Path(__file__).resolve().parents[1]
    if args.planner == "live":
        active_planner: Planner = OpenAICompatiblePlanner(
            args.planner_base_url,
            args.planner_model,
            destination="drop_tray",
            api_key=os.getenv(args.planner_api_key_env),
            output_mode=args.planner_output_mode,
        )
        planner_metadata = {
            "component": "OpenAICompatiblePlanner",
            "mode": "live",
            "provider": args.planner_provider,
            "model": args.planner_model,
        }
    else:
        active_planner = MockPlanner(arguments={"target": args.destination, "destination": "drop_tray"})
        planner_metadata = {
            "component": "MockPlanner",
            "mode": "mock",
            "provider": None,
            "model": None,
        }
    def progress(stage: str, status: str, detail: Any = None) -> None:
        if not args.progress_output:
            return
        args.progress_output.parent.mkdir(parents=True, exist_ok=True)
        with args.progress_output.open("a") as stream:
            stream.write(json.dumps({"stage": stage, "status": status, "detail": detail}) + "\n")

    if args.progress_output:
        args.progress_output.unlink(missing_ok=True)
    observable_planner = ObservablePlanner(
        active_planner,
        planner_metadata,
        lambda report: progress("llm_planner", report["status"], report),
    )
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
            observable_planner,
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
    progress("intent", "completed", {"selected": args.destination, "intent": select_kind.value})
    progress("llm_planner", "running", {"provider": args.planner_provider, "model": args.planner_model})
    selected = harness.handle(Intent(select_kind, args.destination))
    if selected is not TaskState.AWAITING_CONFIRMATION:
        raise RuntimeError("selection did not reach confirmation gate")
    assert harness.pending_action is not None
    progress(
        "plan_review",
        "completed",
        {
            "skill": harness.pending_action.skill,
            "arguments": dict(harness.pending_action.arguments),
            "confirmation": confirm_kind.value,
        },
    )
    harness.handle(Intent(confirm_kind))
    report = {
        "accepted": harness.state is TaskState.COMPLETED,
        "final_state": harness.state.value,
        "destination": args.destination,
        "intent_source": str(args.decoded_intents) if args.decoded_intents else "scripted",
        "policy": args.policy,
        "planner": observable_planner.report,
        "trace": [asdict(record) for record in harness.trace],
        "unitree_acceptance": robot.last_acceptance,
        "unitree_simulator": robot.last_simulator_report,
    }
    simulator = robot.last_simulator_report or {}
    report["intelligence_stages"] = [
        {
            "id": "intent",
            "mode": "synthetic" if args.decoded_intents else "scripted",
            "status": "completed",
            "input": str(args.decoded_intents) if args.decoded_intents else "scripted select + confirm",
            "output": f"select({args.destination}) + confirm",
        },
        {"id": "llm_planner", **observable_planner.report},
        {
            "id": "plan_review",
            "mode": "confirmed",
            "status": "completed",
            "input": observable_planner.report.get("output"),
            "output": "reviewed plan + confirm",
        },
        {
            "id": "vla",
            "mode": "live" if args.policy == "smolvla" else "scripted",
            "status": "completed" if simulator.get("vla_runtime") else "not_used",
            "input": "3 camera frames + 29-DoF joint state + task text" if args.policy == "smolvla" else None,
            "output": f"{simulator.get('vla_runtime', {}).get('chunks_received', 0)} action chunks",
            "role": "bounded manipulation-joint action chunks" if args.policy == "smolvla" else "scripted policy",
        },
        {
            "id": "skill_executor",
            "mode": "deterministic",
            "status": "completed" if simulator.get("sdk2_lowcmd_frames", 0) else "failed",
            "input": "pick_and_place(red_cube, drop_tray)",
            "output": "validated C++ manipulation targets",
        },
        {
            "id": "motion_control",
            "mode": "real_sdk",
            "status": "completed" if simulator.get("sdk2_lowcmd_frames", 0) else "failed",
            "input": "bounded VLA manipulation targets + RL whole-body command + proprioception",
            "output": f"{simulator.get('sdk2_lowcmd_frames', 0)} SDK2 LowCmd frames",
        },
        {
            "id": "physical_verification",
            "mode": "measured",
            "status": "completed" if harness.state is TaskState.COMPLETED else "failed",
            "input": "MuJoCo robot and object state",
            "output": "standing + grasp + lift + release + drop-zone checks",
        },
    ]
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
