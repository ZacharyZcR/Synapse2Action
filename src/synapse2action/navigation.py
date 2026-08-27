from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path
from typing import Protocol, TYPE_CHECKING

from .components import MockPlanner
from .contracts import Action, ExecutionResult, Intent, IntentKind
from .harness import Harness

if TYPE_CHECKING:
    from .robot_transport import CommandReceipt, RobotTransport


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
class NavigationScenario:
    name: str
    destination: str
    start: Pose2D
    goal: Pose2D
    obstacles: tuple[Obstacle2D, ...] = ()
    sensor_range_m: float = 3.0
    robot_radius_m: float = 0.1
    tolerance_m: float = 0.05
    max_steps: int = 300


DEFAULT_NAVIGATION_SCENARIO = NavigationScenario(
    "dynamic_obstacle_navigation_a_to_b",
    "point_b",
    Pose2D(0.0, 0.0),
    Pose2D(2.0, 0.0),
    (Obstacle2D("crate", 1.0, 0.0, 0.25, active_from_ms=600),),
)


@dataclass(frozen=True, slots=True)
class CameraFrame:
    width: int
    height: int
    encoding: str
    data: bytes


@dataclass(frozen=True, slots=True)
class BaseState:
    vx: float = 0.0
    vy: float = 0.0
    yaw_rate: float = 0.0


@dataclass(frozen=True, slots=True)
class SensorFrame:
    frame_id: int
    captured_at_ms: int
    pose: Pose2D
    obstacles: tuple[Obstacle2D, ...]
    camera: CameraFrame
    proprioception: BaseState


@dataclass(frozen=True, slots=True)
class NavigationTask:
    instruction: str
    goal: Pose2D


@dataclass(frozen=True, slots=True)
class NavigationObservation:
    sensor: SensorFrame
    task: NavigationTask
    step: int

    @property
    def pose(self) -> Pose2D:
        return self.sensor.pose

    @property
    def obstacles(self) -> tuple[Obstacle2D, ...]:
        return self.sensor.obstacles

    @property
    def goal(self) -> Pose2D:
        return self.task.goal


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
    def reset(self, task: NavigationTask) -> None: ...

    def predict(self, observation: NavigationObservation) -> ActionChunk: ...


@dataclass(slots=True)
class ScriptedNavigationPolicy:
    speed_mps: float = 0.5
    control_period_ms: int = 100
    clearance_m: float = 0.2
    waypoint_tolerance_m: float = 0.05
    waypoint: Pose2D | None = None
    replan_count: int = 0

    def reset(self, task: NavigationTask) -> None:
        del task
        self.waypoint = None
        self.replan_count = 0

    def predict(self, observation: NavigationObservation) -> ActionChunk:
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
    base_state: BaseState = field(default_factory=BaseState)
    transport: RobotTransport | None = None
    transport_receipts: list[CommandReceipt] = field(default_factory=list)
    command_sequence: int = 0
    last_execution_detail: str = ""

    def _active_obstacles(self, at_ms: int) -> tuple[Obstacle2D, ...]:
        return tuple(
            obstacle
            for obstacle in self.obstacles
            if obstacle.active_from_ms <= at_ms
            and (obstacle.active_until_ms is None or at_ms < obstacle.active_until_ms)
        )

    def observe(self, task: NavigationTask, step: int, at_ms: int) -> NavigationObservation:
        visible = tuple(
            obstacle
            for obstacle in self._active_obstacles(at_ms)
            if hypot(obstacle.x - self.pose.x, obstacle.y - self.pose.y) <= self.sensor_range_m
        )
        sensor = SensorFrame(
            step,
            at_ms,
            self.pose,
            visible,
            _render_camera(self.pose, visible, self.sensor_range_m),
            self.base_state,
        )
        observation = NavigationObservation(sensor, task, step)
        self.frames.append(observation)
        return observation

    def execute_chunk(self, chunk: ActionChunk, at_ms: int) -> bool:
        command_time_ms = at_ms
        for command in chunk.commands:
            if self.transport is not None:
                from .robot_transport import decode_command_receipt, encode_base_command

                sequence = self.command_sequence
                self.command_sequence += 1
                receipt = decode_command_receipt(
                    self.transport.exchange(encode_base_command(sequence, command, command_time_ms)),
                    sequence,
                )
                self.transport_receipts.append(receipt)
                self.pose = receipt.pose
                self.base_state = receipt.base_state
                if not receipt.accepted:
                    self.last_execution_detail = receipt.detail
                    return False
                command_time_ms = receipt.completed_at_ms
                continue
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
                self.base_state = BaseState()
                self.last_execution_detail = "action chunk intersects obstacle"
                return False
            self.pose = next_pose
            self.base_state = BaseState(command.vx, command.vy, command.yaw_rate)
        self.chunks.append(chunk)
        self.last_execution_detail = "action chunk completed"
        return True

    def _halt_base(self) -> None:
        self.base_state = BaseState()
        if self.transport is not None:
            self.transport.halt()

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
        task = NavigationTask(f"navigate to {action.arguments['destination']}", goal)
        self.policy.reset(task)
        elapsed_ms = 0
        for step in range(self.max_steps + 1):
            observation = self.observe(task, step, elapsed_ms)
            if hypot(goal.x - self.pose.x, goal.y - self.pose.y) <= self.tolerance_m:
                self._halt_base()
                return ExecutionResult(True, "destination reached", elapsed_ms)
            if self.stopped:
                return ExecutionResult(False, "navigation stopped", elapsed_ms)
            if step == self.max_steps:
                break
            chunk = self.policy.predict(observation)
            if not chunk.commands:
                self._halt_base()
                return ExecutionResult(False, "policy produced no action", elapsed_ms)
            if not self.execute_chunk(chunk, elapsed_ms):
                self._halt_base()
                return ExecutionResult(False, self.last_execution_detail, elapsed_ms)
            elapsed_ms += sum(command.duration_ms for command in chunk.commands)
        self._halt_base()
        return ExecutionResult(False, "navigation step limit exceeded", elapsed_ms)

    def stop(self) -> None:
        self.stopped = True
        self.base_state = BaseState()
        if self.transport is not None:
            self.transport.stop()


class NavigationVerifier:
    def __init__(self, robot: NavigationRobot, goal: Pose2D, tolerance_m: float = 0.05) -> None:
        self.robot = robot
        self.goal = goal
        self.tolerance_m = tolerance_m

    def verify(self, result: ExecutionResult) -> bool:
        return result.success and hypot(
            self.goal.x - self.robot.pose.x,
            self.goal.y - self.robot.pose.y,
        ) <= self.tolerance_m and self.robot.base_state == BaseState()


def _render_camera(
    pose: Pose2D,
    obstacles: tuple[Obstacle2D, ...],
    sensor_range_m: float,
    width: int = 32,
    height: int = 24,
) -> CameraFrame:
    pixels = bytearray(width * height)
    for obstacle in obstacles:
        relative_x = obstacle.x - pose.x
        relative_y = obstacle.y - pose.y
        column = round((relative_y / sensor_range_m + 1) * (width - 1) / 2)
        row = round((1 - relative_x / sensor_range_m) * (height - 1) / 2)
        radius_px = max(1, round(obstacle.radius * min(width, height) / sensor_range_m))
        for y in range(max(0, row - radius_px), min(height, row + radius_px + 1)):
            for x in range(max(0, column - radius_px), min(width, column + radius_px + 1)):
                if (x - column) ** 2 + (y - row) ** 2 <= radius_px**2:
                    pixels[y * width + x] = 255
    return CameraFrame(width, height, "mono8", bytes(pixels))


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


def load_navigation_scenario(path: Path) -> NavigationScenario:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "name",
        "destination",
        "start",
        "goal",
        "obstacles",
        "sensor_range_m",
        "robot_radius_m",
        "tolerance_m",
        "max_steps",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError("navigation scenario does not match schema")
    if not isinstance(payload["name"], str) or not payload["name"]:
        raise ValueError("navigation scenario requires a name")
    if not isinstance(payload["destination"], str) or not payload["destination"]:
        raise ValueError("navigation scenario requires a destination")
    if not isinstance(payload["obstacles"], list):
        raise ValueError("navigation scenario obstacles must be a list")
    max_steps = payload["max_steps"]
    if type(max_steps) is not int or max_steps <= 0:
        raise ValueError("navigation scenario max_steps must be positive")
    sensor_range = _scenario_number(payload["sensor_range_m"], "sensor_range_m")
    robot_radius = _scenario_number(payload["robot_radius_m"], "robot_radius_m")
    tolerance = _scenario_number(payload["tolerance_m"], "tolerance_m")
    if min(sensor_range, robot_radius, tolerance) <= 0:
        raise ValueError("navigation scenario dimensions must be positive")
    return NavigationScenario(
        payload["name"],
        payload["destination"],
        _scenario_pose(payload["start"]),
        _scenario_pose(payload["goal"]),
        tuple(_scenario_obstacle(value) for value in payload["obstacles"]),
        sensor_range,
        robot_radius,
        tolerance,
        max_steps,
    )


def _scenario_pose(value: object) -> Pose2D:
    if not isinstance(value, dict) or set(value) != {"x", "y", "yaw"}:
        raise ValueError("navigation scenario pose does not match schema")
    return Pose2D(*(_scenario_number(value[name], name) for name in ("x", "y", "yaw")))


def _scenario_obstacle(value: object) -> Obstacle2D:
    expected = {"obstacle_id", "x", "y", "radius", "active_from_ms", "active_until_ms"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("navigation obstacle does not match schema")
    if not isinstance(value["obstacle_id"], str) or not value["obstacle_id"]:
        raise ValueError("navigation obstacle requires an id")
    active_from = value["active_from_ms"]
    active_until = value["active_until_ms"]
    if type(active_from) is not int or active_from < 0:
        raise ValueError("navigation obstacle active_from_ms is invalid")
    if active_until is not None and (type(active_until) is not int or active_until <= active_from):
        raise ValueError("navigation obstacle active_until_ms is invalid")
    radius = _scenario_number(value["radius"], "radius")
    if radius <= 0:
        raise ValueError("navigation obstacle radius must be positive")
    return Obstacle2D(
        value["obstacle_id"],
        _scenario_number(value["x"], "x"),
        _scenario_number(value["y"], "y"),
        radius,
        active_from,
        active_until,
    )


def _scenario_number(value: object, name: str) -> float:
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError(f"navigation scenario {name} is invalid")
    return float(value)


def run_navigation_demo(
    policy: NavigationPolicy | None = None,
    demo_name: str | None = None,
    scenario: NavigationScenario | None = None,
    transport: RobotTransport | None = None,
) -> dict[str, object]:
    scenario = scenario or DEFAULT_NAVIGATION_SCENARIO
    start = scenario.start
    goal = scenario.goal
    obstacles = scenario.obstacles
    active_policy = policy or ScriptedNavigationPolicy()
    robot = NavigationRobot(
        start,
        {scenario.destination: goal},
        policy=active_policy,
        obstacles=obstacles,
        sensor_range_m=scenario.sensor_range_m,
        robot_radius_m=scenario.robot_radius_m,
        tolerance_m=scenario.tolerance_m,
        max_steps=scenario.max_steps,
        transport=transport,
    )
    harness = Harness(
        MockPlanner("navigate_to", {"destination": scenario.destination}),
        robot,
        NavigationVerifier(robot, goal, scenario.tolerance_m),
    )
    harness.handle(Intent(IntentKind.SELECT, scenario.destination))
    harness.handle(Intent(IntentKind.CONFIRM))
    executed_commands = [command for chunk in robot.chunks for command in chunk.commands]
    velocity_deltas = [
        hypot(current.vx - previous.vx, current.vy - previous.vy)
        for previous, current in zip(executed_commands, executed_commands[1:])
    ]
    return {
        "schema_version": 3,
        "demo": demo_name or scenario.name,
        "scenario": scenario.name,
        "navigation_policy": type(active_policy).__name__,
        "robot_transport": transport.name if transport is not None else "in_process",
        "transport_commands": len(robot.transport_receipts),
        "transport_halts": getattr(transport, "halt_count", 0),
        "transport_feedback": [
            {
                "sequence": receipt.sequence,
                "accepted": receipt.accepted,
                "detail": receipt.detail,
                "completed_at_ms": receipt.completed_at_ms,
                "pose": asdict(receipt.pose),
                "base_state": asdict(receipt.base_state),
            }
            for receipt in robot.transport_receipts
        ],
        "passed": harness.state.value == "completed",
        "start": asdict(start),
        "goal": asdict(goal),
        "obstacles": [asdict(obstacle) for obstacle in obstacles],
        "final_pose": asdict(robot.pose),
        "control_cycles": len(robot.chunks),
        "executed_commands": len(executed_commands),
        "mean_translational_velocity_delta_mps": (
            sum(velocity_deltas) / len(velocity_deltas) if velocity_deltas else 0.0
        ),
        "translational_velocity_delta_samples": len(velocity_deltas),
        "observations": len(robot.frames),
        "observed_obstacle_frames": sum(bool(frame.obstacles) for frame in robot.frames),
        "replan_count": getattr(active_policy, "replan_count", None),
        "policy_requests": getattr(active_policy, "request_count", 0),
        "policy_backend_requests": getattr(active_policy, "backend_request_count", None),
        "trajectory": [asdict(frame.pose) for frame in robot.frames],
        "sensor_frames": [
            {
                "frame_id": frame.sensor.frame_id,
                "captured_at_ms": frame.sensor.captured_at_ms,
                "instruction": frame.task.instruction,
                "pose": asdict(frame.pose),
                "visible_obstacles": [obstacle.obstacle_id for obstacle in frame.obstacles],
                "camera": {
                    "width": frame.sensor.camera.width,
                    "height": frame.sensor.camera.height,
                    "encoding": frame.sensor.camera.encoding,
                    "sha256": sha256(frame.sensor.camera.data).hexdigest(),
                    "nonzero_pixels": sum(pixel != 0 for pixel in frame.sensor.camera.data),
                },
                "proprioception": asdict(frame.sensor.proprioception),
            }
            for frame in robot.frames
        ],
        "final_proprioception": asdict(robot.base_state),
        "final_state": harness.state.value,
        "trace": [
            {"sequence": record.sequence, "event": record.event, "state": record.state.value, "detail": record.detail}
            for record in harness.trace
        ],
    }
