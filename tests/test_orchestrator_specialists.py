import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jarvis.orchestrator.core import (
    CODER_EXPERT_AGENT,
    JarvisOrchestrator,
)


class _DigestEvents:
    def __init__(self):
        self.calls = []

    def emit(self, event_type, summary, **kwargs):
        self.calls.append((event_type, summary, kwargs))


class _DigestMemory:
    def __init__(self):
        self.saved = []
        self.threads = []

    def has_mail_digest_run(self, _run_key):
        return False

    def get_mail_digest_runs(self, **_kwargs):
        return []

    def save_mail_digest_run(self, **kwargs):
        self.saved.append(kwargs)

    def upsert_mail_thread_state(self, **kwargs):
        self.threads.append(kwargs)


def _make_digest_orch(provider_type: str, model_id: str) -> JarvisOrchestrator:
    orch = object.__new__(JarvisOrchestrator)
    orch.project_path = "/tmp/project"
    orch.events = _DigestEvents()
    orch.memory = _DigestMemory()
    orch.budget = SimpleNamespace(record_cost=lambda *_args, **_kwargs: None)
    orch._has_mail_mcp_server = lambda: True
    orch._has_mail_tool_allowlist = lambda: True
    orch.config = SimpleNamespace(
        mail=SimpleNamespace(
            enabled=True,
            digest_enabled=True,
            digest_time_local="08:00",
            timezone="UTC",
            window_hours=24,
            include_weekends=True,
        ),
        models=SimpleNamespace(
            executor=model_id,
            provider_type=provider_type,
        ),
    )
    return orch


def test_update_mail_schedule_persists_config():
    orch = object.__new__(JarvisOrchestrator)
    orch.config = SimpleNamespace(
        mail=SimpleNamespace(
            enabled=False,
            digest_enabled=False,
            digest_time_local="08:00",
            timezone="UTC",
            window_hours=24,
            include_weekends=True,
        ),
        save=MagicMock(),
    )

    result = orch.update_mail_schedule(
        enabled=True,
        time_local="07:30",
        timezone="America/Chicago",
        window_hours=12,
        include_weekends=False,
    )

    assert result["enabled"] is True
    assert result["digest_enabled"] is True
    assert result["digest_time_local"] == "07:30"
    assert result["timezone"] == "America/Chicago"
    assert result["window_hours"] == 12
    assert result["include_weekends"] is False
    orch.config.save.assert_called_once()


def test_run_mail_digest_fails_without_mail_mcp():
    orch = object.__new__(JarvisOrchestrator)
    orch._has_mail_mcp_server = lambda: False

    result = asyncio.run(orch.run_mail_digest())
    assert result["status"] == "failed"
    assert "mail MCP" in result["error"]


def test_coder_gate_requires_verification_commands():
    orch = object.__new__(JarvisOrchestrator)
    result = {"status": "completed", "output": "done"}

    orch._enforce_coder_completion_gate(
        specialist=CODER_EXPERT_AGENT,
        task_description="fix the failing tests in parser",
        tool_calls=[],
        result=result,
    )
    assert result["status"] == "failed"
    assert "Quality gate failed" in result["output"]


def test_mail_digest_mode_prefers_local_for_foundation(monkeypatch):
    orch = object.__new__(JarvisOrchestrator)
    orch._effective_provider_type = lambda: "foundation"
    monkeypatch.delenv("JARVIS_MAIL_DIGEST_MODE", raising=False)
    assert orch._mail_digest_mode() == "local"


def test_mail_digest_mode_prefers_sdk_for_non_foundation(monkeypatch):
    orch = object.__new__(JarvisOrchestrator)
    orch._effective_provider_type = lambda: "anthropic"
    monkeypatch.delenv("JARVIS_MAIL_DIGEST_MODE", raising=False)
    assert orch._mail_digest_mode() == "sdk"


def test_run_mail_digest_executes_local_pipeline_for_foundation(monkeypatch):
    orch = _make_digest_orch("foundation", "foundation-models")

    payload = {
        "summary": "Foundation digest",
        "urgent": [{"thread_id": "t-1", "subject": "Security alert", "next_action": "Respond"}],
        "reply_today": [],
        "waiting_on_them": [],
        "fyi": [],
        "top_3_now": [{"thread_id": "t-1", "subject": "Security alert"}],
    }

    async def _fake_build_digest(self, *, window_hours, local_model_id):
        assert window_hours == 24
        assert local_model_id is None
        return payload, "local digest"

    monkeypatch.delenv("JARVIS_MAIL_DIGEST_MODE", raising=False)
    with patch(
        "jarvis.orchestrator.core.ZapierMailClient.from_env",
        return_value=object(),
    ):
        with patch(
            "jarvis.orchestrator.core.LocalMailDigestService.build_digest",
            _fake_build_digest,
        ):
            result = asyncio.run(orch.run_mail_digest(force=True))

    assert result["status"] == "completed"
    assert result["mode"] == "local"
    assert result["digest"]["raw_summary"] == "Foundation digest"
    assert len(orch.memory.saved) == 1


def test_run_mail_digest_executes_sdk_mail_chief_for_lmstudio(monkeypatch):
    orch = _make_digest_orch("lmstudio", "openai/gpt-oss-20b")
    orch._build_options = lambda: SimpleNamespace(tools=["x"], allowed_tools=[], mcp_servers={"zapier": {}})
    orch._build_mail_tool_allowlist = lambda: ["mcp__zapier__gmail_find_email"]
    orch._build_mail_mcp_servers = lambda: {"zapier": {"type": "streamable-http"}}

    class _FakeZapierClient:
        async def fetch_recent_messages(self, *, window_hours, limit=30):
            assert window_hours == 24
            assert limit == 30
            return [
                SimpleNamespace(
                    sender="alice@example.com",
                    subject="Need confirmation today",
                    received_at="2026-02-19T09:00:00Z",
                    snippet="Can you confirm?",
                    thread_id="t-123",
                    message_id="m-123",
                )
            ]

    class _FakeSDKClient:
        seen = []

        def __init__(self, options=None):
            self.options = options
            _FakeSDKClient.seen.append(options)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def query(self, _prompt):
            return None

        async def receive_response(self):
            from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

            yield AssistantMessage(
                content=[
                    TextBlock(
                        text=(
                            '{"summary":"LM digest","urgent":[],"reply_today":[],"waiting_on_them":[],'  # noqa: E501
                            '"fyi":[],"top_3_now":[]}'
                        )
                    )
                ],
                model="openai/gpt-oss-20b",
            )
            yield ResultMessage(
                subtype="result",
                duration_ms=10,
                duration_api_ms=8,
                is_error=False,
                num_turns=1,
                session_id="sdk-test-1",
                total_cost_usd=0.0,
            )

    monkeypatch.delenv("JARVIS_MAIL_DIGEST_MODE", raising=False)
    with patch("jarvis.orchestrator.core.ZapierMailClient.from_env", return_value=_FakeZapierClient()):
        with patch("jarvis.orchestrator.core.ClaudeSDKClient", _FakeSDKClient):
            result = asyncio.run(orch.run_mail_digest(force=True))

    assert result["status"] == "completed"
    assert result["mode"] == "sdk"
    assert result["digest"]["raw_summary"] == "LM digest"
    assert len(_FakeSDKClient.seen) == 1
    assert _FakeSDKClient.seen[0].allowed_tools == ["mcp__zapier__gmail_find_email"]
    assert _FakeSDKClient.seen[0].mcp_servers == {"zapier": {"type": "streamable-http"}}
