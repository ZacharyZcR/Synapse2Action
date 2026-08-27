from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class WorldObject:
    object_id: str
    revision: int
    observed_at_ms: int
    position: tuple[float, float, float]
    occupied: bool = False
    reachable: bool = True


@dataclass(frozen=True, slots=True)
class WorldDecision:
    accepted: bool
    reason: str


class FakeWorld:
    def __init__(self, objects: list[WorldObject] | None = None, max_age_ms: int = 1_000) -> None:
        self.max_age_ms = max_age_ms
        self._objects = {item.object_id: item for item in objects or []}

    def validate(self, object_id: str, revision: int, at_ms: int) -> WorldDecision:
        item = self._objects.get(object_id)
        if item is None:
            return WorldDecision(False, "target missing")
        if item.revision != revision:
            return WorldDecision(False, "target revision changed")
        if at_ms - item.observed_at_ms > self.max_age_ms:
            return WorldDecision(False, "world observation stale")
        if item.occupied:
            return WorldDecision(False, "target occupied")
        if not item.reachable:
            return WorldDecision(False, "target unreachable")
        return WorldDecision(True, "world state valid")

    def move(self, object_id: str, position: tuple[float, float, float], at_ms: int) -> None:
        item = self._require(object_id)
        self._objects[object_id] = replace(
            item, revision=item.revision + 1, position=position, observed_at_ms=at_ms
        )

    def set_occupied(self, object_id: str, occupied: bool, at_ms: int) -> None:
        item = self._require(object_id)
        self._objects[object_id] = replace(
            item, revision=item.revision + 1, occupied=occupied, observed_at_ms=at_ms
        )

    def remove(self, object_id: str) -> None:
        self._objects.pop(object_id, None)

    def _require(self, object_id: str) -> WorldObject:
        try:
            return self._objects[object_id]
        except KeyError as exc:
            raise ValueError(f"unknown world object: {object_id}") from exc
