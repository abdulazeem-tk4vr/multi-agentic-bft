"""Event bus adapter that mirrors Aegean events to VizState."""

from __future__ import annotations

from typing import Any, Callable

from aegean.events import EventBus


class VizEventBus(EventBus):
    def __init__(self, on_event: Callable[[dict[str, Any]], None] | None = None) -> None:
        super().__init__()
        self._on_event = on_event

    def emit(self, topic: str, payload: dict[str, Any], session_id: str | None = None) -> None:
        super().emit(topic, payload, session_id=session_id)
        if self._on_event is None:
            return
        ev: dict[str, Any] = {"topic": topic, "payload": payload}
        if session_id is not None:
            ev["session_id"] = session_id
        self._on_event(ev)
