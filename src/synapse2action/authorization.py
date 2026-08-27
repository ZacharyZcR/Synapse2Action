from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Challenge:
    token: str
    target: str
    target_revision: int
    issued_at_ms: int
    expires_at_ms: int


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    accepted: bool
    reason: str


class ChallengeStore:
    def __init__(self, lifetime_ms: int = 3_000) -> None:
        self.lifetime_ms = lifetime_ms
        self._sequence = 0
        self._active: Challenge | None = None
        self._consumed: set[str] = set()

    def issue(self, target: str, target_revision: int, at_ms: int) -> Challenge:
        self._sequence += 1
        self._active = Challenge(
            f"challenge-{self._sequence:08d}",
            target,
            target_revision,
            at_ms,
            at_ms + self.lifetime_ms,
        )
        return self._active

    def revoke(self) -> None:
        self._active = None

    def consume(
        self,
        token: str,
        target: str,
        target_revision: int,
        at_ms: int,
    ) -> AuthorizationDecision:
        if token in self._consumed:
            return AuthorizationDecision(False, "challenge already consumed")
        challenge = self._active
        if challenge is None or token != challenge.token:
            return AuthorizationDecision(False, "unknown challenge")
        if at_ms > challenge.expires_at_ms:
            return AuthorizationDecision(False, "challenge expired")
        if target != challenge.target:
            return AuthorizationDecision(False, "target mismatch")
        if target_revision != challenge.target_revision:
            return AuthorizationDecision(False, "target revision changed")
        self._consumed.add(token)
        self._active = None
        return AuthorizationDecision(True, "challenge consumed")
