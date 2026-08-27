from __future__ import annotations

from dataclasses import asdict, dataclass

from .contracts import Action, ExecutionResult


@dataclass(frozen=True, slots=True)
class Point2D:
    x: float
    y: float


@dataclass(slots=True)
class TabletopObject:
    object_id: str
    position: Point2D
    held: bool = False


@dataclass(frozen=True, slots=True)
class TabletopFrame:
    step: str
    gripper: Point2D
    object_position: Point2D
    object_held: bool


class TabletopRobot:
    def __init__(
        self,
        item: TabletopObject,
        destinations: dict[str, Point2D],
    ) -> None:
        self.item = item
        self.destinations = destinations
        self.gripper = Point2D(0.0, 0.0)
        self.frames: list[TabletopFrame] = []
        self.executed: list[Action] = []
        self.stopped = False
        self._record("initial")

    def execute(self, action: Action) -> ExecutionResult:
        if self.stopped:
            return ExecutionResult(False, "robot is stopped")
        if action.skill != "pick_and_place":
            return ExecutionResult(False, f"unsupported tabletop skill: {action.skill}")
        if action.arguments["target"] != self.item.object_id:
            return ExecutionResult(False, "target not found")
        destination = self.destinations.get(action.arguments["destination"])
        if destination is None:
            return ExecutionResult(False, "destination not found")

        self.executed.append(action)
        self.gripper = self.item.position
        self._record("approach")
        self.item.held = True
        self._record("grasp")
        self.gripper = destination
        self.item.position = destination
        self._record("transport")
        self.item.held = False
        self._record("release")
        return ExecutionResult(True, "object placed in drop zone", duration_ms=1200)

    def stop(self) -> None:
        self.stopped = True
        self._record("stop")

    def snapshot(self) -> dict[str, object]:
        return {
            "item": {
                "object_id": self.item.object_id,
                "position": asdict(self.item.position),
                "held": self.item.held,
            },
            "gripper": asdict(self.gripper),
        }

    def _record(self, step: str) -> None:
        self.frames.append(TabletopFrame(step, self.gripper, self.item.position, self.item.held))


class TabletopVerifier:
    def __init__(self, robot: TabletopRobot, destination: Point2D) -> None:
        self.robot = robot
        self.destination = destination

    def verify(self, result: ExecutionResult) -> bool:
        return (
            result.success
            and not self.robot.item.held
            and self.robot.item.position == self.destination
        )
