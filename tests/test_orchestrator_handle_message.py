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


class _DummyResearchMemory:
    def __init__(self):
        self.calls = []

    def add_research_sources(self, urls, source):
        self.calls.append((urls, source))
        return len(urls)


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


def test_handle_message_routes_foundation_to_local_chat():
    orch = _make_orch()
    orch.config.models.executor = "foundation-models"
    orch.config.models.provider_type = "foundation"
    orch._chat_local = AsyncMock(
        return_value={
            "status": "completed",
            "route": "chat",
            "reply": "local-ok",
            "decision": {"mode": "chat", "confidence": 1.0, "reason": "local_model:foundation"},
        }
    )

    with patch("jarvis.orchestrator.core.ensure_project_jarvis_file"):
        with patch("jarvis.orchestrator.core.append_project_turn"):
            result = asyncio.run(_run(orch.handle_message("hi", origin="ws:test")))

    assert result["status"] == "completed"
    assert result["reply"] == "local-ok"
    orch._chat_local.assert_awaited_once_with("hi", "foundation", "foundation-models")


def test_handle_message_routes_opencode_to_opencode_chat():
    orch = _make_orch()
    orch.config.models.executor = "opencode/default"
    orch.config.models.provider_type = "opencode"
    orch._chat_opencode = AsyncMock(
        return_value={
            "status": "completed",
            "route": "chat",
            "reply": "opencode-ok",
            "decision": {"mode": "chat", "confidence": 1.0, "reason": "opencode"},
        }
    )

    with patch("jarvis.orchestrator.core.ensure_project_jarvis_file"):
        with patch("jarvis.orchestrator.core.append_project_turn"):
            result = asyncio.run(_run(orch.handle_message("hi", origin="ws:test")))

    assert result["status"] == "completed"
    assert result["reply"] == "opencode-ok"
    orch._chat_opencode.assert_awaited_once_with("hi", "opencode/default")


def test_handle_message_routes_mail_to_local_digest_for_opencode():
    orch = _make_orch()
    orch.config.models.executor = "opencode/default"
    orch.config.models.provider_type = "opencode"
    orch._chat_opencode = AsyncMock()
    orch._has_mail_mcp_server = lambda: True
    orch._has_mail_tool_allowlist = lambda: True
    orch.run_mail_digest = AsyncMock(
        return_value={
            "status": "completed",
            "digest": {
                "raw_summary": "Inbox summary",
                "urgent": [],
                "reply_today": [],
                "waiting_on_them": [],
                "fyi": [],
                "top_3_now": [],
            },
        }
    )

    with patch("jarvis.orchestrator.core.ensure_project_jarvis_file"):
        with patch("jarvis.orchestrator.core.append_project_turn"):
            result = asyncio.run(_run(orch.handle_message("check my email", origin="ws:test")))

    assert result["status"] == "completed"
    assert result["route"] == "mail"
    assert result["decision"]["reason"] == "mail_digest_local"
    orch.run_mail_digest.assert_awaited_once_with(force=True, origin="chat:ws:test")
    orch._chat_opencode.assert_not_awaited()


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


def test_resolve_task_provider_for_origin_forces_opencode_for_a2a():
    orch = object.__new__(JarvisOrchestrator)

    provider, model = JarvisOrchestrator._resolve_task_provider_for_origin(
        orch,
        origin="a2a",
        provider_type="anthropic",
        model_id="claude-sonnet-4-5-20250929",
    )

    assert provider == "opencode"
    assert model.startswith("opencode/")


def test_resolve_task_provider_for_origin_keeps_provider_for_non_a2a():
    orch = object.__new__(JarvisOrchestrator)

    provider, model = JarvisOrchestrator._resolve_task_provider_for_origin(
        orch,
        origin="ws",
        provider_type="anthropic",
        model_id="claude-sonnet-4-5-20250929",
    )

    assert provider == "anthropic"
    assert model == "claude-sonnet-4-5-20250929"


def test_select_a2a_workflow_single_for_simple_task():
    orch = object.__new__(JarvisOrchestrator)
    mode, reason = JarvisOrchestrator._select_a2a_workflow(
        orch,
        origin="a2a",
        task_description="Reply with exactly PING_OK",
    )
    assert mode == "single"
    assert reason == "simple_default"


def test_select_a2a_workflow_stepwise_for_multi_stage_task():
    orch = object.__new__(JarvisOrchestrator)
    mode, reason = JarvisOrchestrator._select_a2a_workflow(
        orch,
        origin="a2a",
        task_description=(
            "Design and develop a React todo app, start server, run tests, "
            "verify in browser and fix issues"
        ),
    )
    assert mode == "stepwise"
    assert reason.startswith("stepwise_signals:")


def test_select_a2a_workflow_parallel_for_parallel_signals():
    orch = object.__new__(JarvisOrchestrator)
    mode, reason = JarvisOrchestrator._select_a2a_workflow(
        orch,
        origin="a2a",
        task_description=(
            "Use parallel subagent worktrees to implement feature, run tests, "
            "do browser checks, and open pull request"
        ),
    )
    assert mode == "parallel"
    assert reason.startswith("parallel_signals:")


def test_select_a2a_workflow_respects_env_override():
    orch = object.__new__(JarvisOrchestrator)
    with patch.dict("os.environ", {"JARVIS_A2A_WORKFLOW_MODE": "parallel"}, clear=False):
        mode, reason = JarvisOrchestrator._select_a2a_workflow(
            orch,
            origin="a2a",
            task_description="Reply with exactly PING_OK",
        )
    assert mode == "parallel"
    assert reason == "env_override:parallel"
