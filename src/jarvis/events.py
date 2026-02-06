"""Central event bus: emit events to SQLite + listeners."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Standard event types
EVENT_TOOL_USE = "tool_use"
EVENT_STATE_CHANGE = "state_change"
EVENT_FEATURE_START = "feature_start"
EVENT_FEATURE_COMPLETE = "feature_complete"
EVENT_ERROR = "error"
EVENT_APPROVAL_NEEDED = "approval_needed"
EVENT_COST = "cost"
EVENT_TRUST_CHANGE = "trust_change"
EVENT_TASK_START = "task_start"
EVENT_TASK_COMPLETE = "task_complete"


class EventCollector:
    """Central event bus: writes to SQLite and notifies listeners."""

    def __init__(self, memory, session_id: str | None = None):
        self._memory = memory
        self._session_id = session_id
        self._listeners: list[Callable] = []

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @session_id.setter
    def session_id(self, value: str):
        self._session_id = value

    def emit(
        self,
        event_type: str,
        summary: str,
        *,
        task_id: str | None = None,
        feature_id: str | None = None,
        cost_usd: float = 0.0,
        metadata: dict | None = None,
    ) -> int:
        """Emit an event: persist to SQLite and notify all listeners."""
        event_id = self._memory.record_event(
            event_type=event_type,
            summary=summary,
            session_id=self._session_id,
            task_id=task_id,
            feature_id=feature_id,
            cost_usd=cost_usd,
            metadata=metadata,
        )

        event_data = {
            "id": event_id,
            "timestamp": time.time(),
            "event_type": event_type,
            "summary": summary,
            "session_id": self._session_id,
            "task_id": task_id,
            "feature_id": feature_id,
            "cost_usd": cost_usd,
            "metadata": metadata,
        }

        for listener in self._listeners:
            try:
                listener(event_data)
            except Exception as e:
                logger.warning(f"Event listener error: {e}")

        return event_id

    def add_listener(self, callback: Callable[[dict], Any]) -> None:
        """Register a listener for all events."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable) -> None:
        """Remove a registered listener."""
        try:
            self._listeners.remove(callback)
        except ValueError:
            pass
