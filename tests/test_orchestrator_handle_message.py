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
        self.calls = []

    def save_channel_turn(self, origin, project_path, user_message, reply):
        self.calls.append((origin, project_path, user_message, reply))


class _DummyResearchMemory:
    def __init__(self):
        self.calls = []

    def add_research_sources(self, urls, source):
        self.calls.append((urls, source))
        return len(urls)


async def _run(coro):
    return await coro


def _make_orch():
    orch = object.__new__(JarvisOrchestrator)
    orch.project_path = "/tmp/project"
    orch.config = SimpleNamespace(
        models=SimpleNamespace(
            executor="opencode/glm-5-free",
            provider_type="opencode",
        )
    )
    orch.events = _DummyEvents()
    orch.memory = _DummyMemory()
    orch._ingest_research_urls_from_text = lambda *_args, **_kwargs: None
    orch._chat_lock = asyncio.Lock()
    orch._chat_client = None
    orch._chat_opencode = AsyncMock(
        return_value={
            "status": "completed",
            "route": "chat",
            "reply": "opencode-ok",
            "decision": {"mode": "chat", "confidence": 1.0, "reason": "opencode"},
        }
    )
    return orch


def test_handle_message_routes_to_opencode_chat():
    orch = _make_orch()

    with patch("jarvis.orchestrator.core.ensure_project_jarvis_file"):
        with patch("jarvis.orchestrator.core.append_project_turn"):
            result = asyncio.run(_run(orch.handle_message("hi", origin="ws:test")))

    assert result["status"] == "completed"
    assert result["reply"] == "opencode-ok"
    orch._chat_opencode.assert_awaited_once_with("hi", "opencode/glm-5-free")


def test_ingest_research_urls_noop_when_memory_lacks_api():
    orch = object.__new__(JarvisOrchestrator)
    orch.memory = _DummyMemory()
    orch.events = _DummyEvents()

    added = JarvisOrchestrator._ingest_research_urls_from_text(
        orch,
        "Check http://127.0.0.1:4173 and https://example.com/docs",
        source="task:a2a",
    )

    assert added == 0
    assert orch.events.calls == []


def test_ingest_research_urls_emits_event_when_supported():
    orch = object.__new__(JarvisOrchestrator)
    orch.memory = _DummyResearchMemory()
    orch.events = _DummyEvents()

    added = JarvisOrchestrator._ingest_research_urls_from_text(
        orch,
        "Check http://127.0.0.1:4173 and https://example.com/docs",
        source="task:a2a",
    )

    assert added == 2
    assert len(orch.memory.calls) == 1
    assert len(orch.events.calls) == 1


def test_resolve_task_provider_for_origin_forces_opencode():
    orch = object.__new__(JarvisOrchestrator)

    provider, model = JarvisOrchestrator._resolve_task_provider_for_origin(
        orch,
        origin="a2a",
        provider_type="legacy",
        model_id="legacy/model",
    )

    assert provider == "opencode"
    assert model.startswith("opencode/")


def test_select_a2a_workflow_is_runtime_autonomy():
    orch = object.__new__(JarvisOrchestrator)
    mode, reason = JarvisOrchestrator._select_a2a_workflow(
        orch,
        origin="a2a",
        task_description="Design and implement a feature",
    )
    assert mode == "runtime"
    assert reason == "runtime_autonomy"
