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


def test_mail_digest_mode_prefers_local_for_opencode(monkeypatch):
    orch = object.__new__(JarvisOrchestrator)
    orch._effective_provider_type = lambda: "opencode"
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
