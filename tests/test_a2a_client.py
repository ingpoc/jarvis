import io
import json
import urllib.error
from pathlib import Path

import pytest

from jarvis.a2a.client import A2AClientError, JarvisA2AClient


class _Response:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def test_send_message_adds_auth_header_and_payload(tmp_path, monkeypatch):
    token_path = tmp_path / "a2a_token"
    token_path.write_text("abc123")
    captured = {}

    def _fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["auth"] = req.get_header("Authorization")
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _Response(
            {
                "jsonrpc": "2.0",
                "result": {"taskId": "a2a-1", "status": "submitted"},
                "id": "x",
            }
        )

    monkeypatch.setattr("jarvis.a2a.client.urllib.request.urlopen", _fake_urlopen)
    client = JarvisA2AClient(base_url="http://localhost:9848", token_path=token_path)
    result = client.send_message("ping", blocking=False, context_id="ctx-1")

    assert result["taskId"] == "a2a-1"
    assert captured["url"] == "http://localhost:9848/"
    assert captured["auth"] == "Bearer abc123"
    assert captured["body"]["method"] == "message/send"
    assert captured["body"]["params"]["message"] == "ping"
    assert captured["body"]["params"]["contextId"] == "ctx-1"


def test_jsonrpc_error_payload_raises_client_error(tmp_path, monkeypatch):
    token_path = tmp_path / "a2a_token"
    token_path.write_text("abc123")

    def _fake_urlopen(req, timeout=0):
        return _Response(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "Missing parameter"},
                "id": "x",
            }
        )

    monkeypatch.setattr("jarvis.a2a.client.urllib.request.urlopen", _fake_urlopen)
    client = JarvisA2AClient(base_url="http://localhost:9848", token_path=token_path)

    with pytest.raises(A2AClientError, match="message/send failed"):
        client.send_message("ping")


def test_wait_for_task_returns_terminal_result(monkeypatch):
    statuses = [
        {"taskId": "a2a-xyz", "status": "working"},
        {"taskId": "a2a-xyz", "status": "completed", "result": "pong"},
    ]
    client = JarvisA2AClient(base_url="http://localhost:9848", token="token-1")
    monkeypatch.setattr(client, "get_task", lambda task_id: statuses.pop(0))
    monkeypatch.setattr("jarvis.a2a.client.time.sleep", lambda _: None)

    result = client.wait_for_task("a2a-xyz", timeout_seconds=5.0, poll_interval_seconds=0.01)
    assert result["status"] == "completed"
    assert result["result"] == "pong"


def test_http_error_raises_with_response_body(tmp_path, monkeypatch):
    token_path = tmp_path / "a2a_token"
    token_path.write_text("abc123")

    body = json.dumps({"detail": {"code": "invalid_token"}}).encode("utf-8")
    err = urllib.error.HTTPError(
        url="http://localhost:9848/",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=io.BytesIO(body),
    )

    def _fake_urlopen(req, timeout=0):
        raise err

    monkeypatch.setattr("jarvis.a2a.client.urllib.request.urlopen", _fake_urlopen)
    client = JarvisA2AClient(base_url="http://localhost:9848", token_path=token_path)

    with pytest.raises(A2AClientError, match="HTTP 401"):
        client.send_message("ping")


def test_send_message_requires_token_when_missing(tmp_path):
    missing = tmp_path / "missing_token_file"
    assert not Path(missing).exists()
    client = JarvisA2AClient(
        base_url="http://localhost:9848",
        token=None,
        token_path=missing,
    )
    with pytest.raises(A2AClientError, match="Missing A2A token"):
        client.send_message("ping")
