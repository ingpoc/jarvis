import pytest

from jarvis.opencode_client import OpenCodeClient


def test_normalize_model_variants() -> None:
    client = OpenCodeClient("http://127.0.0.1:4096", auto_start=False)
    assert client._normalize_model("opencode/default") is None
    assert client._normalize_model("opencode:coder") == {
        "providerID": "opencode",
        "modelID": "coder",
    }
    assert client._normalize_model("opencode/minimax-m2.5-free") == {
        "providerID": "opencode",
        "modelID": "minimax-m2.5-free",
    }
    assert client._normalize_model("opencode/zen/minimax/m2.5-free") == {
        "providerID": "zen",
        "modelID": "minimax/m2.5-free",
    }
    assert client._normalize_model("opencode") is None
    assert client._normalize_model("opencode-default") is None
    assert client._normalize_model("openai/gpt-5.2") == {
        "providerID": "openai",
        "modelID": "gpt-5.2",
    }


def test_extract_text_prefers_last_text_part() -> None:
    client = OpenCodeClient("http://127.0.0.1:4096", auto_start=False)
    payload = {
        "parts": [
            {"type": "reasoning", "text": "hidden"},
            {"type": "text", "text": "first"},
            {"type": "tool", "name": "bash"},
            {"type": "text", "text": "final answer"},
        ]
    }
    assert client._extract_text_from_parts(payload) == "final answer"


def test_session_permission_rules_include_bash_allow() -> None:
    client = OpenCodeClient("http://127.0.0.1:4096", auto_start=False)
    rules = client._session_permission_rules()
    assert any(
        rule.get("permission") == "bash"
        and rule.get("pattern") == "*"
        and rule.get("action") == "allow"
        for rule in rules
    )


@pytest.mark.asyncio
async def test_run_task_offloads_network_calls_with_to_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenCodeClient("http://127.0.0.1:4096", auto_start=False)
    to_thread_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fake_to_thread(func, *args):  # noqa: ANN001
        to_thread_calls.append((getattr(func, "__name__", str(func)), args))
        return func(*args)

    async def fake_ensure_available() -> None:
        return None

    def fake_request(
        method: str,
        path: str,
        payload: dict | None = None,
        timeout: int = 30,
    ) -> dict:
        if method == "POST" and path == "/session?directory=%2Ftmp%2Fproj":
            assert isinstance(payload, dict)
            assert payload.get("title") == "Jarvis delegated task"
            rules = payload.get("permission")
            assert isinstance(rules, list) and len(rules) > 0
            assert any(
                isinstance(rule, dict)
                and rule.get("permission") == "bash"
                and rule.get("pattern") == "*"
                and rule.get("action") == "allow"
                for rule in rules
            )
            assert timeout == 10
            return {"id": "sess-123"}
        if method == "POST" and path == "/session/sess-123/message?directory=%2Ftmp%2Fproj":
            assert payload == {"parts": [{"type": "text", "text": "ping"}]}
            assert timeout == 180
            return {"parts": [{"type": "text", "text": "pong"}]}
        raise AssertionError(f"Unexpected request: method={method} path={path}")

    monkeypatch.setattr("jarvis.opencode_client.asyncio.to_thread", fake_to_thread)
    monkeypatch.setattr(client, "ensure_available", fake_ensure_available)
    monkeypatch.setattr(client, "_request", fake_request)

    result = await client.run_task("ping", cwd="/tmp/proj")

    assert result.session_id == "sess-123"
    assert result.text == "pong"
    assert len(to_thread_calls) == 2
    assert to_thread_calls[0][0] == "fake_request"
    assert to_thread_calls[1][0] == "fake_request"


@pytest.mark.asyncio
async def test_run_task_resumes_existing_session_without_creating_new_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenCodeClient("http://127.0.0.1:4096", auto_start=False)
    to_thread_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fake_to_thread(func, *args):  # noqa: ANN001
        to_thread_calls.append((getattr(func, "__name__", str(func)), args))
        return func(*args)

    async def fake_ensure_available() -> None:
        return None

    def fake_request(
        method: str,
        path: str,
        payload: dict | None = None,
        timeout: int = 30,
    ) -> dict:
        if method == "POST" and path == "/session/sess-existing/message?directory=%2Ftmp%2Fproj":
            assert payload == {"parts": [{"type": "text", "text": "follow-up"}]}
            assert timeout == 180
            return {"parts": [{"type": "text", "text": "resumed"}]}
        raise AssertionError(f"Unexpected request: method={method} path={path}")

    monkeypatch.setattr("jarvis.opencode_client.asyncio.to_thread", fake_to_thread)
    monkeypatch.setattr(client, "ensure_available", fake_ensure_available)
    monkeypatch.setattr(client, "_request", fake_request)

    result = await client.run_task("follow-up", cwd="/tmp/proj", resume_session_id="sess-existing")

    assert result.session_id == "sess-existing"
    assert result.text == "resumed"
    assert len(to_thread_calls) == 1
