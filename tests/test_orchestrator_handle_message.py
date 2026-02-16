import asyncio

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


async def _run(coro):
    return await coro


def test_handle_message_completed():
    orch = object.__new__(JarvisOrchestrator)
    orch.project_path = "/tmp/project"
    orch.events = _DummyEvents()
    orch.memory = _DummyMemory()
    orch._ingest_research_urls_from_text = lambda *_args, **_kwargs: None

    async def _chat(_msg):
        return {"status": "completed", "reply": "Hello there"}

    orch.chat = _chat

    result = asyncio.run(_run(orch.handle_message("hi", origin="ws:test")))
    assert result["status"] == "completed"
    assert result["route"] == "chat"
    assert result["reply"] == "Hello there"
    assert result["decision"]["mode"] == "chat"
    assert result["decision"]["confidence"] == 1.0
    assert orch.memory.calls[-1][0] == "ws:test"


def test_handle_message_failed_when_empty_reply():
    orch = object.__new__(JarvisOrchestrator)
    orch.project_path = "/tmp/project"
    orch.events = _DummyEvents()
    orch.memory = _DummyMemory()
    orch._ingest_research_urls_from_text = lambda *_args, **_kwargs: None

    async def _chat(_msg):
        return {"status": "completed", "reply": ""}

    orch.chat = _chat

    result = asyncio.run(_run(orch.handle_message("hi", origin="slack:test")))
    assert result["status"] == "failed"
    assert result["decision"]["confidence"] == 0.0

