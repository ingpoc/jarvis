"""WebSocket bridge: localhost server for UI clients (SwiftUI menu bar app).

Protocol: JSON messages over ws://127.0.0.1:9847
Commands: get_status, get_timeline, approve, deny, run_task
Events: pushed to all connected clients via EventCollector listener
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
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
        self._started_at = time.time()

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
        request_id = cmd_data.get("id")
        result: Any = None

        try:
            if action == "get_status":
                if self._orchestrator:
                    raw_status = await self._orchestrator.get_status()
                    result = self._build_status_payload(raw_status)
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "get_timeline":
                if self._orchestrator:
                    limit = data.get("limit", 50)
                    result = self._orchestrator.memory.get_timeline(limit=limit)
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "get_available_tools":
                if self._orchestrator:
                    tools = self._orchestrator.get_capabilities().get("tools", [])
                    result = {"tools": tools}
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "get_capabilities":
                if self._orchestrator:
                    result = self._orchestrator.get_capabilities()
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

            elif action == "chat":
                message = data.get("message", "")
                if not message:
                    result = {"error": "Missing 'message'"}
                elif self._orchestrator:
                    chat_result = await self._orchestrator.chat(message)
                    result = chat_result
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "add_mcp_server":
                if not self._orchestrator:
                    result = {"error": "Orchestrator not connected"}
                else:
                    result = self._orchestrator.register_mcp_server(
                        name=data.get("name", ""),
                        command=data.get("command", ""),
                        args=data.get("args", []) or [],
                        env=data.get("env", {}) or {},
                    )

            elif action == "add_agent":
                if not self._orchestrator:
                    result = {"error": "Orchestrator not connected"}
                else:
                    result = self._orchestrator.register_agent(
                        name=data.get("name", ""),
                        description=data.get("description", ""),
                        prompt=data.get("prompt", ""),
                        tools=data.get("tools", []) or [],
                        model=data.get("model"),
                    )

            elif action == "add_skill":
                if not self._orchestrator:
                    result = {"error": "Orchestrator not connected"}
                else:
                    result = self._orchestrator.register_skill(
                        name=data.get("name", ""),
                        description=data.get("description", ""),
                        content=data.get("content", ""),
                    )

            elif action == "run_tests":
                if self._orchestrator:
                    prompt = (
                        "Run the project's test suite, report failures, and suggest fixes. "
                        "Use the project's native test command."
                    )
                    asyncio.create_task(self._orchestrator.run_task(prompt))
                    result = {"queued": "run_tests"}
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "build_project":
                if self._orchestrator:
                    prompt = "Build the current project and report build status and any errors."
                    asyncio.create_task(self._orchestrator.run_task(prompt))
                    result = {"queued": "build_project"}
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "git_status":
                cwd = self._orchestrator.project_path if self._orchestrator else None
                proc = await asyncio.create_subprocess_exec(
                    "git", "status", "--short",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode == 0:
                    result = {"git_status": stdout.decode().strip() or "Clean working tree"}
                else:
                    result = {"error": stderr.decode().strip() or "git status failed"}

            elif action == "read_file":
                file_path = data.get("file_path", "")
                if not file_path:
                    result = {"error": "Missing 'file_path'"}
                else:
                    path = Path(file_path).expanduser()
                    if not path.exists():
                        result = {"error": f"File not found: {path}"}
                    elif path.is_dir():
                        result = {"error": f"Path is a directory: {path}"}
                    else:
                        text = path.read_text(errors="replace")
                        result = {
                            "file_path": str(path),
                            "size_bytes": path.stat().st_size,
                            "content": text[:20000],
                            "truncated": len(text) > 20000,
                        }

            elif action == "analyze_code":
                file_path = data.get("file_path", "")
                if not file_path:
                    result = {"error": "Missing 'file_path'"}
                else:
                    path = Path(file_path).expanduser()
                    if not path.exists() or path.is_dir():
                        result = {"error": f"File not found: {path}"}
                    else:
                        text = path.read_text(errors="replace")
                        lines = text.splitlines()
                        result = {
                            "file_path": str(path),
                            "language_hint": path.suffix.lstrip("."),
                            "line_count": len(lines),
                            "char_count": len(text),
                            "preview": "\n".join(lines[:120]),
                            "truncated": len(lines) > 120,
                        }

            elif action == "process_file":
                file_path = data.get("file_path", "")
                if not file_path:
                    result = {"error": "Missing 'file_path'"}
                else:
                    path = Path(file_path).expanduser()
                    if not path.exists():
                        result = {"error": f"File not found: {path}"}
                    else:
                        result = {
                            "file_path": str(path),
                            "is_directory": path.is_dir(),
                            "size_bytes": path.stat().st_size if path.is_file() else None,
                            "extension": path.suffix.lower(),
                        }

            elif action == "get_containers":
                from jarvis.container_tools import _run_container_cmd
                cmd_result = await _run_container_cmd("list", "--format", "json", timeout=10)
                if cmd_result["exit_code"] == 0 and cmd_result["stdout"]:
                    try:
                        containers = json.loads(cmd_result["stdout"])
                        jarvis_containers = [
                            c for c in containers
                            if c.get("configuration", {}).get("id", "").startswith("jarvis-")
                        ]
                        result = {
                            "containers": [
                                self._normalize_container(c) for c in jarvis_containers
                            ]
                        }
                    except json.JSONDecodeError:
                        result = {"containers": []}
                else:
                    result = {"containers": []}

            elif action == "stop_container":
                from jarvis.container_tools import _run_container_cmd
                container_id = data.get("container_id", "")
                if not container_id:
                    result = {"success": False, "error": "Missing 'container_id'"}
                else:
                    cmd_result = await _run_container_cmd("stop", container_id, timeout=30)
                    result = {
                        "success": cmd_result["exit_code"] == 0,
                        "container_id": container_id,
                        "output": cmd_result["stdout"] or cmd_result["stderr"],
                    }

            elif action == "start_container":
                from jarvis.container_tools import _run_container_cmd
                container_id = data.get("container_id", "")
                if not container_id:
                    result = {"success": False, "error": "Missing 'container_id'"}
                else:
                    cmd_result = await _run_container_cmd("start", container_id, timeout=30)
                    result = {
                        "success": cmd_result["exit_code"] == 0,
                        "container_id": container_id,
                        "output": cmd_result["stdout"] or cmd_result["stderr"],
                    }

            elif action == "restart_container":
                from jarvis.container_tools import _run_container_cmd
                container_id = data.get("container_id", "")
                if not container_id:
                    result = {"success": False, "error": "Missing 'container_id'"}
                else:
                    stop_result = await _run_container_cmd("stop", container_id, timeout=30)
                    start_result = await _run_container_cmd("start", container_id, timeout=30)
                    ok = stop_result["exit_code"] == 0 and start_result["exit_code"] == 0
                    result = {
                        "success": ok,
                        "container_id": container_id,
                        "output": start_result["stdout"] or stop_result["stderr"] or start_result["stderr"],
                    }

            else:
                result = {"error": f"Unknown action: {action}"}

        except Exception as e:
            logger.exception("Command error (%s): %s", action, e)
            result = {"error": str(e)}

        response = {"type": "response", "id": request_id, "action": action, "data": result}
        # Include the result fields at top-level for clients decoding direct payload types.
        if isinstance(result, dict):
            response.update(result)
        await ws.send(json.dumps(response, default=str))

    def _build_status_payload(self, raw_status: dict) -> dict:
        """Normalize status shape for both legacy and typed Swift clients."""
        active_tasks = raw_status.get("active_tasks", []) or []
        recent_tasks = raw_status.get("recent_tasks", []) or []

        status = "idle"
        if active_tasks:
            status = "building"
        elif any(t.get("status") in ("failed", "error") for t in recent_tasks):
            status = "error"

        return {
            **raw_status,
            "status": status,
            "current_session": raw_status.get("session_id"),
            "current_feature": active_tasks[0]["description"][:120] if active_tasks else None,
            "uptime": max(0.0, time.time() - self._started_at),
        }

    @staticmethod
    def _normalize_container(container: dict) -> dict:
        """Map container CLI JSON into app model fields."""
        config = container.get("configuration", {}) or {}
        resources = config.get("resources", {}) or {}
        image = config.get("image", {}) or {}
        status = container.get("status", "")
        container_id = config.get("id", "")
        cpus = resources.get("cpus")
        if isinstance(cpus, str) and cpus.isdigit():
            cpus = int(cpus)
        if not isinstance(cpus, int):
            cpus = None

        memory = resources.get("memory")
        if memory is not None and not isinstance(memory, str):
            memory = str(memory)

        return {
            "id": container_id,
            "name": container_id,
            "status": status.lower() if isinstance(status, str) else "unknown",
            "image": image.get("reference", "unknown"),
            "cpus": cpus,
            "memory": memory,
            "task_id": None,
        }

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
