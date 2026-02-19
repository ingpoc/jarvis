"""A2A Executor: bridges A2A protocol to Jarvis Orchestrator."""

import asyncio
import logging
from typing import Any

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

from jarvis.a2a.models import A2ATask, A2ATaskState, A2AArtifact
from jarvis.a2a.task_store import A2ATaskStore
from jarvis.a2a.streaming import get_emitter
from jarvis.session_manager import SessionManager
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
        session_manager: SessionManager | None = None,
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

        self.session_manager = session_manager or SessionManager.get_instance()
        logger.info("JarvisAgentExecutor.__init__: session_manager initialized")

        self._orchestrator = orchestrator
        self._project_path = project_path
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._task_clients: dict[str, ClaudeSDKClient] = {}
        logger.info("JarvisAgentExecutor.__init__: getting emitter")

        self._emitter = get_emitter()
        logger.info("JarvisAgentExecutor.__init__: emitter obtained")
        self._openclaw_notifier = OpenClawNotifier.from_env()

        self._timeout = config.a2a.task_timeout_seconds
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
        options: ClaudeAgentOptions | None = None,
    ) -> A2ATask:
        """Submit a new task for execution.

        Args:
            message: The user message/task description
            blocking: If True, wait for completion; if False, return immediately
            context_id: Optional context ID for session isolation
            options: Optional ClaudeAgentOptions for the client

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
            try:
                # Update to working state
                self.task_store.update_task_status(task.id, A2ATaskState.WORKING)
                await self._emit_event(task.id, "task_started", {
                    "taskId": task.id,
                    "status": A2ATaskState.WORKING.value,
                })

                # Get or create client for this context
                channel_id = context_id or f"a2a-{task.id}"
                client = await self.session_manager.get_client(channel_id, options)
                self._task_clients[task.id] = client

                # Execute via orchestrator or client
                if self._orchestrator:
                    result_text = await self._execute_with_orchestrator(
                        task.id, message, channel_id
                    )
                else:
                    result_text = await self._execute_with_client(client, message)

                # Add result as artifact
                if result_text:
                    self.task_store.add_artifact(
                        task.id,
                        name="result",
                        content=result_text,
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
                self._task_clients.pop(task.id, None)
                self._active_tasks.pop(task.id, None)

        # Create asyncio task
        coro_task = asyncio.create_task(execute())
        self._active_tasks[task.id] = coro_task

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
    ) -> str:
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
            )

            # Extract result text
            if isinstance(result, dict):
                return result.get("output", result.get("reply", str(result)))
            return str(result)

        except Exception as e:
            logger.exception(f"Orchestrator execution failed for {task_id}: {e}")
            raise

    async def _execute_with_client(
        self,
        client: ClaudeSDKClient,
        message: str,
    ) -> str:
        """Execute message with Claude SDK client directly.

        Used when no orchestrator is configured.
        """
        try:
            await client.query(message)
            result_text = ""
            async for msg in client.receive_response():
                if hasattr(msg, 'content'):
                    for block in msg.content:
                        if hasattr(block, 'text'):
                            result_text += block.text + "\n"
            return result_text.strip() or f"Task received: {message[:100]}"
        except Exception as e:
            logger.exception(f"Direct client execution failed: {e}")
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
