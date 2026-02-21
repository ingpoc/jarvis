"""WebSocket bridge: localhost server for UI clients (SwiftUI menu bar app).

Protocol: JSON messages over ws://127.0.0.1:9847
Commands: get_status, get_timeline, approve, deny, run_task
Events: pushed to all connected clients via EventCollector listener
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone
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
OPENCODE_FREE_MODELS = [
    "minimax-m2.5-free",
    "glm-5-free",
    "kimi-k2.5-free",
    "big-pickle",
]


def _require_websockets():
    if not HAS_WEBSOCKETS:
        raise ImportError(
            "websockets is required for the WS bridge. Install with: pip install websockets"
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
        self._background_tasks: set[asyncio.Task] = set()

        # Register as EventCollector listener
        self._events.add_listener(self._broadcast_event)

    def _track_background_task(self, task: asyncio.Task) -> None:
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _run_chat_nonblocking(
        self,
        *,
        message: str,
        origin: str,
        request_id: str | None,
        action: str,
    ) -> dict:
        """Return chat quickly; continue long-running turns in background."""
        if not self._orchestrator:
            return {"error": "Orchestrator not connected"}

        default_sync_timeout = 20.0

        raw_timeout = os.environ.get("JARVIS_WS_CHAT_SYNC_TIMEOUT_SECS", "").strip()
        try:
            sync_timeout = float(raw_timeout) if raw_timeout else default_sync_timeout
        except ValueError:
            sync_timeout = default_sync_timeout
        chat_task = asyncio.create_task(self._orchestrator.handle_message(message, origin=origin))

        if sync_timeout <= 0:
            return await chat_task

        done, _ = await asyncio.wait({chat_task}, timeout=sync_timeout)
        if done:
            return await chat_task

        raw_async_timeout = os.environ.get("JARVIS_WS_CHAT_ASYNC_TIMEOUT_SECS", "").strip()
        try:
            async_timeout = float(raw_async_timeout) if raw_async_timeout else 180.0
        except ValueError:
            async_timeout = 180.0
        async_timeout = max(10.0, min(async_timeout, 1800.0))

        async def _publish_when_done() -> None:
            try:
                done, _ = await asyncio.wait({chat_task}, timeout=async_timeout)
                if not done:
                    chat_task.cancel()
                    msg = f"Background chat timed out after {int(async_timeout)}s."
                    self._events.emit(
                        "error",
                        msg,
                        metadata={
                            "request_id": request_id,
                            "action": action,
                            "origin": origin,
                            "error": msg,
                        },
                    )
                    return

                result = await chat_task
                reply = (result.get("reply") or "").strip()
                completion_text = (reply or str(result.get("status") or "completed")).strip()
                self._events.emit(
                    "chat_async_complete",
                    completion_text[:5000],
                    metadata={
                        "request_id": request_id,
                        "action": action,
                        "origin": origin,
                        "route": result.get("route"),
                        "status": result.get("status"),
                        "reply": reply[:5000],
                        "decision": result.get("decision") or {},
                    },
                )
            except asyncio.CancelledError:
                msg = "Background chat cancelled."
                self._events.emit(
                    "error",
                    msg,
                    metadata={
                        "request_id": request_id,
                        "action": action,
                        "origin": origin,
                        "error": msg,
                    },
                )
                raise
            except Exception as exc:
                logger.exception("Background chat failed")
                self._events.emit(
                    "error",
                    f"Background chat failed: {exc}",
                    metadata={
                        "request_id": request_id,
                        "action": action,
                        "origin": origin,
                        "error": str(exc),
                    },
                )

        self._track_background_task(asyncio.create_task(_publish_when_done()))
        queued = {
            "status": "queued",
            "route": "chat",
            "reply": "Working on it. I will post the full response when finished.",
            "queued": True,
            "decision": {
                "mode": "chat",
                "confidence": 0.5,
                "reason": "async_queued",
            },
        }
        return queued

    def _resolve_client_path(self, raw_path: str) -> Path:
        """Resolve client-provided paths strictly inside Jarvis workspace."""
        base = (
            Path(self._orchestrator.project_path if self._orchestrator else ".")
            .expanduser()
            .resolve()
        )
        incoming = Path(raw_path).expanduser()
        candidate = incoming if incoming.is_absolute() else (base / incoming)
        resolved = candidate.resolve()
        if resolved != base and base not in resolved.parents:
            raise PermissionError(f"Path escapes workspace: {resolved}")
        return resolved

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
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "error",
                                "data": {"message": "Invalid JSON"},
                            }
                        )
                    )
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
        started_at = time.time()

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

            elif action == "run_mail_digest":
                if not self._orchestrator:
                    result = {"error": "Orchestrator not connected"}
                else:
                    result = await self._orchestrator.run_mail_digest(
                        window_hours=int(data.get("window_hours", 24) or 24),
                        force=bool(data.get("force", False)),
                        origin="ws:mail_digest",
                    )

            elif action == "get_mail_digest":
                if not self._orchestrator:
                    result = {"error": "Orchestrator not connected"}
                else:
                    result = {
                        "runs": self._orchestrator.get_mail_digest(
                            run_date=data.get("date"),
                            limit=int(data.get("limit", 10) or 10),
                        )
                    }

            elif action == "set_mail_schedule":
                if not self._orchestrator:
                    result = {"error": "Orchestrator not connected"}
                else:
                    result = self._orchestrator.update_mail_schedule(
                        enabled=data.get("enabled"),
                        time_local=data.get("time_local"),
                        timezone=data.get("timezone"),
                        window_hours=data.get("window_hours"),
                        include_weekends=data.get("include_weekends"),
                    )

            elif action == "mail_draft_reply":
                thread_id = str(data.get("thread_id", "") or "").strip()
                tone = str(data.get("tone", "concise") or "concise").strip()
                if not thread_id:
                    result = {"error": "Missing 'thread_id'"}
                elif not self._orchestrator:
                    result = {"error": "Orchestrator not connected"}
                else:
                    prompt = (
                        f"Draft a {tone} reply for mail thread '{thread_id}'. "
                        "Use mail tools to read the latest thread context before drafting. "
                        "Return subject + draft body."
                    )
                    result = await self._orchestrator.handle_message(
                        prompt,
                        origin="ws:mail_draft_reply",
                    )

            elif action == "get_available_tools":
                if self._orchestrator:
                    tools = await asyncio.to_thread(self._discover_opencode_tools)
                    if not tools:
                        # Fallback to orchestrator capability inventory.
                        tools = self._orchestrator.get_capabilities().get("tools", [])
                    result = {"tools": tools}
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "get_capabilities":
                if self._orchestrator:
                    result = self._orchestrator.get_capabilities()
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "get_model_status":
                config = self._orchestrator.config if self._orchestrator else None
                current_model = config.models.executor if config else "unknown"

                def _provider_from_model(model_id: str) -> str:
                    model_id = str(model_id or "")
                    if model_id.startswith("opencode/") or model_id.startswith("opencode:") or model_id == "opencode":
                        return "opencode"
                    return "opencode"

                derived_provider_type = _provider_from_model(current_model)
                configured_provider_type = (
                    str(getattr(config.models, "provider_type", "")).strip().lower()
                    if config
                    else ""
                )
                if configured_provider_type != "opencode":
                    configured_provider_type = "opencode"

                provider_type = (
                    configured_provider_type
                    if configured_provider_type and configured_provider_type == derived_provider_type
                    else derived_provider_type
                )

                provider = "opencode"

                result = {
                    "current_model": current_model,
                    "provider": provider,
                    "provider_type": provider_type,
                    "opencode_available_models": OPENCODE_FREE_MODELS,
                    "runtime_provider": "opencode",
                }

            elif action == "switch_model":
                model = data.get("model", "")
                if not model:
                    result = {"error": "Missing 'model'"}
                elif self._orchestrator:
                    if not (
                        model.startswith("opencode/")
                        or model.startswith("opencode:")
                        or model == "opencode"
                    ):
                        result = {
                            "error": "Only opencode/* models are allowed in this runtime",
                            "provider": "opencode",
                            "provider_type": "opencode",
                        }
                    else:
                        self._orchestrator.config.models.executor = model
                        self._orchestrator.config.models.provider_type = "opencode"
                        self._orchestrator.config.save()
                        await self._orchestrator._reset_chat_client()
                        result = {
                            "success": True,
                            "current_model": model,
                            "provider": "opencode",
                            "provider_type": "opencode",
                        }
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
                    origin_tag = f"ws:{request_id}" if request_id else "ws"
                    force_mode = str(data.get("mode", "")).strip().lower()
                    if force_mode == "pipeline":

                        async def runner(desc: str):
                            return await self._orchestrator.run_pipeline(desc)

                        mode = "pipeline"
                    else:
                        # WS default is single-agent for predictable conversational UX.
                        # Callers can explicitly request pipeline mode with data.mode="pipeline".
                        async def runner(desc: str):
                            return await self._orchestrator.run_task(desc, origin=origin_tag)

                        mode = "single"
                    asyncio.create_task(runner(description))
                    result = {"queued": description[:100], "mode": mode, "origin": origin_tag}
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "chat":
                message = data.get("message", "")
                if not message:
                    result = {"error": "Missing 'message'"}
                elif self._orchestrator:
                    origin_tag = f"ws:{ws.remote_address[0]}:{ws.remote_address[1]}"
                    result = await self._run_chat_nonblocking(
                        message=message,
                        origin=origin_tag,
                        request_id=request_id,
                        action=action,
                    )
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "message":
                message = data.get("message", "")
                if not message:
                    result = {"error": "Missing 'message'"}
                elif not self._orchestrator:
                    result = {"error": "Orchestrator not connected"}
                else:
                    origin_tag = f"ws:{ws.remote_address[0]}:{ws.remote_address[1]}"
                    result = await self._run_chat_nonblocking(
                        message=message,
                        origin=origin_tag,
                        request_id=request_id,
                        action=action,
                    )
                    route = result.get("route", "unknown")
                    decision = result.get("decision", {}) or {}
                    self._events.emit(
                        "chat_intent",
                        f"route={route}",
                        metadata={
                            "route": route,
                            "confidence": decision.get("confidence"),
                            "reason": decision.get("reason"),
                            "mode": decision.get("mode"),
                        },
                    )

            elif action == "send_voice":
                message = data.get("text", "") or data.get("message", "")
                if not message:
                    result = {"error": "Missing 'text'"}
                elif not self._orchestrator:
                    result = {"error": "Orchestrator not connected"}
                else:
                    origin_tag = f"voice:ws:{ws.remote_address[0]}:{ws.remote_address[1]}"
                    self._events.emit(
                        "voice_command",
                        f"voice input: {str(message)[:120]}",
                        metadata={"origin": origin_tag, "request_id": request_id},
                    )

                    # Voice interactions should return a direct reply for speech-to-speech UX.
                    voice_result = await self._orchestrator.handle_message(
                        str(message),
                        origin=origin_tag,
                    )
                    reply = (voice_result.get("reply") or "").strip()
                    result = {
                        "success": voice_result.get("status") != "failed",
                        "transcript": str(message),
                        "reply": reply,
                        "status": voice_result.get("status"),
                        "route": voice_result.get("route"),
                        "decision": voice_result.get("decision", {}),
                    }

            elif action == "run_code_orchestration":
                if not self._orchestrator:
                    result = {"error": "Orchestrator not connected"}
                else:
                    code = str(data.get("code", "") or "")
                    timeout = int(data.get("timeout", 30) or 30)
                    if not code.strip():
                        result = {"error": "Missing 'code'"}
                    else:
                        result = self._orchestrator.run_code_orchestration(
                            code=code,
                            timeout=max(1, min(timeout, 300)),
                        )

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
                    origin_tag = f"ws:{request_id}:run_tests" if request_id else "ws:run_tests"
                    asyncio.create_task(self._orchestrator.run_task(prompt, origin=origin_tag))
                    result = {"queued": "run_tests"}
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "build_project":
                if self._orchestrator:
                    prompt = "Build the current project and report build status and any errors."
                    origin_tag = (
                        f"ws:{request_id}:build_project" if request_id else "ws:build_project"
                    )
                    asyncio.create_task(self._orchestrator.run_task(prompt, origin=origin_tag))
                    result = {"queued": "build_project"}
                else:
                    result = {"error": "Orchestrator not connected"}

            elif action == "git_status":
                cwd = self._orchestrator.project_path if self._orchestrator else None
                proc = await asyncio.create_subprocess_exec(
                    "git",
                    "status",
                    "--short",
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
                    path = self._resolve_client_path(file_path)
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
                    path = self._resolve_client_path(file_path)
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
                    path = self._resolve_client_path(file_path)
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

                # Listing containers can be slow right after the container system is started.
                cmd_result = await _run_container_cmd("list", "--format", "json", timeout=30)
                if cmd_result["exit_code"] == 0 and cmd_result["stdout"]:
                    try:
                        containers = json.loads(cmd_result["stdout"])
                        jarvis_containers = [
                            c
                            for c in containers
                            if c.get("configuration", {}).get("id", "").startswith("jarvis-")
                        ]
                        result = {
                            "containers": [self._normalize_container(c) for c in jarvis_containers]
                        }
                    except json.JSONDecodeError:
                        result = {
                            "containers": [],
                            "error": "Failed to decode container list JSON",
                            "raw_output": (cmd_result["stdout"] or "")[:2000],
                        }
                else:
                    err = (
                        cmd_result.get("stderr")
                        or cmd_result.get("stdout")
                        or "container list failed"
                    )
                    result = {"containers": [], "error": err[:2000]}

            elif action == "get_workspace_snapshot":
                result = await self._build_workspace_snapshot()

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
                        "output": start_result["stdout"]
                        or stop_result["stderr"]
                        or start_result["stderr"],
                    }

            else:
                result = {"error": f"Unknown action: {action}"}

        except Exception as e:
            logger.exception("Command error (%s): %s", action, e)
            result = {"error": str(e), "error_type": type(e).__name__}

        duration_ms = int(max(0.0, (time.time() - started_at) * 1000))
        if isinstance(result, dict):
            result.setdefault("_meta", {})
            result["_meta"].update(
                {
                    "request_id": request_id,
                    "action": action,
                    "duration_ms": duration_ms,
                }
            )

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
        preflight = raw_status.get("preflight") or {}

        return {
            **raw_status,
            "status": status,
            "current_session": raw_status.get("session_id"),
            "current_feature": active_tasks[0]["description"][:120] if active_tasks else None,
            "uptime": max(0.0, time.time() - self._started_at),
            "preflight_ready": bool(preflight.get("ready", False)),
            "preflight_errors": preflight.get("errors", []),
            "preflight_warnings": preflight.get("warnings", []),
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

    async def _build_workspace_snapshot(self) -> dict:
        """Return workspace/worktree/container snapshot for UI visibility."""
        from jarvis.container_tools import _run_container_cmd
        from jarvis.config import (
            JARVIS_A2A_TOKEN,
            JARVIS_CONFIG,
            JARVIS_DB,
            JARVIS_LOGS,
            JARVIS_MCP_RUNTIME_CONFIG,
            JARVIS_OPENCODE_CONFIG,
            JARVIS_PIDS,
            JARVIS_RUNTIME_WORKFLOW_DIR,
            JARVIS_SYSTEM_DIR,
        )

        workspace = (
            Path(self._orchestrator.project_path if self._orchestrator else ".")
            .expanduser()
            .resolve()
        )
        worktrees = await asyncio.to_thread(self._discover_workspace_worktrees, workspace)

        containers: list[dict] = []
        cmd_result = await _run_container_cmd("list", "--format", "json", timeout=30)
        if cmd_result["exit_code"] == 0 and cmd_result["stdout"]:
            try:
                parsed = json.loads(cmd_result["stdout"])
                containers = [
                    c
                    for c in parsed
                    if c.get("configuration", {}).get("id", "").startswith("jarvis-")
                ]
            except json.JSONDecodeError:
                containers = []

        mapped_containers = self._map_containers_to_worktrees(containers, worktrees)
        task_executions = await asyncio.to_thread(self._build_task_execution_rows)
        recent_events = await asyncio.to_thread(self._build_workspace_trace_events)

        cfg = getattr(self._orchestrator, "config", None)
        models = getattr(cfg, "models", None) if cfg else None
        provider_type = getattr(models, "provider_type", None) if models else None
        model_executor = getattr(models, "executor", None) if models else None
        workspace_root = getattr(cfg, "workspace_root", None) if cfg else None
        capabilities = self._orchestrator.get_capabilities() if self._orchestrator else {}
        mcp_info = capabilities.get("mcp_servers", {}) if isinstance(capabilities, dict) else {}
        static_mcp = mcp_info.get("static", []) if isinstance(mcp_info, dict) else []
        dynamic_mcp = mcp_info.get("dynamic", []) if isinstance(mcp_info, dict) else []
        capability_tools = capabilities.get("tools", []) if isinstance(capabilities, dict) else []
        capability_agents = capabilities.get("agents", []) if isinstance(capabilities, dict) else []
        capability_hooks = capabilities.get("hooks", []) if isinstance(capabilities, dict) else []
        capability_skills = capabilities.get("skills", []) if isinstance(capabilities, dict) else []
        skills_enabled = bool(capabilities.get("skills_enabled", False)) if isinstance(capabilities, dict) else False
        delegated_provider_policy = os.environ.get("JARVIS_DELEGATED_PROVIDER_POLICY", "opencode_only")
        delegated_permission_mode = os.environ.get("JARVIS_A2A_PERMISSION_MODE", "bypassPermissions")
        opencode_permission_rules_count = 0
        opencode_permission_profile = "unknown"
        try:
            from jarvis.opencode_client import get_opencode_client

            opencode_client = get_opencode_client()
            rules = opencode_client._session_permission_rules()
            opencode_permission_rules_count = len(rules) if isinstance(rules, list) else 0
            opencode_permission_profile = "custom" if opencode_permission_rules_count > 0 else "none"
        except Exception:
            pass
        mcp_tool_count = (
            len([t for t in capability_tools if isinstance(t, str) and t.startswith("mcp__")])
            if isinstance(capability_tools, list)
            else 0
        )
        skill_tool_available = (
            any(t == "Skill" or t == "skill://Skill" for t in capability_tools)
            if isinstance(capability_tools, list)
            else False
        )
        opencode_inventory = await asyncio.to_thread(self._discover_opencode_inventory)

        return {
            "workspace_root": str(workspace),
            "runtime_config": {
                "provider_type": provider_type,
                "model_executor": model_executor,
                "workspace_root_config": workspace_root,
                "a2a_workflow_mode": os.environ.get("JARVIS_A2A_WORKFLOW_MODE", "auto"),
                "a2a_opencode_model": os.environ.get("JARVIS_A2A_OPENCODE_MODEL", "opencode/glm-5-free"),
                "task_timeout_secs": os.environ.get("JARVIS_TASK_TIMEOUT_SECS", ""),
                "opencode_timeout_secs": os.environ.get("JARVIS_OPENCODE_TIMEOUT_SECS", "300"),
                "delegated_provider_policy": delegated_provider_policy,
                "delegated_permission_mode": delegated_permission_mode,
                "opencode_session_permission_profile": opencode_permission_profile,
                "opencode_session_permissions_count": opencode_permission_rules_count,
                "mcp_config_source": str(JARVIS_MCP_RUNTIME_CONFIG),
                "loaded_static_mcp_servers": static_mcp,
                "loaded_dynamic_mcp_servers": dynamic_mcp,
                "capability_tool_count": len(capability_tools) if isinstance(capability_tools, list) else 0,
                "capability_mcp_tool_count": mcp_tool_count,
                "capability_agents": capability_agents if isinstance(capability_agents, list) else [],
                "capability_hooks": capability_hooks if isinstance(capability_hooks, list) else [],
                "capability_skills": capability_skills if isinstance(capability_skills, list) else [],
                "skills_enabled": skills_enabled,
                "skill_tool_available": skill_tool_available,
                "discovered_skill_count": len(opencode_inventory.get("skills", [])),
                "discovered_skills_preview": opencode_inventory.get("skills", [])[:8],
                "discovered_skills": opencode_inventory.get("skills", []),
                "discovered_mcp_servers": opencode_inventory.get("mcp_servers", []),
            },
            "summary": {
                "worktree_count": len(worktrees),
                "container_count": len(mapped_containers),
                "mapped_container_count": len([c for c in mapped_containers if c.get("worktree_path")]),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "paths": {
                "jarvis_home": str(Path.home() / ".jarvis"),
                "system_dir": str(JARVIS_SYSTEM_DIR),
                "jarvis_config": str(JARVIS_CONFIG),
                "opencode_config": str(JARVIS_OPENCODE_CONFIG),
                "runtime_workflow_dir": str(JARVIS_RUNTIME_WORKFLOW_DIR),
                "runtime_docs_dir": str(JARVIS_RUNTIME_WORKFLOW_DIR / "docs"),
                "runtime_mcp_config": str(JARVIS_MCP_RUNTIME_CONFIG),
                "a2a_token": str(JARVIS_A2A_TOKEN),
                "logs_dir": str(JARVIS_LOGS),
                "db_path": str(JARVIS_DB),
                "pids_dir": str(JARVIS_PIDS),
            },
            "worktrees": worktrees,
            "containers": mapped_containers,
            "task_executions": task_executions,
            "recent_events": recent_events,
        }

    def _build_task_execution_rows(self, limit: int = 24) -> list[dict]:
        """Build per-task runtime config rows from task and timeline state."""
        if not self._orchestrator:
            return []

        cfg = getattr(self._orchestrator, "config", None)
        configured_workspace_root = (
            str(Path(cfg.workspace_root).expanduser().resolve())
            if cfg and getattr(cfg, "workspace_root", None)
            else None
        )

        scopes: list[str] = []
        current_project = str(Path(self._orchestrator.project_path).expanduser().resolve())
        scopes.append(current_project)
        if configured_workspace_root and configured_workspace_root not in scopes:
            scopes.append(configured_workspace_root)

        by_id: dict[str, Any] = {}
        for scope in scopes:
            for task in self._orchestrator.memory.list_tasks(scope):
                by_id[task.id] = task

        tasks = sorted(by_id.values(), key=lambda t: t.updated_at, reverse=True)[:limit]
        if not tasks:
            return []

        timeline = self._orchestrator.memory.get_timeline(limit=600)
        by_task: dict[str, dict[str, Any]] = {}
        for event in timeline:
            task_id = event.get("task_id")
            if not task_id:
                continue
            by_task.setdefault(task_id, {})
            metadata = event.get("metadata") or {}
            event_type = event.get("event_type")
            if event_type == "task_workflow_selected":
                by_task[task_id]["workflow"] = metadata.get("workflow")
                by_task[task_id]["workflow_reason"] = metadata.get("reason")
            elif event_type == "task_execution_config":
                by_task[task_id]["provider_type"] = metadata.get("provider_type")
                by_task[task_id]["model_id"] = metadata.get("model_id")
                by_task[task_id]["workflow"] = metadata.get("workflow") or by_task[task_id].get("workflow")

        rows: list[dict] = []
        for task in tasks:
            meta = by_task.get(task.id, {})
            rows.append(
                {
                    "task_id": task.id,
                    "description": task.description,
                    "status": task.status,
                    "provider_type": meta.get("provider_type", "unknown"),
                    "model_id": meta.get("model_id", "unknown"),
                    "workflow": meta.get("workflow", "autonomous"),
                    "workflow_reason": meta.get("workflow_reason", ""),
                    "updated_at": task.updated_at,
                }
            )
        return rows

    def _build_workspace_trace_events(self, limit: int = 20) -> list[dict]:
        """Return recent high-signal events for workspace trace view."""
        if not self._orchestrator:
            return []

        allowed = {
            "task_start",
            "task_workflow_selected",
            "task_execution_config",
            "tool_use",
            "task_complete",
            "error",
        }
        timeline = self._orchestrator.memory.get_timeline(limit=200)
        events: list[dict] = []
        for item in timeline:
            event_type = item.get("event_type", "")
            if event_type not in allowed:
                continue
            events.append(
                {
                    "id": str(item.get("id", "")),
                    "timestamp": float(item.get("timestamp", 0.0) or 0.0),
                    "event_type": event_type,
                    "summary": str(item.get("summary", "")),
                    "task_id": item.get("task_id"),
                    "metadata": {
                        str(k): str(v)
                        for k, v in (item.get("metadata") or {}).items()
                        if v is not None
                    },
                }
            )
            if len(events) >= limit:
                break
        return events

    @staticmethod
    def _discover_workspace_worktrees(workspace_root: Path, max_depth: int = 7) -> list[dict]:
        """Find git worktrees under workspace root by scanning .git indirection files."""
        workspace_root = workspace_root.resolve()
        worktrees: list[dict] = []
        seen: set[str] = set()

        def _walk(path: Path, depth: int) -> None:
            if depth > max_depth:
                return
            try:
                entries = list(path.iterdir())
            except OSError:
                return

            git_file = path / ".git"
            if git_file.is_file():
                try:
                    text = git_file.read_text(errors="replace").strip()
                except OSError:
                    text = ""
                if text.startswith("gitdir:") and "/worktrees/" in text:
                    key = str(path)
                    if key not in seen:
                        seen.add(key)
                        worktrees.append(
                            {
                                "id": path.name,
                                "path": str(path),
                            }
                        )

            for child in entries:
                if not child.is_dir():
                    continue
                if child.name in {".git", ".venv", "node_modules", ".pytest_cache", "__pycache__"}:
                    continue
                _walk(child, depth + 1)

        _walk(workspace_root, 0)
        worktrees.sort(key=lambda item: item["path"])
        return worktrees

    def _map_containers_to_worktrees(self, containers: list[dict], worktrees: list[dict]) -> list[dict]:
        """Attach mount paths and best worktree match per container."""
        worktree_paths = [Path(w["path"]).resolve() for w in worktrees if w.get("path")]
        mapped: list[dict] = []

        for container in containers:
            normalized = self._normalize_container(container)
            mount_paths = self._extract_container_mount_paths(container)
            best_match = None
            for mount in mount_paths:
                mount_path = Path(mount).expanduser().resolve()
                for wt in worktree_paths:
                    if mount_path == wt or wt in mount_path.parents or mount_path in wt.parents:
                        best_match = str(wt)
                        break
                if best_match:
                    break

            normalized["mount_paths"] = mount_paths
            normalized["worktree_path"] = best_match
            mapped.append(normalized)

        return mapped

    @staticmethod
    def _extract_container_mount_paths(container: dict) -> list[str]:
        """Best-effort extraction of host mount paths from container JSON."""
        config = container.get("configuration", {}) or {}
        candidates = [
            config.get("volumes"),
            config.get("mounts"),
            config.get("bindMounts"),
            container.get("mounts"),
        ]
        mounts: list[str] = []

        for candidate in candidates:
            if not candidate:
                continue
            if isinstance(candidate, list):
                for item in candidate:
                    if isinstance(item, str):
                        host = item.split(":", 1)[0].strip()
                        if host:
                            mounts.append(host)
                    elif isinstance(item, dict):
                        host = (
                            item.get("source")
                            or item.get("hostPath")
                            or item.get("path")
                            or item.get("host")
                        )
                        if isinstance(host, str) and host:
                            mounts.append(host)

        deduped: list[str] = []
        seen: set[str] = set()
        for mount in mounts:
            if mount not in seen:
                seen.add(mount)
                deduped.append(mount)
        return deduped

    @staticmethod
    def _discover_opencode_tools() -> list[str]:
        """Discover tool surfaces from OpenCode runtime inventory."""
        inventory = JarvisWSServer._discover_opencode_inventory()
        return sorted(set(inventory.get("tools", [])))

    @staticmethod
    def _discover_opencode_inventory() -> dict[str, list[str]]:
        """Discover OpenCode runtime inventory using native OpenCode CLI commands."""
        from jarvis.config import JARVIS_OPENCODE_CONFIG

        binary = os.environ.get("JARVIS_OPENCODE_BIN", str(Path.home() / ".bun" / "bin" / "opencode"))
        env = os.environ.copy()
        env["OPENCODE_CONFIG"] = str(JARVIS_OPENCODE_CONFIG)
        discovered_tools: set[str] = set()
        discovered_skills: set[str] = set()
        discovered_mcp_servers: set[str] = set()

        def run_cli(*args: str, timeout: int = 25) -> str:
            try:
                proc = subprocess.run(
                    [binary, *args],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=timeout,
                    check=False,
                )
                return (proc.stdout or "").strip()
            except Exception:
                return ""

        # 1) Skills: OpenCode's own discovered skill catalog.
        skill_out = run_cli("debug", "skill")
        if skill_out:
            skill_json_blob = ""
            first = skill_out.find("[")
            last = skill_out.rfind("]")
            if first != -1 and last != -1 and last > first:
                skill_json_blob = skill_out[first:last + 1]
            try:
                skill_data = json.loads(skill_json_blob or skill_out)
            except json.JSONDecodeError:
                skill_data = None
            if isinstance(skill_data, list):
                for entry in skill_data:
                    if not isinstance(entry, dict):
                        continue
                    name = str(entry.get("name") or "").strip()
                    if name:
                        discovered_skills.add(name)
                        discovered_tools.add(f"skill://{name}")
            else:
                # Fallback: OpenCode may truncate huge skill payloads; extract names from raw output.
                for match in re.finditer(r'"name"\s*:\s*"([^"]+)"', skill_out):
                    name = str(match.group(1)).strip()
                    if name:
                        discovered_skills.add(name)
                        discovered_tools.add(f"skill://{name}")

        # 2) MCP servers discovered by OpenCode runtime.
        mcp_out = run_cli("mcp", "list")
        if mcp_out:
            ansi_free = re.sub(r"\x1B\[[0-9;]*[A-Za-z]", "", mcp_out)
            for line in ansi_free.splitlines():
                line = line.strip()
                match = re.search(r"[✓✗]\s+([A-Za-z0-9._-]+)", line)
                if match:
                    server_name = match.group(1)
                    discovered_mcp_servers.add(server_name)
                    discovered_tools.add(f"mcp://{server_name}")

        # 3) Session permission tool classes used for delegated execution.
        from jarvis.opencode_client import get_opencode_client

        try:
            client = get_opencode_client()
            for rule in client._session_permission_rules():
                permission = str(rule.get("permission") or "").strip()
                if permission:
                    discovered_tools.add(f"opencode://permission/{permission}")
        except Exception:
            pass

        return {
            "tools": sorted(discovered_tools),
            "skills": sorted(discovered_skills),
            "mcp_servers": sorted(discovered_mcp_servers),
        }

    def _broadcast_event(self, event_data: dict) -> None:
        """EventCollector listener callback: push events to all clients."""
        if not self._clients:
            return

        message = json.dumps(
            {"type": "event", "data": event_data},
            default=str,
        )

        # Check if we're in an async context with a running event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running event loop - schedule broadcast from the main loop
            logger.debug(
                f"No running loop, scheduling broadcast for {event_data.get('event_type')}"
            )
            # Use call_soon_threadsafe if we have a reference to the loop
            if self._server:
                asyncio.run_coroutine_threadsafe(
                    self._broadcast_to_clients(message), asyncio.get_event_loop()
                )
            return

        stale: set = set()
        for ws in self._clients:
            try:
                asyncio.ensure_future(ws.send(message), loop=loop)
            except Exception as e:
                logger.debug(f"Broadcast failed for client: {e}")
                stale.add(ws)

        self._clients -= stale

    async def _broadcast_to_clients(self, message: str) -> None:
        """Async helper to broadcast message to all clients."""
        stale: set = set()
        for ws in self._clients:
            try:
                await ws.send(message)
            except Exception as e:
                logger.debug(f"Broadcast failed for client: {e}")
                stale.add(ws)
        self._clients -= stale
