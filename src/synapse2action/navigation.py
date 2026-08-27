from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import hypot
from typing import Protocol

from .components import MockPlanner
from .contracts import Action, ExecutionResult, Intent, IntentKind
from .harness import Harness


@dataclass(frozen=True, slots=True)
class Pose2D:
    x: float
    y: float
    yaw: float = 0.0


@dataclass(frozen=True, slots=True)
class NavigationObservation:
    pose: Pose2D
    goal: Pose2D
    step: int


@dataclass(frozen=True, slots=True)
class BaseVelocity:
    vx: float
    vy: float
    yaw_rate: float
    duration_ms: int


@dataclass(frozen=True, slots=True)
class ActionChunk:
    commands: tuple[BaseVelocity, ...]


class NavigationPolicy(Protocol):
    def predict(self, instruction: str, observation: NavigationObservation) -> ActionChunk: ...


@dataclass(slots=True)
class ScriptedNavigationPolicy:
    speed_mps: float = 0.5
    control_period_ms: int = 100

    def predict(self, instruction: str, observation: NavigationObservation) -> ActionChunk:
        del instruction
        dx = observation.goal.x - observation.pose.x
        dy = observation.goal.y - observation.pose.y
        distance = hypot(dx, dy)
        if distance == 0:
            return ActionChunk(())
        speed = min(self.speed_mps, distance * 1000 / self.control_period_ms)
        return ActionChunk(
            (
                BaseVelocity(
                    speed * dx / distance,
                    speed * dy / distance,
                    0.0,
                    self.control_period_ms,
                ),
            )
        )


@dataclass(slots=True)
class NavigationRobot:
    pose: Pose2D
    destinations: dict[str, Pose2D]
    policy: NavigationPolicy = field(default_factory=ScriptedNavigationPolicy)
    tolerance_m: float = 0.05
    max_steps: int = 300
    frames: list[NavigationObservation] = field(default_factory=list)
    chunks: list[ActionChunk] = field(default_factory=list)
    executed: list[Action] = field(default_factory=list)
    stopped: bool = False

    def observe(self, goal: Pose2D, step: int) -> NavigationObservation:
        observation = NavigationObservation(self.pose, goal, step)
        self.frames.append(observation)
        return observation

    def execute_chunk(self, chunk: ActionChunk) -> None:
        for command in chunk.commands:
            seconds = command.duration_ms / 1000
            self.pose = Pose2D(
                self.pose.x + command.vx * seconds,
                self.pose.y + command.vy * seconds,
                self.pose.yaw + command.yaw_rate * seconds,
            )
        self.chunks.append(chunk)

    def execute(self, action: Action) -> ExecutionResult:
        if self.stopped:
            return ExecutionResult(False, "robot is stopped")
        if action.skill != "navigate_to":
            return ExecutionResult(False, f"unsupported navigation skill: {action.skill}")
        if action.steps != ("closed_loop_navigation",):
            return ExecutionResult(False, "invalid navigation policy")
        goal = self.destinations.get(action.arguments["destination"])
        if goal is None:
            return ExecutionResult(False, "destination not found")

        self.executed.append(action)
        elapsed_ms = 0
        for step in range(self.max_steps + 1):
            observation = self.observe(goal, step)
            if hypot(goal.x - self.pose.x, goal.y - self.pose.y) <= self.tolerance_m:
                return ExecutionResult(True, "destination reached", elapsed_ms)
            if self.stopped:
                return ExecutionResult(False, "navigation stopped", elapsed_ms)
            if step == self.max_steps:
                break
            chunk = self.policy.predict(f"navigate to {action.arguments['destination']}", observation)
            if not chunk.commands:
                return ExecutionResult(False, "policy produced no action", elapsed_ms)
            self.execute_chunk(chunk)
            elapsed_ms += sum(command.duration_ms for command in chunk.commands)
        return ExecutionResult(False, "navigation step limit exceeded", elapsed_ms)

    def stop(self) -> None:
        self.stopped = True


class NavigationVerifier:
    def __init__(self, robot: NavigationRobot, goal: Pose2D, tolerance_m: float = 0.05) -> None:
        self.robot = robot
        self.goal = goal
        self.tolerance_m = tolerance_m

    def verify(self, result: ExecutionResult) -> bool:
        return result.success and hypot(
            self.goal.x - self.robot.pose.x,
            self.goal.y - self.robot.pose.y,
        ) <= self.tolerance_m


def run_navigation_demo() -> dict[str, object]:
    start = Pose2D(0.0, 0.0)
    goal = Pose2D(2.0, 1.0)
    robot = NavigationRobot(start, {"point_b": goal})
    harness = Harness(
        MockPlanner("navigate_to", {"destination": "point_b"}),
        robot,
        NavigationVerifier(robot, goal),
    )
    harness.handle(Intent(IntentKind.SELECT, "point_b"))
    harness.handle(Intent(IntentKind.CONFIRM))
    return {
        "schema_version": 1,
        "demo": "closed_loop_navigation_a_to_b",
        "passed": harness.state.value == "completed",
        "start": asdict(start),
        "goal": asdict(goal),
        "final_pose": asdict(robot.pose),
        "control_cycles": len(robot.chunks),
        "observations": len(robot.frames),
        "final_state": harness.state.value,
        "trace": [
            {"sequence": record.sequence, "event": record.event, "state": record.state.value, "detail": record.detail}
            for record in harness.trace
        ],
    }
