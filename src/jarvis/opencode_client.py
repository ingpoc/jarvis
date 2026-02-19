"""OpenCode server client for non-interactive Jarvis execution."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class OpenCodeRunResult:
    """Normalized OpenCode run result."""

    session_id: str
    text: str
    raw: dict[str, Any]


class OpenCodeClientError(RuntimeError):
    """OpenCode client error."""


class OpenCodeClient:
    """Minimal HTTP client for `opencode serve`."""

    def __init__(
        self,
        base_url: str,
        username: str = "opencode",
        password: str | None = None,
        auto_start: bool = True,
        startup_timeout_seconds: int = 15,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password or ""
        self.auto_start = auto_start
        self.startup_timeout_seconds = startup_timeout_seconds
        self._process: subprocess.Popen | None = None

    def _auth_headers(self) -> dict[str, str]:
        if not self.password:
            return {}
        token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = None
        headers = {"Content-Type": "application/json", **self._auth_headers()}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url=url, method=method, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                raw = res.read().decode("utf-8").strip()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OpenCodeClientError(f"OpenCode HTTP {exc.code} on {path}: {detail}") from exc
        except Exception as exc:  # noqa: BLE001
            raise OpenCodeClientError(f"OpenCode request failed on {path}: {exc}") from exc

        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OpenCodeClientError(f"OpenCode returned non-JSON response for {path}: {raw[:300]}") from exc
        if isinstance(parsed, dict):
            return parsed
        return {"data": parsed}

    def is_available(self) -> bool:
        try:
            health = self._request("GET", "/global/health", payload=None, timeout=3)
            return bool(health.get("healthy", False))
        except Exception:  # noqa: BLE001
            return False

    def _start_server(self) -> None:
        parsed = urllib.parse.urlsplit(self.base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 4096
        binary = os.environ.get("JARVIS_OPENCODE_BIN", "opencode")
        env = os.environ.copy()
        if self.password and "OPENCODE_SERVER_PASSWORD" not in env:
            env["OPENCODE_SERVER_PASSWORD"] = self.password
            env["OPENCODE_SERVER_USERNAME"] = self.username

        self._process = subprocess.Popen(  # noqa: S603
            [binary, "serve", "--hostname", host, "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

    async def ensure_available(self) -> None:
        if self.is_available():
            return

        if not self.auto_start:
            raise OpenCodeClientError(
                f"OpenCode server not reachable at {self.base_url}. "
                "Start it with `opencode serve` or set JARVIS_OPENCODE_AUTOSTART=1."
            )

        if not self._process or self._process.poll() is not None:
            self._start_server()

        deadline = time.time() + max(3, self.startup_timeout_seconds)
        while time.time() < deadline:
            if self.is_available():
                return
            await asyncio.sleep(0.5)

        raise OpenCodeClientError(
            f"OpenCode server did not become ready within {self.startup_timeout_seconds}s at {self.base_url}."
        )

    def _extract_text_from_parts(self, payload: dict[str, Any]) -> str:
        parts = payload.get("parts", [])
        if isinstance(parts, list):
            for part in reversed(parts):
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        return text.strip()
        info = payload.get("info", {})
        if isinstance(info, dict):
            message = info.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        return ""

    def _normalize_model(self, model_id: str | None) -> dict[str, str] | None:
        if not model_id:
            return None
        model = str(model_id).strip()
        if model.startswith("opencode/"):
            model = model.split("/", 1)[1] or ""
        if model.startswith("opencode:"):
            model = model.split(":", 1)[1] or ""
        if model in {"opencode", "opencode-default"}:
            return None
        if model in {"", "default"}:
            return None
        if "/" in model:
            provider_id, model_name = model.split("/", 1)
            provider_id = provider_id.strip()
            model_name = model_name.strip()
            if provider_id and model_name:
                return {"providerID": provider_id, "modelID": model_name}
        return {"providerID": "opencode", "modelID": model}

    async def run_task(
        self,
        message: str,
        *,
        model_id: str | None = None,
        agent: str | None = None,
        timeout_seconds: int = 180,
    ) -> OpenCodeRunResult:
        await self.ensure_available()

        session = self._request("POST", "/session", {"title": "Jarvis delegated task"}, timeout=10)
        session_id = str(session.get("id") or session.get("sessionID") or "").strip()
        if not session_id:
            raise OpenCodeClientError(f"OpenCode did not return session id: {session}")

        body: dict[str, Any] = {
            "parts": [{"type": "text", "text": message}],
        }
        normalized_model = self._normalize_model(model_id)
        if normalized_model:
            body["model"] = normalized_model
        if agent:
            body["agent"] = agent

        response = self._request(
            "POST",
            f"/session/{session_id}/message",
            body,
            timeout=max(30, timeout_seconds),
        )
        text = self._extract_text_from_parts(response)
        if not text:
            # Fallback for unexpected payload shape.
            text = json.dumps(response, default=str)[:5000]

        return OpenCodeRunResult(session_id=session_id, text=text, raw=response)


_opencode_client: OpenCodeClient | None = None


def get_opencode_client() -> OpenCodeClient:
    """Get singleton OpenCode client using environment configuration."""
    global _opencode_client
    if _opencode_client is None:
        base_url = os.environ.get("JARVIS_OPENCODE_BASE_URL", "http://127.0.0.1:4096")
        username = os.environ.get("JARVIS_OPENCODE_USERNAME", "opencode")
        password = os.environ.get("JARVIS_OPENCODE_PASSWORD", "")
        auto_start = os.environ.get("JARVIS_OPENCODE_AUTOSTART", "1").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        startup_timeout = int(os.environ.get("JARVIS_OPENCODE_STARTUP_TIMEOUT_SECS", "15"))
        _opencode_client = OpenCodeClient(
            base_url=base_url,
            username=username,
            password=password,
            auto_start=auto_start,
            startup_timeout_seconds=startup_timeout,
        )
    return _opencode_client
