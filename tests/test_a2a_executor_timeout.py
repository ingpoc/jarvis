import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.a2a.executor import JarvisAgentExecutor
from jarvis.a2a.models import A2ATaskState
from jarvis.a2a.task_store import A2ATaskStore
from jarvis.memory import MemoryStore


class _DummySessionManager:
    async def get_client(self, channel_id: str, options=None):  # noqa: ANN001
        return object()


class _FailingSessionManager:
    async def get_client(self, channel_id: str, options=None):  # noqa: ANN001
        raise AssertionError("get_client() should not be called when orchestrator is configured")


class _SlowOrchestrator:
    async def run_task(self, **kwargs):  # noqa: ANN003
        await asyncio.sleep(10)
        return {"output": "should not complete before timeout"}


class _FastOrchestrator:
    async def run_task(self, **kwargs):  # noqa: ANN003
        return {"output": "ok"}


class _CountingOrchestrator:
    def __init__(self) -> None:
        self.calls = 0

    async def run_task(self, **kwargs):  # noqa: ANN003
        self.calls += 1
        return {"output": "ok", "usage": {"input_tokens": 10, "output_tokens": 20}}


@pytest.mark.asyncio
async def test_non_blocking_task_enforces_timeout_watchdog() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "a2a-timeout.db"
        store = A2ATaskStore(memory=MemoryStore(db_path=db_path))
        config = SimpleNamespace(a2a=SimpleNamespace(task_timeout_seconds=1))
        executor = JarvisAgentExecutor(
            config=config,
            task_store=store,
            session_manager=_DummySessionManager(),
            orchestrator=_SlowOrchestrator(),
        )

        task = await executor.submit_task(run_id="run-timeout-1", message="timeout me", blocking=False)
        assert task.status in {A2ATaskState.SUBMITTED, A2ATaskState.WORKING}

        deadline = asyncio.get_event_loop().time() + 3
        latest = None
        while asyncio.get_event_loop().time() < deadline:
            latest = await executor.get_task(task.id)
            if latest and latest.status in {A2ATaskState.FAILED, A2ATaskState.COMPLETED, A2ATaskState.CANCELED}:
                break
            await asyncio.sleep(0.1)

        assert latest is not None
        assert latest.status == A2ATaskState.FAILED
        assert latest.error and "TASK_TIMEOUT" in latest.error
        assert task.id not in executor.get_active_tasks()


@pytest.mark.asyncio
async def test_orchestrator_path_skips_sdk_client_initialization() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "a2a-orch.db"
        store = A2ATaskStore(memory=MemoryStore(db_path=db_path))
        config = SimpleNamespace(a2a=SimpleNamespace(task_timeout_seconds=5))
        executor = JarvisAgentExecutor(
            config=config,
            task_store=store,
            session_manager=_FailingSessionManager(),
            orchestrator=_FastOrchestrator(),
        )

        task = await executor.submit_task(run_id="run-fast-1", message="fast task", blocking=True)
        assert task.status == A2ATaskState.COMPLETED
        assert task.result == "ok"


@pytest.mark.asyncio
async def test_submit_task_is_idempotent_by_run_id() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "a2a-idempotent.db"
        store = A2ATaskStore(memory=MemoryStore(db_path=db_path))
        config = SimpleNamespace(a2a=SimpleNamespace(task_timeout_seconds=5))
        orchestrator = _CountingOrchestrator()
        executor = JarvisAgentExecutor(
            config=config,
            task_store=store,
            session_manager=_FailingSessionManager(),
            orchestrator=orchestrator,
        )

        first = await executor.submit_task(run_id="run-dedupe-1", message="dedupe me", blocking=True)
        second = await executor.submit_task(run_id="run-dedupe-1", message="dedupe me", blocking=True)

        assert first.id == second.id
        assert first.run_id == second.run_id == "run-dedupe-1"
        assert orchestrator.calls == 1
