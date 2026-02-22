"""A2A Executor: bridges A2A protocol to Jarvis Orchestrator."""

import asyncio
import json
import logging
import os
import platform
import resource
import time
from typing import Any

from jarvis.a2a.models import A2ATask, A2ATaskState
from jarvis.a2a.task_store import A2ATaskStore
from jarvis.config import JarvisConfig

logger = logging.getLogger(__name__)


class JarvisAgentExecutor:
    """Executes A2A tasks using the Jarvis orchestration layer."""

    DEFAULT_TIMEOUT_SECONDS = 300

    def __init__(
        self,
        config: JarvisConfig,
        task_store: A2ATaskStore | None = None,
        session_manager: Any | None = None,
        orchestrator: Any = None,
        project_path: str | None = None,
    ):
        logger.info("JarvisAgentExecutor.__init__: starting")

        self.config = config
        self.task_store = task_store or A2ATaskStore()
        self.session_manager = session_manager
        self._orchestrator = orchestrator
        self._project_path = project_path
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._timeout_watchdogs: dict[str, asyncio.Task] = {}
        self._task_clients: dict[str, Any] = {}

        self._timeout = config.a2a.task_timeout_seconds
        self._progress_heartbeat_seconds = max(
            1.0,
            float(os.environ.get("JARVIS_A2A_PROGRESS_HEARTBEAT_SECS", "5")),
        )
        logger.info("JarvisAgentExecutor.__init__: initialization complete")

    def set_orchestrator(self, orchestrator: Any) -> None:
        """Set the orchestrator instance for task execution."""
        self._orchestrator = orchestrator

    def set_project_path(self, project_path: str) -> None:
        """Set the project path for orchestrator creation."""
        self._project_path = project_path

    async def submit_task(
        self,
        run_id: str,
        message: str,
        blocking: bool = False,
        context_id: str | None = None,
        resume_session_id: str | None = None,
        task_type: str | None = None,
        priority: str | None = None,
        retry_policy: dict[str, Any] | None = None,
        timeouts: dict[str, Any] | None = None,
    ) -> A2ATask:
        """Submit a new task for execution.

        Args:
            run_id: Idempotency key provided by NanoClaw
            message: The user message/task description
            blocking: If True, wait for completion; if False, return immediately
            context_id: Optional context ID for session isolation
            resume_session_id: Optional OpenCode session id for explicit resume

        Returns:
            A2ATask with current status
        """
        run_id = (run_id or "").strip()
        if not run_id:
            raise ValueError("run_id is required")

        existing = self.task_store.get_task_by_run_id(run_id)
        if existing:
            return existing

        # Create task record
        task = self.task_store.create_task(
            run_id=run_id,
            message=message,
            context_id=context_id,
        )

        # Start async execution
        async def execute() -> None:
            heartbeat_task: asyncio.Task | None = None
            started_at = time.monotonic()
            try:
                # Update to working state
                self.task_store.update_task_status(task.id, A2ATaskState.WORKING)
                async def heartbeat() -> None:
                    while True:
                        await asyncio.sleep(self._progress_heartbeat_seconds)
                        current = self.task_store.get_task(task.id)
                        if not current or current.status not in {A2ATaskState.SUBMITTED, A2ATaskState.WORKING}:
                            return
                        # Touch updated_at so long-running delegated tasks show forward progress.
                        self.task_store.update_task_status(task.id, A2ATaskState.WORKING)

                heartbeat_task = asyncio.create_task(heartbeat())

                channel_id = context_id or f"a2a-{task.id}"

                # Execute via orchestrator only in OpenCode-only mode.
                opencode_session_id: str | None = None
                if not self._orchestrator:
                    raise RuntimeError("No orchestrator configured for OpenCode-only A2A execution")

                orchestrator_result = await self._execute_with_orchestrator(
                    task.id,
                    message,
                    channel_id,
                    resume_session_id=resume_session_id,
                )

                if isinstance(orchestrator_result, dict):
                    raw_result = (
                        orchestrator_result.get("output")
                        or orchestrator_result.get("reply")
                        or orchestrator_result
                    )
                    result_text = raw_result if isinstance(raw_result, str) else str(raw_result)
                    candidate_session_id = orchestrator_result.get("session_id")
                    if isinstance(candidate_session_id, str) and candidate_session_id.strip():
                        opencode_session_id = candidate_session_id.strip()
                else:
                    result_text = str(orchestrator_result)

                usage = self._extract_usage(orchestrator_result)
                usage["duration_ms"] = int(max(0.0, (time.monotonic() - started_at) * 1000.0))
                usage["peak_rss_mb"] = self._peak_rss_mb()

                # Add result as artifact
                if result_text:
                    self.task_store.add_artifact(
                        task.id,
                        name="result",
                        content=result_text,
                        mime_type="text/plain",
                    )
                if isinstance(orchestrator_result, dict):
                    research_gate = orchestrator_result.get("research_gate")
                    if isinstance(research_gate, dict):
                        self.task_store.add_artifact(
                            task.id,
                            name="research_gate",
                            content=json.dumps(research_gate, ensure_ascii=True),
                            mime_type="application/json",
                        )
                    quality_assessment = orchestrator_result.get("quality_assessment")
                    if isinstance(quality_assessment, dict):
                        self.task_store.add_artifact(
                            task.id,
                            name="quality_assessment",
                            content=json.dumps(quality_assessment, ensure_ascii=True),
                            mime_type="application/json",
                        )
                if opencode_session_id:
                    self.task_store.add_artifact(
                        task.id,
                        name="opencode_session",
                        content=opencode_session_id,
                        mime_type="text/plain",
                    )
                self.task_store.add_artifact(
                    task.id,
                    name="usage",
                    content=json.dumps(usage, ensure_ascii=True),
                    mime_type="application/json",
                )
                self.task_store.add_artifact(
                    task.id,
                    name="run_meta",
                    content=json.dumps(
                        {
                            "run_id": run_id,
                            "context_id": context_id,
                            "task_id": task.id,
                            "task_type": task_type,
                            "priority": priority,
                            "retry_policy": retry_policy,
                            "timeouts": timeouts,
                            "worker_identity": self._worker_identity(),
                        },
                        ensure_ascii=True,
                    ),
                    mime_type="application/json",
                )

                # Update task with result
                self.task_store.update_task_status(
                    task.id,
                    A2ATaskState.COMPLETED,
                    result=result_text[:5000] if result_text else None,
                )
            except asyncio.CancelledError:
                existing = self.task_store.get_task(task.id)
                is_timeout_failure = bool(
                    existing
                    and existing.status == A2ATaskState.FAILED
                    and existing.error
                    and "TASK_TIMEOUT" in existing.error
                )
                if not is_timeout_failure:
                    self.task_store.update_task_status(
                        task.id,
                        A2ATaskState.CANCELED,
                        error=json.dumps(
                            {"code": "TASK_CANCELED", "message": "Task cancelled by user"},
                            ensure_ascii=True,
                        ),
                    )
                raise
            except Exception as e:  # noqa: BLE001
                logger.exception("A2A task %s failed: %s", task.id, e)
                error_payload = {
                    "code": "TASK_EXECUTION_ERROR",
                    "message": str(e),
                }
                self.task_store.update_task_status(
                    task.id,
                    A2ATaskState.FAILED,
                    error=json.dumps(error_payload, ensure_ascii=True),
                )
            finally:
                if heartbeat_task and not heartbeat_task.done():
                    heartbeat_task.cancel()
                self._task_clients.pop(task.id, None)
                self._active_tasks.pop(task.id, None)
                watchdog = self._timeout_watchdogs.pop(task.id, None)
                if watchdog and not watchdog.done():
                    watchdog.cancel()

        # Create asyncio task
        coro_task = asyncio.create_task(execute())
        self._active_tasks[task.id] = coro_task

        # Non-blocking tasks must still enforce a hard runtime limit.
        if not blocking and self._timeout > 0:

            async def timeout_watchdog(task_id: str) -> None:
                await asyncio.sleep(self._timeout)
                current = self.task_store.get_task(task_id)
                if not current or current.status not in {A2ATaskState.SUBMITTED, A2ATaskState.WORKING}:
                    return
                timeout_error = f"Task timed out after {self._timeout} seconds"
                error_payload = {"code": "TASK_TIMEOUT", "message": timeout_error}
                self.task_store.update_task_status(
                    task_id,
                    A2ATaskState.FAILED,
                    error=json.dumps(error_payload, ensure_ascii=True),
                )
                running = self._active_tasks.get(task_id)
                if running and not running.done():
                    running.cancel()

            self._timeout_watchdogs[task.id] = asyncio.create_task(timeout_watchdog(task.id))

        if blocking:
            try:
                await asyncio.wait_for(coro_task, timeout=self._timeout)
            except asyncio.TimeoutError:
                error_payload = {
                    "code": "TASK_TIMEOUT",
                    "message": f"Task timed out after {self._timeout} seconds",
                }
                self.task_store.update_task_status(
                    task.id,
                    A2ATaskState.FAILED,
                    error=json.dumps(error_payload, ensure_ascii=True),
                )
        return self.task_store.get_task(task.id) or task

    async def _execute_with_orchestrator(
        self,
        task_id: str,
        message: str,
        channel_id: str,
        resume_session_id: str | None = None,
    ) -> Any:
        """Execute using the JarvisOrchestrator."""
        if not self._orchestrator:
            return "No orchestrator configured"

        try:
            # Run the task through orchestrator with channel_id for session isolation.
            # Do NOT call set_channel() on shared orchestrator to avoid race conditions
            # with concurrent A2A tasks - run_task() handles channel isolation internally.
            result = await self._orchestrator.run_task(
                task_description=message,
                origin="a2a",
                emit_notifications=False,
                channel_id=channel_id,
                resume_session_id=resume_session_id,
            )
            return result

        except Exception as e:  # noqa: BLE001
            logger.exception("Orchestrator execution failed for %s: %s", task_id, e)
            raise

    async def cancel_task(self, task_id: str) -> A2ATask | None:
        """Cancel a running task.

        Uses client.interrupt() to stop the current operation.
        """
        task = self.task_store.get_task(task_id)
        if not task:
            return None

        # Check if task is still running
        if task.status not in {A2ATaskState.SUBMITTED, A2ATaskState.WORKING}:
            return task

        # Cancel the asyncio task
        watchdog = self._timeout_watchdogs.pop(task_id, None)
        if watchdog and not watchdog.done():
            watchdog.cancel()
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()
            try:
                await self._active_tasks[task_id]
            except asyncio.CancelledError:
                pass

        # Interrupt the client if available
        if task_id in self._task_clients:
            client = self._task_clients[task_id]
            if hasattr(client, "interrupt"):
                await client.interrupt()

        return self.task_store.get_task(task_id)

    async def get_task(self, task_id: str) -> A2ATask | None:
        """Get current task state."""
        return self.task_store.get_task(task_id)

    def get_active_tasks(self) -> list[str]:
        """Get list of active task IDs."""
        return list(self._active_tasks.keys())

    @staticmethod
    def _peak_rss_mb() -> int:
        """Best-effort process RSS high watermark in MiB."""
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # macOS reports bytes; Linux reports KiB.
        if rss > 10_000_000:
            return int(rss / (1024 * 1024))
        return int(rss / 1024)

    @staticmethod
    def _extract_usage(orchestrator_result: Any) -> dict[str, int]:
        """Extract usage stats from orchestrator result payload."""
        usage = {"input_tokens": 0, "output_tokens": 0}
        if not isinstance(orchestrator_result, dict):
            return usage
        raw = orchestrator_result.get("usage")
        if isinstance(raw, dict):
            usage["input_tokens"] = int(raw.get("input_tokens", 0) or 0)
            usage["output_tokens"] = int(raw.get("output_tokens", 0) or 0)
        return usage

    @staticmethod
    def _worker_identity() -> str:
        return os.environ.get("JARVIS_WORKER_ID", f"jarvis@{platform.node()}:{os.getpid()}")
