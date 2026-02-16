import asyncio

from jarvis.ws_server import JarvisWSServer


class _DummyEvents:
    def __init__(self):
        self.calls = []

    def emit(self, event_type, summary, **kwargs):
        self.calls.append((event_type, summary, kwargs))


class _FastOrchestrator:
    async def handle_message(self, message, origin):
        return {
            "status": "completed",
            "route": "chat",
            "reply": f"echo:{message}:{origin}",
            "decision": {"mode": "chat", "confidence": 1.0, "reason": "direct_chat_model"},
        }


class _SlowOrchestrator:
    async def handle_message(self, message, origin):
        await asyncio.sleep(0.03)
        return {
            "status": "completed",
            "route": "chat",
            "reply": f"done:{message}:{origin}",
            "decision": {"mode": "chat", "confidence": 1.0, "reason": "direct_chat_model"},
        }


def test_ws_chat_returns_sync_when_fast(monkeypatch):
    monkeypatch.setenv("JARVIS_WS_CHAT_SYNC_TIMEOUT_SECS", "0.5")
    ws = object.__new__(JarvisWSServer)
    ws._events = _DummyEvents()
    ws._orchestrator = _FastOrchestrator()
    ws._background_tasks = set()

    result = asyncio.run(
        ws._run_chat_nonblocking(
            message="hi",
            origin="ws:test",
            request_id="req-1",
            action="chat",
        )
    )
    assert result["status"] == "completed"
    assert result["reply"].startswith("echo:hi")


def test_ws_chat_queues_when_slow(monkeypatch):
    monkeypatch.setenv("JARVIS_WS_CHAT_SYNC_TIMEOUT_SECS", "0.001")
    ws = object.__new__(JarvisWSServer)
    ws._events = _DummyEvents()
    ws._orchestrator = _SlowOrchestrator()
    ws._background_tasks = set()

    async def _run():
        queued = await ws._run_chat_nonblocking(
            message="hi",
            origin="ws:test",
            request_id="req-2",
            action="message",
        )
        await asyncio.sleep(0.06)
        return queued

    result = asyncio.run(_run())
    assert result["status"] == "queued"
    assert result["decision"]["reason"] == "async_queued"
    assert any(call[0] == "chat_async_complete" for call in ws._events.calls)
