"""A2A Streaming: SSE streaming for task updates."""
import asyncio
import json
from typing import AsyncIterator

from jarvis.a2a.models import A2ATask, A2ATaskState


class TaskEventEmitter:
    """Emits SSE events for task updates."""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """Subscribe to events for a task."""
        queue: asyncio.Queue = asyncio.Queue()
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        self._subscribers[task_id].append(queue)
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from task events."""
        if task_id in self._subscribers:
            try:
                self._subscribers[task_id].remove(queue)
            except ValueError:
                pass
            if not self._subscribers[task_id]:
                del self._subscribers[task_id]

    async def emit(self, task_id: str, event_type: str, data: dict) -> None:
        """Emit an event to all subscribers for a task."""
        if task_id not in self._subscribers:
            return
        event = {
            "event": event_type,
            "data": data,
        }
        for queue in self._subscribers[task_id]:
            await queue.put(event)


# Global emitter instance
_emitter: TaskEventEmitter | None = None


def get_emitter() -> TaskEventEmitter:
    """Get the global event emitter."""
    global _emitter
    if _emitter is None:
        _emitter = TaskEventEmitter()
    return _emitter


async def stream_task_updates(task_id: str, timeout: float = 300.0) -> AsyncIterator[str]:
    """Stream SSE events for a task.

    Yields SSE-formatted strings.
    Stops when task reaches a terminal state or timeout.
    """
    emitter = get_emitter()
    queue = emitter.subscribe(task_id)
    terminal_states = {
        A2ATaskState.COMPLETED,
        A2ATaskState.FAILED,
        A2ATaskState.CANCELED,
        A2ATaskState.REJECTED,
    }

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=timeout)
                event_type = event.get("event", "update")
                data = event.get("data", {})

                # Format as SSE
                yield f"event: {event_type}\n"
                yield f"data: {json.dumps(data)}\n"
                yield "\n"

                # Check for terminal state
                status = data.get("status")
                if status and status in {s.value for s in terminal_states}:
                    break

            except asyncio.TimeoutError:
                # Send keepalive
                yield f"event: keepalive\ndata: {{}}\n\n"
    finally:
        emitter.unsubscribe(task_id, queue)


def format_sse_event(event_type: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
