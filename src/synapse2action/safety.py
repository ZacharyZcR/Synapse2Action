from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import Intent, IntentKind


@dataclass(frozen=True, slots=True)
class GateDecision:
    accepted: bool
    reason: str


@dataclass(slots=True)
class IntentGate:
    min_confirm_delay_ms: int = 300
    max_confirm_delay_ms: int = 3_000
    refractory_ms: int = 250
    confirmations_required: int = 1
    selected_at_ms: int | None = None
    confirmation_count: int = 0
    last_seen_ms: dict[IntentKind, int] = field(default_factory=dict)

    def admit(self, intent: Intent, at_ms: int) -> GateDecision:
        if intent.kind is IntentKind.STOP:
            return GateDecision(True, "stop always preempts")

        previous = self.last_seen_ms.get(intent.kind)
        self.last_seen_ms[intent.kind] = at_ms
        if previous is not None and at_ms - previous < self.refractory_ms:
            return GateDecision(False, "refractory period")

        if intent.kind is IntentKind.SELECT:
            self.selected_at_ms = at_ms
            self.confirmation_count = 0
            return GateDecision(True, "selection opened confirmation window")

        if intent.kind is IntentKind.CONFIRM:
            if self.selected_at_ms is None:
                return GateDecision(False, "no active selection")
            elapsed = at_ms - self.selected_at_ms
            if elapsed < self.min_confirm_delay_ms:
                return GateDecision(False, "confirmation too early")
            if elapsed > self.max_confirm_delay_ms:
                self.selected_at_ms = None
                self.confirmation_count = 0
                return GateDecision(False, "confirmation expired")
            self.confirmation_count += 1
            if self.confirmation_count < self.confirmations_required:
                return GateDecision(False, "additional confirmation required")
            self.selected_at_ms = None
            self.confirmation_count = 0
            return GateDecision(True, "confirmation within window")

        if intent.kind is IntentKind.CANCEL:
            self.selected_at_ms = None
            self.confirmation_count = 0
        return GateDecision(True, "accepted")
