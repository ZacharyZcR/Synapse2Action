from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import subprocess
from time import monotonic
from typing import Callable, Mapping

from .contracts import Action, ExecutionResult
from .navigation import Pose2D
from .skills import RiskLevel, SkillContext, SkillRegistry, SkillSpec
from .task_spec import TaskSpec, load_task_spec


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(slots=True)
class UnitreeSimulationRobot:
    """High-level Robot adapter for the official SDK2 MuJoCo acceptance runner."""

    runner_path: Path
    report_directory: Path
    destinations: Mapping[str, Pose2D]
    scenario: str = "locomotion"
    timeout_seconds: float = 60.0
    run: Runner = subprocess.run
    stopped: bool = False
    executed: list[Action] = field(default_factory=list)
    last_acceptance: dict[str, object] | None = None
    last_simulator_report: dict[str, object] | None = None

    def execute(self, action: Action) -> ExecutionResult:
        started = monotonic()
        if self.stopped:
            return ExecutionResult(False, "robot is stopped")
        if action.skill != "navigate_to":
            return ExecutionResult(False, f"unsupported Unitree simulation skill: {action.skill}")
        destination = self.destinations.get(str(action.arguments["destination"]))
        if destination is None:
            return ExecutionResult(False, "unknown Unitree simulation destination")

        self.executed.append(action)
        command = (
            str(self.runner_path),
            self.scenario,
            str(destination.x),
            str(destination.y),
            str(destination.yaw),
        )
        try:
            completed = self.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            self.stop()
            return self._result(False, "Unitree simulation timed out", started)

        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "runner failed"
            return self._result(False, f"Unitree simulation failed: {detail}", started)

        try:
            self.last_acceptance = self._load_report("acceptance.json")
            self.last_simulator_report = self._load_report("g1-mujoco.json")
        except (OSError, ValueError, TypeError) as exc:
            return self._result(False, f"invalid Unitree simulation report: {exc}", started)
        if self.last_acceptance.get("accepted") is not True:
            return self._result(False, "Unitree simulation acceptance failed", started)
        return self._result(True, "Unitree simulation independently accepted", started)

    def stop(self) -> None:
        self.stopped = True

    def _load_report(self, name: str) -> dict[str, object]:
        payload = json.loads((self.report_directory / name).read_text())
        if not isinstance(payload, dict):
            raise TypeError(f"{name} must contain an object")
        return payload

    @staticmethod
    def _result(success: bool, detail: str, started: float) -> ExecutionResult:
        return ExecutionResult(success, detail, round((monotonic() - started) * 1000))


class UnitreeSimulationVerifier:
    def __init__(self, robot: UnitreeSimulationRobot) -> None:
        self.robot = robot

    def verify(self, result: ExecutionResult) -> bool:
        acceptance = self.robot.last_acceptance
        simulator = self.robot.last_simulator_report
        return bool(
            result.success
            and acceptance
            and acceptance.get("accepted") is True
            and simulator
            and float(simulator.get("final_position_error_m", 99)) <= 0.1
            and abs(float(simulator.get("final_yaw_error_rad", 99))) <= 0.15
        )


@dataclass(frozen=True, slots=True)
class NavigateToPlanner:
    def plan(self, target: str) -> Action:
        return Action("navigate_to", {"destination": target})


@dataclass(slots=True)
class UnitreePickPlaceSimulationRobot:
    runner_path: Path
    report_directory: Path
    timeout_seconds: float = 30.0
    report_stem: str = "g1-pick-place"
    task_spec_path: Path | None = None
    run: Runner = subprocess.run
    stopped: bool = False
    executed: list[Action] = field(default_factory=list)
    last_acceptance: dict[str, object] | None = None
    last_simulator_report: dict[str, object] | None = None

    def execute(self, action: Action) -> ExecutionResult:
        started = monotonic()
        if self.stopped:
            return ExecutionResult(False, "robot is stopped")
        if self.task_spec_path is None:
            return ExecutionResult(False, "Unitree simulation requires a task spec")
        try:
            task = load_task_spec(self.task_spec_path)
            task.validate_action(action.skill, action.arguments)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return ExecutionResult(False, f"invalid Unitree task: {exc}")
        self.executed.append(action)
        try:
            completed = self.run(
                (str(self.runner_path), str(self.task_spec_path), "planner_action"),
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            self.stop()
            return UnitreeSimulationRobot._result(False, "Unitree pick-and-place timed out", started)
        try:
            self.last_acceptance = self._load(f"{self.report_stem}-acceptance.json")
            self.last_simulator_report = self._load(f"{self.report_stem}.json")
        except (OSError, ValueError, TypeError) as exc:
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip() or "runner failed"
                return UnitreeSimulationRobot._result(False, f"Unitree pick-and-place failed: {detail}", started)
            return UnitreeSimulationRobot._result(False, f"invalid pick-and-place report: {exc}", started)
        accepted = self.last_acceptance.get("accepted") is True
        return UnitreeSimulationRobot._result(accepted, "Unitree pick-and-place independently accepted" if accepted else "Unitree pick-and-place acceptance failed", started)

    def stop(self) -> None:
        self.stopped = True

    def _load(self, name: str) -> dict[str, object]:
        payload = json.loads((self.report_directory / name).read_text())
        if not isinstance(payload, dict):
            raise TypeError(f"{name} must contain an object")
        return payload


class UnitreePickPlaceVerifier:
    def __init__(self, robot: UnitreePickPlaceSimulationRobot) -> None:
        self.robot = robot

    def verify(self, result: ExecutionResult) -> bool:
        report = self.robot.last_simulator_report
        acceptance = self.robot.last_acceptance
        if not result.success or not report or not acceptance or acceptance.get("accepted") is not True:
            return False
        initial = report.get("initial_object_position_xyz_m")
        task = load_task_spec(self.robot.task_spec_path) if self.robot.task_spec_path else None
        if task is None:
            return False
        return bool(
            isinstance(initial, list)
            and len(initial) == 3
            and report.get("grasped") is True
            and report.get("released") is True
            and float(report.get("maximum_object_height_m", 0)) - float(initial[2])
            >= task.verification.minimum_lift_m
            and report.get("final_object_center_in_drop_zone") is True
            and float(report.get("minimum_base_height_m", 0))
            >= task.verification.minimum_base_height_m
        )


@dataclass(slots=True)
class GrootPickPlaceSimulationRobot(UnitreePickPlaceSimulationRobot):
    """Run a public GR00T checkpoint behind the existing Robot contract."""

    report_stem: str = "g1-groot-closed-loop"

    def execute(self, action: Action) -> ExecutionResult:
        result = UnitreePickPlaceSimulationRobot.execute(self, action)
        if self.last_simulator_report is None:
            return result
        report = self.last_simulator_report or {}
        official = report.get("official_contact_success") is True
        detail = (
            "GR00T rollout reached the official contact criterion"
            if official
            else "GR00T rollout did not reach the official contact criterion"
        )
        return ExecutionResult(official, detail, result.duration_ms)


class GrootPickPlaceVerifier:
    """Require completed placement, not GR00T's contact-only benchmark flag."""

    def __init__(self, robot: GrootPickPlaceSimulationRobot) -> None:
        self.robot = robot

    def verify(self, result: ExecutionResult) -> bool:
        report = self.robot.last_simulator_report
        task = load_task_spec(self.robot.task_spec_path) if self.robot.task_spec_path else None
        return bool(
            result.success
            and report
            and task
            and report.get("official_contact_success") is True
            and report.get("grasped") is True
            and float(report.get("maximum_lift_m", 0)) >= task.verification.minimum_lift_m
            and report.get("released") is True
            and report.get("stable_on_target") is True
            and float(report.get("minimum_base_height_m", 0))
            >= task.verification.minimum_base_height_m
        )


def unitree_pick_place_skill_registry(*, timeout_ms: int = 30_000) -> SkillRegistry:
    if timeout_ms <= 0:
        raise ValueError("pick-and-place timeout must be positive")

    def precondition(action: Action, context: SkillContext) -> str | None:
        if action.arguments["target"] != context.selected_target:
            return "planner changed selected target"
        if not action.arguments["destination"]:
            return "destination is empty"
        return None

    return SkillRegistry([
        SkillSpec(
            "pick_and_place",
            {"target": str, "destination": str},
            timeout_ms=timeout_ms,
            risk=RiskLevel.MEDIUM,
            precondition=precondition,
            success_condition=lambda result: bool(result.process_compliance),
        )
    ])
