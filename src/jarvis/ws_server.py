"""WebSocket bridge: localhost server for UI clients (SwiftUI menu bar app).

Protocol: JSON messages over ws://127.0.0.1:9847
Commands: get_status, get_timeline, approve, deny, run_task
Events: pushed to all connected clients via EventCollector listener
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

try:
    import websockets
    from websockets.server import serve

    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

if TYPE_CHECKING:
    from jarvis.events import EventCollector
    from jarvis.orchestrator import JarvisOrchestrator

logger = logging.getLogger(__name__)

DEFAULT_PORT = 9847


def _require_websockets():
    if not HAS_WEBSOCKETS:
        raise ImportError(
            "websockets is required for the WS bridge. "
            "Install with: pip install websockets"
        )


class JarvisWSServer:
    """WebSocket server for local UI clients."""

    def __init__(
        self,
        event_collector: EventCollector,
        orchestrator: JarvisOrchestrator | None = None,
        port: int = DEFAULT_PORT,
    ):
        _require_websockets()
        self._events = event_collector
        self._orchestrator = orchestrator
        self._port = port
        self._clients: set = set()
        self._server = None

        # Register as EventCollector listener
        self._events.add_listener(self._broadcast_event)

    async def start(self) -> None:
        """Start WebSocket server on 127.0.0.1."""
        self._server = await serve(
            self._handler,
            "127.0.0.1",
            self._port,
        )
        logger.info(f"WebSocket server listening on ws://127.0.0.1:{self._port}")

    async def stop(self) -> None:
        """Close the server and all connections."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("WebSocket server stopped")

        # Remove listener
        self._events.remove_listener(self._broadcast_event)

    async def _handler(self, websocket) -> None:
        """Handle a single client connection."""
        self._clients.add(websocket)
        remote = websocket.remote_address
        logger.info(f"Client connected: {remote}")

        try:
            async for raw in websocket:
                try:
                    cmd_data = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "data": {"message": "Invalid JSON"},
                    }))
                    continue

                await self._handle_command(websocket, cmd_data)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            logger.info(f"Client disconnected: {remote}")

    async def _handle_command(self, ws, cmd_data: dict) -> None:
        """Dispatch a command from a client.

        Expected format: {"type": "command", "action": "...", "data": {...}}
        """
        action = cmd_data.get("action", "")
        data = cmd_data.get("data", {})
        result: Any = None

        try:
            if action == "get_status":
                if self._orchestrator:
                    result = await self._orchestrator.get_status()
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "get_timeline":
                if self._orchestrator:
                    limit = data.get("limit", 50)
                    result = self._orchestrator.memory.get_timeline(limit=limit)
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "approve":
                task_id = data.get("task_id", "")
                self._events.emit(
                    "approval_granted",
                    f"Approved via WS: {task_id}",
                    task_id=task_id,
                )
                result = {"approved": task_id}

            elif action == "deny":
                task_id = data.get("task_id", "")
                self._events.emit(
                    "approval_denied",
                    f"Denied via WS: {task_id}",
                    task_id=task_id,
                )
                result = {"denied": task_id}

            elif action == "run_task":
                description = data.get("description", "")
                if not description:
                    result = {"error": "Missing 'description'"}
                elif self._orchestrator:
                    asyncio.create_task(
                        self._orchestrator.run_task(description)
                    )
                    result = {"queued": description[:100]}
                else:
                    result = {"error": "Orchestrator not connected"}

            else:
                result = {"error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Command error ({action}): {e}")
            result = {"error": str(e)}

        response = {"type": "response", "action": action, "data": result}
        await ws.send(json.dumps(response, default=str))

    def _broadcast_event(self, event_data: dict) -> None:
        """EventCollector listener callback: push events to all clients."""
        if not self._clients:
            return

        message = json.dumps(
            {"type": "event", "data": event_data},
            default=str,
        )

        stale: set = set()
        for ws in self._clients:
            try:
                asyncio.ensure_future(ws.send(message))
            except Exception:
                stale.add(ws)

        self._clients -= stale
