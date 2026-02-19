import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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


def _make_orch():
    """Create a minimal orchestrator with stubs for chat() dependencies."""
    orch = object.__new__(JarvisOrchestrator)
    orch.project_path = "/tmp/project"
    orch.config = SimpleNamespace(
        models=SimpleNamespace(
            executor="claude-sonnet-4-5-20250929",
            provider_type="anthropic",
        )
    )
    orch.events = _DummyEvents()
    orch.memory = _DummyMemory()
    orch._ingest_research_urls_from_text = lambda *_args, **_kwargs: None
    orch._chat_lock = asyncio.Lock()
    orch._chat_client = None
    return orch


def _make_result_message(is_error=False, total_cost_usd=0.0, num_turns=1):
    from claude_agent_sdk import ResultMessage
    return ResultMessage(
        subtype="result",
        duration_ms=100,
        duration_api_ms=80,
        is_error=is_error,
        num_turns=num_turns,
        session_id="test-session",
        total_cost_usd=total_cost_usd,
    )


def test_handle_message_completed():
    """handle_message delegates to chat and returns backward-compat shape."""
    orch = _make_orch()

    mock_client = AsyncMock()
    mock_client.query = AsyncMock()

    async def _fake_receive():
        from claude_agent_sdk import AssistantMessage, TextBlock
        yield AssistantMessage(content=[TextBlock(text="Hello there")], model="test")
        yield _make_result_message(total_cost_usd=0.01)

    mock_client.receive_response = _fake_receive
    orch._ensure_chat_client = AsyncMock(return_value=mock_client)
    orch.budget = MagicMock()
    orch.budget.record_cost = MagicMock()

    with patch("jarvis.orchestrator.core.ensure_project_jarvis_file"):
        with patch("jarvis.orchestrator.core.append_project_turn"):
            result = asyncio.run(_run(orch.handle_message("hi", origin="ws:test")))

    assert result["status"] == "completed"
    assert result["route"] == "chat"
    assert result["reply"] == "Hello there"
    assert result["decision"]["mode"] == "chat"
    assert result["decision"]["confidence"] == 1.0
    assert orch.memory.calls[-1][0] == "ws:test"


def test_handle_message_failed_when_empty_reply():
    """Empty reply from model should result in failed status."""
    orch = _make_orch()

    mock_client = AsyncMock()
    mock_client.query = AsyncMock()

    async def _fake_receive():
        yield _make_result_message()

    mock_client.receive_response = _fake_receive
    orch._ensure_chat_client = AsyncMock(return_value=mock_client)
    orch.budget = MagicMock()
    orch.budget.record_cost = MagicMock()
    orch._reset_chat_client = AsyncMock()

    with patch("jarvis.orchestrator.core.ensure_project_jarvis_file"):
        with patch("jarvis.orchestrator.core.append_project_turn"):
            result = asyncio.run(_run(orch.handle_message("hi", origin="slack:test")))

    assert result["status"] == "failed"
    assert result["decision"]["confidence"] == 0.0
