from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass, field
from typing import Any

from .contracts import Intent, IntentKind, IntentSource, TaskState
from .harness import Harness


TERMINAL_STATES = frozenset(
    {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED, TaskState.EMERGENCY_STOPPED}
)


@dataclass(slots=True)
class ScriptedIntentSource:
    intents: Iterable[Intent]
    _iterator: Iterator[Intent] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._iterator = iter(self.intents)

    def next_intent(self) -> Intent | None:
        return next(self._iterator, None)


@dataclass(slots=True)
class KeyboardIntentSource:
    read: Callable[[str], str] = input
    write: Callable[[str], Any] = print

    def next_intent(self) -> Intent | None:
        while True:
            try:
                raw = self.read("intent [select TARGET|confirm|cancel|stop]> ").strip()
            except EOFError:
                return None
            if not raw:
                continue
            command, _, argument = raw.partition(" ")
            command = command.lower()
            if command in {"select", "s"}:
                if argument.strip():
                    return Intent(IntentKind.SELECT, argument.strip())
                self.write("select requires a target")
                continue
            kinds = {
                "confirm": IntentKind.CONFIRM,
                "c": IntentKind.CONFIRM,
                "cancel": IntentKind.CANCEL,
                "x": IntentKind.CANCEL,
                "stop": IntentKind.STOP,
                "q": IntentKind.STOP,
            }
            if command in kinds and not argument:
                return Intent(kinds[command])
            self.write("unknown intent command")


def run_intent_source(source: IntentSource, harness: Harness) -> dict[str, Any]:
    handled = 0
    errors: list[str] = []
    while harness.state not in TERMINAL_STATES:
        intent = source.next_intent()
        if intent is None:
            break
        try:
            harness.handle(intent)
            handled += 1
        except ValueError as exc:
            errors.append(str(exc))
    return {
        "schema_version": 1,
        "source": type(source).__name__,
        "handled_intents": handled,
        "errors": errors,
        "final_state": harness.state.value,
        "trace": [{**asdict(record), "state": record.state.value} for record in harness.trace],
    }
