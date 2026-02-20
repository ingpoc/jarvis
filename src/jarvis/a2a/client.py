"""A2A client helpers for external agent integrations (for example OpenClaw)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

from jarvis.config import JARVIS_A2A_TOKEN


TERMINAL_TASK_STATES = {
    "completed",
    "failed",
    "canceled",
    "rejected",
}


class A2AClientError(RuntimeError):
    """Raised when A2A calls fail or return protocol errors."""


class JarvisA2AClient:
    """Small JSON-RPC client for Jarvis A2A server."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        token_path: str | Path | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("JARVIS_A2A_URL") or "http://127.0.0.1:9848").rstrip("/")
        self._token = token
        self._token_path = Path(token_path) if token_path else None
        self.timeout_seconds = timeout_seconds

    def health(self) -> dict[str, Any]:
        return self._http_get_json("/health", require_auth=False)

    def agent_card(self) -> dict[str, Any]:
        return self._http_get_json("/.well-known/agent-card.json", require_auth=False)

    def send_message(
        self,
        message: str,
        *,
        blocking: bool = False,
        context_id: str | None = None,
        resume_session_id: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "message": message,
            "blocking": blocking,
        }
        if context_id:
            params["contextId"] = context_id
        if resume_session_id:
            params["resumeSessionId"] = resume_session_id
        return self._jsonrpc("message/send", params, request_id=request_id)

    def stream_message(
        self,
        *,
        task_id: str | None = None,
        message: str | None = None,
        context_id: str | None = None,
        resume_session_id: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if not task_id and not message:
            raise A2AClientError("stream_message requires either task_id or message")
        params: dict[str, Any] = {}
        if task_id:
            params["taskId"] = task_id
        if message:
            params["message"] = message
        if context_id:
            params["contextId"] = context_id
        if resume_session_id:
            params["resumeSessionId"] = resume_session_id
        return self._jsonrpc("message/stream", params, request_id=request_id)

    def get_task(self, task_id: str, *, request_id: str | None = None) -> dict[str, Any]:
        return self._jsonrpc("tasks/get", {"taskId": task_id}, request_id=request_id)

    def cancel_task(self, task_id: str, *, request_id: str | None = None) -> dict[str, Any]:
        return self._jsonrpc("tasks/cancel", {"taskId": task_id}, request_id=request_id)

    def wait_for_task(
        self,
        task_id: str,
        *,
        timeout_seconds: float = 120.0,
        poll_interval_seconds: float = 1.0,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        last_result: dict[str, Any] | None = None

        while time.monotonic() < deadline:
            task = self.get_task(task_id)
            last_result = task
            status = str(task.get("status", "")).strip().lower()
            if status in TERMINAL_TASK_STATES:
                return task
            time.sleep(poll_interval_seconds)

        if last_result is None:
            raise A2AClientError(f"Task {task_id} did not return any status before timeout")
        raise A2AClientError(
            f"Task {task_id} did not complete in {timeout_seconds:.1f}s "
            f"(last_status={last_result.get('status')})"
        )

    def _resolve_token(self) -> str:
        if self._token:
            return self._token.strip()

        env_token = os.environ.get("JARVIS_A2A_TOKEN")
        if env_token:
            return env_token.strip()

        env_token_path = os.environ.get("JARVIS_A2A_TOKEN_PATH")
        token_path = self._token_path
        if token_path is None and env_token_path:
            token_path = Path(env_token_path)
        if token_path is None:
            token_path = JARVIS_A2A_TOKEN

        if token_path.exists():
            token = token_path.read_text().strip()
            if token:
                return token

        raise A2AClientError(
            "Missing A2A token. Set JARVIS_A2A_TOKEN or provide token_path "
            f"(default: {JARVIS_A2A_TOKEN})."
        )

    def _auth_headers(self, require_auth: bool) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if require_auth:
            headers["Authorization"] = f"Bearer {self._resolve_token()}"
        return headers

    def _build_url(self, path: str) -> str:
        clean = path if path.startswith("/") else f"/{path}"
        return urllib.parse.urljoin(f"{self.base_url}/", clean.lstrip("/"))

    def _http_get_json(self, path: str, *, require_auth: bool) -> dict[str, Any]:
        req = urllib.request.Request(
            self._build_url(path),
            method="GET",
            headers=self._auth_headers(require_auth),
        )
        return self._open_json(req)

    def _jsonrpc(
        self,
        method: str,
        params: dict[str, Any],
        *,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": request_id or f"jarvis-a2a-{uuid4().hex[:10]}",
            "method": method,
            "params": params,
        }
        req = urllib.request.Request(
            self._build_url("/"),
            method="POST",
            headers=self._auth_headers(require_auth=True),
            data=json.dumps(payload).encode("utf-8"),
        )
        body = self._open_json(req)
        if "error" in body:
            error = body.get("error") or {}
            code = error.get("code")
            message = error.get("message", "Unknown JSON-RPC error")
            raise A2AClientError(f"{method} failed (code={code}): {message}")
        result = body.get("result")
        if not isinstance(result, dict):
            raise A2AClientError(f"{method} returned invalid response payload")
        return result

    def _open_json(self, req: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            detail = body
            try:
                parsed = json.loads(body)
                detail = json.dumps(parsed)
            except json.JSONDecodeError:
                pass
            raise A2AClientError(f"HTTP {exc.code} for {req.full_url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise A2AClientError(f"Network error for {req.full_url}: {exc}") from exc

        if not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            raise A2AClientError(f"Unexpected JSON type from {req.full_url}: {type(parsed).__name__}")
        except json.JSONDecodeError as exc:
            raise A2AClientError(f"Invalid JSON from {req.full_url}: {raw[:240]}") from exc
