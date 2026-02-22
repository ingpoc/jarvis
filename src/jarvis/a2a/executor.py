"""A2A Executor: bridges A2A protocol to Jarvis Orchestrator."""

import asyncio
import json
import logging
import os
from typing import Any

from jarvis.a2a.models import A2ATask, A2ATaskState, A2AArtifact
from jarvis.a2a.task_store import A2ATaskStore
from jarvis.a2a.streaming import get_emitter
from jarvis.config import JarvisConfig
from jarvis.openclaw_notifier import OpenClawNotifier

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
        import logging
        logger = logging.getLogger(__name__)
        logger.info("JarvisAgentExecutor.__init__: starting")

        self.config = config
        logger.info("JarvisAgentExecutor.__init__: config set")

        self.task_store = task_store or A2ATaskStore()
        logger.info("JarvisAgentExecutor.__init__: task_store created")

        self.session_manager = session_manager
        logger.info("JarvisAgentExecutor.__init__: session_manager disabled in OpenCode-only mode")

        self._orchestrator = orchestrator
        self._project_path = project_path
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._timeout_watchdogs: dict[str, asyncio.Task] = {}
        self._task_clients: dict[str, Any] = {}
        logger.info("JarvisAgentExecutor.__init__: getting emitter")

        self._emitter = get_emitter()
        logger.info("JarvisAgentExecutor.__init__: emitter obtained")
        self._openclaw_notifier = OpenClawNotifier.from_env()

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
        message: str,
        blocking: bool = True,
        context_id: str | None = None,
        resume_session_id: str | None = None,
        options: Any | None = None,
    ) -> A2ATask:
        """Submit a new task for execution.

        Args:
            message: The user message/task description
            blocking: If True, wait for completion; if False, return immediately
            context_id: Optional context ID for session isolation
            resume_session_id: Optional OpenCode session id for explicit resume
                    options: Reserved for compatibility; ignored in OpenCode-only mode

        Returns:
            A2ATask with current status
        """
        # Create task record
        task = self.task_store.create_task(message=message, context_id=context_id)

        # Emit task created event
        await self._emit_event(task.id, "task_created", {
            "taskId": task.id,
            "status": task.status.value,
            "message": message[:200],
        })

        # Start async execution
        async def execute():
            heartbeat_task: asyncio.Task | None = None
            try:
                # Update to working state
                self.task_store.update_task_status(task.id, A2ATaskState.WORKING)
                await self._emit_event(task.id, "task_started", {
                    "taskId": task.id,
                    "status": A2ATaskState.WORKING.value,
                })

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
                if self._orchestrator:
                    orchestrator_result = await self._execute_with_orchestrator(
                        task.id, message, channel_id, resume_session_id=resume_session_id
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
                else:
                    raise RuntimeError("No orchestrator configured for OpenCode-only A2A execution")

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

                # Update task with result
                self.task_store.update_task_status(
                    task.id,
                    A2ATaskState.COMPLETED,
                    result=result_text[:5000] if result_text else None,
                )
                await self._emit_event(task.id, "task_completed", {
                    "taskId": task.id,
                    "status": A2ATaskState.COMPLETED.value,
                })

            except asyncio.CancelledError:
                existing = self.task_store.get_task(task.id)
                is_timeout_failure = bool(
                    existing
                    and existing.status == A2ATaskState.FAILED
                    and existing.error
                    and "timed out after" in existing.error
                )
                if not is_timeout_failure:
                    self.task_store.update_task_status(
                        task.id,
                        A2ATaskState.CANCELED,
                        error="Task cancelled by user",
                    )
                    await self._emit_event(task.id, "task_canceled", {
                        "taskId": task.id,
                        "status": A2ATaskState.CANCELED.value,
                    })
                raise
            except Exception as e:
                logger.exception(f"A2A task {task.id} failed: {e}")
                self.task_store.update_task_status(
                    task.id,
                    A2ATaskState.FAILED,
                    error=str(e),
                )
                await self._emit_event(task.id, "task_failed", {
                    "taskId": task.id,
                    "status": A2ATaskState.FAILED.value,
                    "error": str(e),
                })
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

        # Non-blocking tasks must still enforce a hard runtime limit. Without this watchdog,
        # delegated OpenClaw tasks can remain "working" indefinitely if the upstream call hangs.
        if not blocking and self._timeout > 0:
            async def timeout_watchdog(task_id: str) -> None:
                await asyncio.sleep(self._timeout)
                current = self.task_store.get_task(task_id)
                if not current or current.status not in {A2ATaskState.SUBMITTED, A2ATaskState.WORKING}:
                    return
                timeout_error = f"Task timed out after {self._timeout} seconds"
                self.task_store.update_task_status(
                    task_id,
                    A2ATaskState.FAILED,
                    error=timeout_error,
                )
                await self._emit_event(task_id, "task_failed", {
                    "taskId": task_id,
                    "status": A2ATaskState.FAILED.value,
                    "error": timeout_error,
                })
                running = self._active_tasks.get(task_id)
                if running and not running.done():
                    running.cancel()

            self._timeout_watchdogs[task.id] = asyncio.create_task(timeout_watchdog(task.id))

        if blocking:
            try:
                await asyncio.wait_for(coro_task, timeout=self._timeout)
            except asyncio.TimeoutError:
                self.task_store.update_task_status(
                    task.id,
                    A2ATaskState.FAILED,
                    error=f"Task timed out after {self._timeout} seconds",
                )
                await self._emit_event(task.id, "task_failed", {
                    "taskId": task.id,
                    "status": A2ATaskState.FAILED.value,
                    "error": f"Task timed out after {self._timeout} seconds",
                })

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
                emit_notifications=False,  # A2A handles its own notifications
                channel_id=channel_id,
                resume_session_id=resume_session_id,
            )

            return result

        except Exception as e:
            logger.exception(f"Orchestrator execution failed for {task_id}: {e}")
            raise

    async def _emit_event(self, task_id: str, event_type: str, data: dict) -> None:
        """Emit an event to streaming subscribers."""
        try:
            await self._emitter.emit(task_id, event_type, data)
        except Exception as e:
            logger.debug(f"Event emit failed (non-blocking): {e}")
        try:
            await self._openclaw_notifier.notify_task_event(task_id, event_type, data)
        except Exception as e:
            logger.debug(f"OpenClaw notify failed (non-blocking): {e}")

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
            if hasattr(client, 'interrupt'):
                await client.interrupt()

        return self.task_store.get_task(task_id)

    async def get_task(self, task_id: str) -> A2ATask | None:
        """Get current task state."""
        return self.task_store.get_task(task_id)

    def get_active_tasks(self) -> list[str]:
        """Get list of active task IDs."""
        return list(self._active_tasks.keys())
