"""A2A Server: FastAPI endpoints for A2A protocol."""
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse

from jarvis.a2a.auth import validate_bearer_token
from jarvis.a2a.agent_card import build_agent_card
from jarvis.a2a.executor import JarvisAgentExecutor
from jarvis.config import JarvisConfig

logger = logging.getLogger(__name__)


def jsonrpc_error(code: int, message: str, request_id: Any = None, status: int = 400) -> JSONResponse:
    """Build a JSON-RPC 2.0 error response."""
    return JSONResponse(
        content={"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": request_id},
        status_code=status,
    )


def create_a2a_app(config: JarvisConfig, orchestrator: Any = None, project_path: str | None = None) -> FastAPI:
    """Create FastAPI app for A2A protocol.

    Args:
        config: Jarvis configuration
        orchestrator: Optional JarvisOrchestrator instance for task execution
        project_path: Optional project path for orchestrator creation
    """
    executor: JarvisAgentExecutor | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal executor
        try:
            logger.info("A2A lifespan startup: initializing executor...")
            executor = JarvisAgentExecutor(
                config,
                orchestrator=orchestrator,
                project_path=project_path,
            )
            logger.info(f"A2A server started successfully on port {config.a2a.port}")
            if orchestrator:
                logger.info("A2A executor wired to JarvisOrchestrator")
            else:
                logger.warning("A2A executor running without orchestrator - task submission may fail")
        except Exception as e:
            logger.exception(f"A2A lifespan startup failed: {e}")
            raise

        try:
            yield
        finally:
            # Cleanup
            try:
                if executor:
                    active = executor.get_active_tasks()
                    if active:
                        logger.warning(f"Shutting down with {len(active)} active tasks")
                logger.info("A2A server stopped")
            except Exception as e:
                logger.exception(f"A2A lifespan cleanup error: {e}")

    app = FastAPI(
        title="Jarvis A2A Server",
        description="A2A protocol server for Jarvis agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    def verify_auth(request: Request) -> bool:
        """Verify Bearer token from Authorization header.

        Auth is ALWAYS required. Token file must exist (created by daemon on startup).
        """
        token_path = config.a2a.token_path

        # If no custom token path, use default
        if not token_path:
            from jarvis.a2a.auth import get_token_path
            token_path = str(get_token_path(""))

        auth_header = request.headers.get("Authorization")
        if not validate_bearer_token(auth_header, token_path):
            raise HTTPException(
                status_code=401,
                detail={
                    "layer": "auth",
                    "code": "invalid_token",
                    "message": "Invalid or missing Bearer token",
                    "remediation": "Provide valid token in Authorization header. "
                                   "Token file should be at ~/.jarvis/system/jarvis_config/a2a_token",
                },
            )
        return True

    def _get_base_url(request: Request) -> str:
        """Extract base URL from request.

        Uses request's scheme and host header. Falls back to config port
        if host header doesn't include port.
        """
        scheme = request.url.scheme
        host = request.headers.get("host", f"localhost:{config.a2a.port}")

        # If host doesn't include port and we're not on standard ports, add it
        if ":" not in host:
            if scheme == "https" and config.a2a.port != 443:
                host = f"{host}:{config.a2a.port}"
            elif scheme == "http" and config.a2a.port != 80:
                host = f"{host}:{config.a2a.port}"

        return f"{scheme}://{host}"

    @app.get("/.well-known/agent-card.json")
    async def get_agent_card(request: Request):
        """Return Agent Card for discovery."""
        base_url = _get_base_url(request)
        return build_agent_card(base_url=base_url, port=config.a2a.port)

    @app.post("/")
    async def jsonrpc_endpoint(
        request: Request,
        _: bool = Depends(verify_auth),
    ):
        """Handle JSON-RPC 2.0 requests."""
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return jsonrpc_error(-32700, "Parse error")

        # Validate JSON-RPC structure
        if body.get("jsonrpc") != "2.0":
            return jsonrpc_error(-32600, "Invalid Request", body.get("id"))

        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")

        if method == "message/send":
            return await handle_message_send(params, request_id)
        elif method == "tasks/get":
            return await handle_tasks_get(params, request_id)
        elif method == "tasks/cancel":
            return await handle_tasks_cancel(params, request_id)
        else:
            return jsonrpc_error(-32601, f"Method not found: {method}", request_id)

    async def handle_message_send(params: dict, request_id: Any) -> JSONResponse:
        """Handle message/send method."""
        run_id = str(params.get("runId") or params.get("run_id") or "").strip()
        message = params.get("message") or params.get("content", {}).get("message")
        if not run_id:
            return jsonrpc_error(-32602, "Missing 'runId' parameter", request_id)
        if not message:
            return jsonrpc_error(-32602, "Missing 'message' parameter", request_id)

        blocking = params.get("blocking", False)
        if bool(blocking):
            return jsonrpc_error(-32602, "blocking=true is not supported; use non-blocking submit + tasks/get", request_id)
        context_id = params.get("contextId") or params.get("context_id")
        resume_session_id = params.get("resumeSessionId") or params.get("resume_session_id")
        task_type = params.get("taskType") or params.get("task_type")
        priority = params.get("priority")
        retry_policy = params.get("retryPolicy") or params.get("retry_policy")
        timeouts = params.get("timeouts")

        task = await executor.submit_task(
            run_id=run_id,
            message=message,
            blocking=blocking,
            context_id=context_id,
            resume_session_id=resume_session_id,
            task_type=task_type,
            priority=priority,
            retry_policy=retry_policy,
            timeouts=timeouts,
        )

        return JSONResponse(content={
            "jsonrpc": "2.0",
            "result": {
                "taskId": task.id,
                "runId": task.run_id,
                "status": task.status.value,
                "createdAt": task.created_at,
                "updatedAt": task.updated_at,
            },
            "id": request_id,
        })

    async def handle_tasks_get(params: dict, request_id: Any) -> JSONResponse:
        """Handle tasks/get method."""
        task_id = params.get("taskId") or params.get("task_id")
        if not task_id:
            return jsonrpc_error(-32602, "Missing 'taskId' parameter", request_id)

        task = await executor.get_task(task_id)
        if not task:
            return jsonrpc_error(-32602, f"Task not found: {task_id}", request_id, 404)

        result = {
            "taskId": task.id,
            "runId": task.run_id,
            "status": task.status.value,
            "createdAt": task.created_at,
            "updatedAt": task.updated_at,
        }
        if task.result:
            result["result"] = task.result
        if task.error:
            result["error"] = task.error
        if task.artifacts:
            result["artifacts"] = [
                {"name": a.name, "content": a.content, "mimeType": a.mime_type}
                for a in task.artifacts
            ]

        return JSONResponse(content={
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id,
        })

    async def handle_tasks_cancel(params: dict, request_id: Any) -> JSONResponse:
        """Handle tasks/cancel method."""
        task_id = params.get("taskId") or params.get("task_id")
        if not task_id:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "error": {"code": -32602, "message": "Missing 'taskId' parameter"},
                    "id": request_id,
                },
                status_code=400,
            )

        task = await executor.cancel_task(task_id)
        if not task:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "error": {"code": -32602, "message": f"Task not found: {task_id}"},
                    "id": request_id,
                },
                status_code=404,
            )

        return JSONResponse(content={
            "jsonrpc": "2.0",
            "result": {
                "taskId": task.id,
                "runId": task.run_id,
                "status": task.status.value,
            },
            "id": request_id,
        })

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok", "active_tasks": len(executor.get_active_tasks()) if executor else 0}

    return app


class JarvisA2AServer:
    """Manages A2A server lifecycle."""

    def __init__(
        self,
        config: JarvisConfig,
        orchestrator: Any = None,
        project_path: str | None = None,
    ):
        self.config = config
        self._orchestrator = orchestrator
        self._project_path = project_path
        self.app = create_a2a_app(config, orchestrator=orchestrator, project_path=project_path)
        self._server = None

    def set_orchestrator(self, orchestrator: Any) -> None:
        """Update the orchestrator reference."""
        self._orchestrator = orchestrator
        # Note: This requires app restart to take effect

    async def start(self) -> None:
        """Start the A2A server."""
        import uvicorn
        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=self.config.a2a.port,
            log_level="info",
        )
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def stop(self) -> None:
        """Stop the A2A server."""
        if self._server:
            self._server.should_exit = True
