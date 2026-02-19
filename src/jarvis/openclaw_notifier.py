"""OpenClaw webhook notifier for Jarvis task lifecycle events."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


class OpenClawNotifier:
    """Posts lightweight task events to OpenClaw hooks/wake endpoint."""

    def __init__(self, url: str, token: str, mode: str = "next-heartbeat") -> None:
        self.url = url.rstrip("/")
        self.token = token.strip()
        self.mode = mode if mode in {"now", "next-heartbeat"} else "next-heartbeat"
        self.enabled = bool(self.url and self.token)

    @classmethod
    def from_env(cls) -> "OpenClawNotifier":
        url = os.environ.get("JARVIS_OPENCLAW_HOOK_URL", "").strip()
        token = os.environ.get("JARVIS_OPENCLAW_HOOK_TOKEN", "").strip()
        mode = os.environ.get("JARVIS_OPENCLAW_HOOK_MODE", "next-heartbeat").strip().lower()
        return cls(url=url, token=token, mode=mode)

    def _format_text(self, task_id: str, event_type: str, data: dict[str, Any]) -> str:
        status = str(data.get("status", "")).strip()
        error = str(data.get("error", "")).strip()
        prefix = f"[jarvis-a2a] {event_type} task={task_id}"
        if status:
            prefix += f" status={status}"
        if error:
            prefix += f" error={error[:180]}"
        return prefix

    def _post(self, text: str) -> None:
        payload = json.dumps({"text": text, "mode": self.mode}).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                _ = res.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            logger.debug("OpenClaw notifier HTTP %s: %s", exc.code, body[:200])
        except Exception as exc:  # noqa: BLE001
            logger.debug("OpenClaw notifier failed: %s", exc)

    async def notify_task_event(self, task_id: str, event_type: str, data: dict[str, Any]) -> None:
        if not self.enabled:
            return
        text = self._format_text(task_id, event_type, data)
        await asyncio.to_thread(self._post, text)

