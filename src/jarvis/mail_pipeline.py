"""Modular local mail digest pipeline.

Uses Zapier MCP directly for mailbox retrieval and deterministic digesting.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

def _safe_json_parse(text: str, default: Any = None) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return default


@dataclass
class MailRecord:
    sender: str
    subject: str
    received_at: str
    snippet: str
    thread_id: str
    message_id: str


class ZapierMailClient:
    """Fetches mail data from Zapier MCP tools."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        token: str | None = None,
        find_tool_name: str = "gmail_find_email",
    ):
        self.endpoint_url = endpoint_url
        self.token = token
        self.find_tool_name = find_tool_name

    @classmethod
    def from_env(cls) -> "ZapierMailClient | None":
        url = os.environ.get("ZAPIER_MCP_URL", "").strip()
        if not url:
            return None
        token = os.environ.get("ZAPIER_MCP_TOKEN", "").strip() or None
        tool_name = os.environ.get("JARVIS_ZAPIER_FIND_TOOL", "gmail_find_email").strip()
        return cls(endpoint_url=url, token=token, find_tool_name=tool_name)

    async def fetch_recent_messages(
        self,
        *,
        window_hours: int,
        limit: int = 30,
    ) -> list[MailRecord]:
        """Call Zapier gmail_find_email and normalize results."""
        limit = max(1, min(int(limit), 100))
        since_dt = datetime.now(timezone.utc) - timedelta(hours=max(1, int(window_hours)))
        after_expr = since_dt.strftime("%Y/%m/%d")
        days = max(1, math.ceil(max(1, int(window_hours)) / 24))

        attempts = [
            {
                "instructions": (
                    "Find recent inbox emails and return structured fields "
                    "(sender, subject, received_at, snippet, thread_id, message_id)."
                ),
                "query": f"in:inbox newer_than:{days}d after:{after_expr}",
            },
            {
                "instructions": "Find latest inbox emails.",
                "query": f"in:inbox newer_than:{days}d",
            },
            {
                "instructions": "Find latest inbox emails (broad search).",
                "query": "in:inbox",
            },
        ]
        output_hint = (
            "Return compact JSON: {\"results\":[...]}. "
            "Each result should include sender, subject, received_at, snippet, thread_id, message_id. "
            f"Return up to {limit} results."
        )

        for attempt in attempts:
            result = await self._call_tool(
                self.find_tool_name,
                {
                    "instructions": attempt["instructions"],
                    "query": attempt["query"],
                    "output_hint": output_hint,
                },
            )
            text = self._extract_text(result)
            parsed = self._parse_records(text, max_items=limit)
            if parsed:
                return parsed
        return []

    async def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            async with streamable_http_client(self.endpoint_url, http_client=client) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    return await session.call_tool(tool_name, arguments)

    @staticmethod
    def _extract_text(call_result: Any) -> str:
        parts: list[str] = []
        content = getattr(call_result, "content", []) or []
        for item in content:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(parts).strip()

    @staticmethod
    def _parse_records(text: str, *, max_items: int) -> list[MailRecord]:
        if not text:
            return []

        payload = _safe_json_parse(text, default=None)
        if payload is None:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                payload = _safe_json_parse(match.group(0), default={})
            else:
                payload = {}

        rows: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            raw_results = payload.get("results", [])
            if isinstance(raw_results, list):
                rows = [r for r in raw_results if isinstance(r, dict)]
        elif isinstance(payload, list):
            rows = [r for r in payload if isinstance(r, dict)]

        out: list[MailRecord] = []
        for row in rows[:max_items]:
            out.append(
                MailRecord(
                    sender=str(row.get("sender") or "").strip(),
                    subject=str(row.get("subject") or "").strip(),
                    received_at=str(row.get("received_at") or "").strip(),
                    snippet=str(row.get("snippet") or "").strip(),
                    thread_id=str(row.get("thread_id") or "").strip(),
                    message_id=str(row.get("message_id") or "").strip(),
                )
            )
        return out


class LocalMailDigestService:
    """Build digest using deterministic heuristics."""

    URGENT_KEYWORDS = (
        "urgent",
        "asap",
        "security alert",
        "action required",
        "verify",
        "immediately",
        "deadline",
        "overdue",
        "account issue",
    )
    WAITING_KEYWORDS = (
        "we'll get back",
        "we will get back",
        "pending",
        "under review",
        "processing",
        "in progress",
        "awaiting",
    )
    AUTOMATED_HINTS = (
        "no-reply",
        "noreply",
        "notification",
        "alert",
        "receipt",
        "invoice",
        "shipped",
        "delivered",
        "newsletter",
    )
    ASK_KEYWORDS = (
        "please",
        "can you",
        "could you",
        "let me know",
        "confirm",
        "reply",
        "need your",
        "?",
    )

    def __init__(self, source: ZapierMailClient):
        self.source = source

    async def build_digest(
        self,
        *,
        window_hours: int,
        local_model_id: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        """Return digest dict and raw notes."""
        _ = local_model_id  # Compatibility-only; OpenCode runtime uses deterministic digest.
        records = await self.source.fetch_recent_messages(window_hours=window_hours)
        digest = self._heuristic_digest(records)

        raw = f"Local pipeline processed {len(records)} messages via Zapier MCP."
        return digest, raw

    def _heuristic_digest(self, records: list[MailRecord]) -> dict[str, Any]:
        buckets: dict[str, list[dict[str, Any]]] = {
            "urgent": [],
            "reply_today": [],
            "waiting_on_them": [],
            "fyi": [],
        }

        for rec in records:
            text = f"{rec.subject} {rec.snippet} {rec.sender}".lower()
            item = {
                "thread_id": rec.thread_id or rec.message_id,
                "message_id": rec.message_id,
                "subject": rec.subject,
                "sender": rec.sender,
                "received_at": rec.received_at,
                "snippet": rec.snippet[:400],
                "reason": "",
                "next_action": "",
            }

            if any(k in text for k in self.URGENT_KEYWORDS):
                item["reason"] = "Contains urgency/security/deadline signals."
                item["next_action"] = "Review immediately and respond if needed."
                buckets["urgent"].append(item)
                continue

            if any(k in text for k in self.WAITING_KEYWORDS):
                item["reason"] = "Looks like a status update where counterpart owes next step."
                item["next_action"] = "Wait; set follow-up reminder."
                buckets["waiting_on_them"].append(item)
                continue

            automated = any(k in text for k in self.AUTOMATED_HINTS)
            asks_for_reply = any(k in text for k in self.ASK_KEYWORDS)
            if asks_for_reply and not automated:
                item["reason"] = "Likely asks for a reply or confirmation."
                item["next_action"] = "Reply today."
                buckets["reply_today"].append(item)
            elif automated:
                item["reason"] = "Automated or informational message."
                item["next_action"] = "No immediate action."
                buckets["fyi"].append(item)
            else:
                item["reason"] = "Potentially actionable personal message."
                item["next_action"] = "Review and reply today if needed."
                buckets["reply_today"].append(item)

        top_3_now = (
            buckets["urgent"][:2]
            + buckets["reply_today"][:2]
            + buckets["waiting_on_them"][:1]
        )[:3]

        return {
            "urgent": buckets["urgent"],
            "reply_today": buckets["reply_today"],
            "waiting_on_them": buckets["waiting_on_them"],
            "fyi": buckets["fyi"],
            "top_3_now": top_3_now,
            "summary": (
                f"Processed {len(records)} messages. "
                f"Urgent={len(buckets['urgent'])}, Reply today={len(buckets['reply_today'])}, "
                f"Waiting={len(buckets['waiting_on_them'])}, FYI={len(buckets['fyi'])}."
            ),
        }
