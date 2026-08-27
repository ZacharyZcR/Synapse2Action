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
class Obstacle2D:
    obstacle_id: str
    x: float
    y: float
    radius: float
    active_from_ms: int = 0
    active_until_ms: int | None = None


@dataclass(frozen=True, slots=True)
class SensorFrame:
    frame_id: int
    captured_at_ms: int
    pose: Pose2D
    obstacles: tuple[Obstacle2D, ...]


@dataclass(frozen=True, slots=True)
class NavigationObservation:
    sensor: SensorFrame
    goal: Pose2D
    step: int

    @property
    def pose(self) -> Pose2D:
        return self.sensor.pose

    @property
    def obstacles(self) -> tuple[Obstacle2D, ...]:
        return self.sensor.obstacles


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
    def reset(self, instruction: str, goal: Pose2D) -> None: ...

    def predict(self, instruction: str, observation: NavigationObservation) -> ActionChunk: ...


@dataclass(slots=True)
class ScriptedNavigationPolicy:
    speed_mps: float = 0.5
    control_period_ms: int = 100
    clearance_m: float = 0.2
    waypoint_tolerance_m: float = 0.05
    waypoint: Pose2D | None = None
    replan_count: int = 0

    def reset(self, instruction: str, goal: Pose2D) -> None:
        del instruction, goal
        self.waypoint = None
        self.replan_count = 0

    def predict(self, instruction: str, observation: NavigationObservation) -> ActionChunk:
        del instruction
        if self.waypoint and _distance(observation.pose, self.waypoint) <= self.waypoint_tolerance_m:
            self.waypoint = None
        if self.waypoint is None:
            obstacle = _first_blocking_obstacle(observation)
            if obstacle:
                self.waypoint = _detour_waypoint(observation.pose, observation.goal, obstacle, self.clearance_m)
                self.replan_count += 1
        target = self.waypoint or observation.goal
        dx = target.x - observation.pose.x
        dy = target.y - observation.pose.y
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
    obstacles: tuple[Obstacle2D, ...] = ()
    sensor_range_m: float = 3.0
    robot_radius_m: float = 0.1
    tolerance_m: float = 0.05
    max_steps: int = 300
    frames: list[NavigationObservation] = field(default_factory=list)
    chunks: list[ActionChunk] = field(default_factory=list)
    executed: list[Action] = field(default_factory=list)
    stopped: bool = False

    def _active_obstacles(self, at_ms: int) -> tuple[Obstacle2D, ...]:
        return tuple(
            obstacle
            for obstacle in self.obstacles
            if obstacle.active_from_ms <= at_ms
            and (obstacle.active_until_ms is None or at_ms < obstacle.active_until_ms)
        )

    def observe(self, goal: Pose2D, step: int, at_ms: int) -> NavigationObservation:
        visible = tuple(
            obstacle
            for obstacle in self._active_obstacles(at_ms)
            if hypot(obstacle.x - self.pose.x, obstacle.y - self.pose.y) <= self.sensor_range_m
        )
        sensor = SensorFrame(step, at_ms, self.pose, visible)
        observation = NavigationObservation(sensor, goal, step)
        self.frames.append(observation)
        return observation

    def execute_chunk(self, chunk: ActionChunk, at_ms: int) -> bool:
        command_time_ms = at_ms
        for command in chunk.commands:
            seconds = command.duration_ms / 1000
            command_time_ms += command.duration_ms
            next_pose = Pose2D(
                self.pose.x + command.vx * seconds,
                self.pose.y + command.vy * seconds,
                self.pose.yaw + command.yaw_rate * seconds,
            )
            if any(
                hypot(next_pose.x - obstacle.x, next_pose.y - obstacle.y)
                < obstacle.radius + self.robot_radius_m
                for obstacle in self._active_obstacles(command_time_ms)
            ):
                return False
            self.pose = next_pose
        self.chunks.append(chunk)
        return True

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
        instruction = f"navigate to {action.arguments['destination']}"
        self.policy.reset(instruction, goal)
        elapsed_ms = 0
        for step in range(self.max_steps + 1):
            observation = self.observe(goal, step, elapsed_ms)
            if hypot(goal.x - self.pose.x, goal.y - self.pose.y) <= self.tolerance_m:
                return ExecutionResult(True, "destination reached", elapsed_ms)
            if self.stopped:
                return ExecutionResult(False, "navigation stopped", elapsed_ms)
            if step == self.max_steps:
                break
            chunk = self.policy.predict(instruction, observation)
            if not chunk.commands:
                return ExecutionResult(False, "policy produced no action", elapsed_ms)
            if not self.execute_chunk(chunk, elapsed_ms):
                return ExecutionResult(False, "action chunk intersects obstacle", elapsed_ms)
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


def _distance(first: Pose2D, second: Pose2D) -> float:
    return hypot(second.x - first.x, second.y - first.y)


def _distance_to_segment(point: Obstacle2D, start: Pose2D, end: Pose2D) -> tuple[float, float]:
    dx = end.x - start.x
    dy = end.y - start.y
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return hypot(point.x - start.x, point.y - start.y), 0.0
    progress = max(0.0, min(1.0, ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_squared))
    nearest_x = start.x + progress * dx
    nearest_y = start.y + progress * dy
    return hypot(point.x - nearest_x, point.y - nearest_y), progress


def _first_blocking_obstacle(observation: NavigationObservation) -> Obstacle2D | None:
    blocking = []
    for obstacle in observation.obstacles:
        distance, progress = _distance_to_segment(obstacle, observation.pose, observation.goal)
        if 0.0 < progress < 1.0 and distance < obstacle.radius + 0.1:
            blocking.append((progress, obstacle))
    return min(blocking, key=lambda item: item[0])[1] if blocking else None


def _detour_waypoint(start: Pose2D, goal: Pose2D, obstacle: Obstacle2D, clearance_m: float) -> Pose2D:
    dx = goal.x - start.x
    dy = goal.y - start.y
    length = hypot(dx, dy)
    offset = obstacle.radius + clearance_m
    return Pose2D(obstacle.x - dy / length * offset, obstacle.y + dx / length * offset)


def run_navigation_demo() -> dict[str, object]:
    start = Pose2D(0.0, 0.0)
    goal = Pose2D(2.0, 0.0)
    obstacles = (Obstacle2D("crate", 1.0, 0.0, 0.25, active_from_ms=600),)
    policy = ScriptedNavigationPolicy()
    robot = NavigationRobot(start, {"point_b": goal}, policy=policy, obstacles=obstacles)
    harness = Harness(
        MockPlanner("navigate_to", {"destination": "point_b"}),
        robot,
        NavigationVerifier(robot, goal),
    )
    harness.handle(Intent(IntentKind.SELECT, "point_b"))
    harness.handle(Intent(IntentKind.CONFIRM))
    return {
        "schema_version": 2,
        "demo": "dynamic_obstacle_navigation_a_to_b",
        "passed": harness.state.value == "completed",
        "start": asdict(start),
        "goal": asdict(goal),
        "obstacles": [asdict(obstacle) for obstacle in obstacles],
        "final_pose": asdict(robot.pose),
        "control_cycles": len(robot.chunks),
        "observations": len(robot.frames),
        "observed_obstacle_frames": sum(bool(frame.obstacles) for frame in robot.frames),
        "replan_count": policy.replan_count,
        "trajectory": [asdict(frame.pose) for frame in robot.frames],
        "sensor_frames": [
            {
                "frame_id": frame.sensor.frame_id,
                "captured_at_ms": frame.sensor.captured_at_ms,
                "pose": asdict(frame.pose),
                "visible_obstacles": [obstacle.obstacle_id for obstacle in frame.obstacles],
            }
            for frame in robot.frames
        ],
        "final_state": harness.state.value,
        "trace": [
            {"sequence": record.sequence, "event": record.event, "state": record.state.value, "detail": record.detail}
            for record in harness.trace
        ],
    }
