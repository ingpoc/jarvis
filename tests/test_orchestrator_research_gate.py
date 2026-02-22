import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from jarvis.orchestrator import JarvisOrchestrator


class _DummyEvents:
    def __init__(self):
        self.calls = []

    def emit(self, event_type, summary, **kwargs):
        self.calls.append((event_type, summary, kwargs))


class _DummyMemory:
    def __init__(self):
        self.created = []
        self.transitions = []

    def create_task(self, task_id, description, project_path):
        self.created.append((task_id, description, project_path))

    def transition_task(self, task_id, status, **kwargs):
        self.transitions.append((task_id, status, kwargs))


def _make_orchestrator_for_run_task():
    orch = object.__new__(JarvisOrchestrator)
    orch.project_path = "/tmp/project"
    orch.config = SimpleNamespace(models=SimpleNamespace(executor="opencode/glm-5-free"))
    orch.memory = _DummyMemory()
    orch.events = _DummyEvents()
    orch._ingest_research_urls_from_text = lambda *_args, **_kwargs: None
    orch._effective_provider_type = lambda: "opencode"
    orch._resolve_task_provider_for_origin = (
        lambda **_kwargs: ("opencode", "opencode/glm-5-free")
    )
    orch._run_task_opencode = AsyncMock(
        return_value={
            "task_id": "task-demo",
            "status": "completed",
            "cost_usd": 0.0,
            "turns": 1,
            "session_id": "sess-1",
            "output": "done",
        }
    )
    orch._finalize_task_result = AsyncMock(side_effect=lambda **kwargs: kwargs["result"])
    return orch


def test_run_task_blocks_when_research_verdict_is_skip():
    orch = _make_orchestrator_for_run_task()
    task = (
        "Implement task.\n"
        "[RESEARCH_HANDOFF_JSON]\n"
        '{"researchId":"r-1","proposedVerdict":"skip","confidence":0.9}\n'
        "[/RESEARCH_HANDOFF_JSON]"
    )

    with patch("jarvis.orchestrator.core.ensure_project_jarvis_file"):
        result = asyncio.run(orch.run_task(task, origin="a2a", emit_notifications=False))

    assert result["status"] == "failed"
    assert result["research_gate"]["decision"] == "skip"
    assert result["quality_assessment"]["quality_outcome"] == "failed"
    orch._run_task_opencode.assert_not_called()


def test_run_task_fails_when_quality_block_missing_for_handoff():
    orch = _make_orchestrator_for_run_task()
    task = (
        "Implement task.\n"
        "[RESEARCH_HANDOFF_JSON]\n"
        '{"researchId":"r-2","proposedVerdict":"adopt","confidence":0.9}\n'
        "[/RESEARCH_HANDOFF_JSON]"
    )

    with patch("jarvis.orchestrator.core.ensure_project_jarvis_file"):
        result = asyncio.run(orch.run_task(task, origin="a2a", emit_notifications=False))

    assert result["status"] == "failed"
    assert result["research_gate"]["decision"] == "adopt"
    assert result["quality_assessment"]["quality_outcome"] == "failed"
    assert "Quality contract failed" in result["output"]
    orch._run_task_opencode.assert_awaited_once()
