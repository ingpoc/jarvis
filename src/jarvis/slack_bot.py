"""Slack integration for Jarvis: bidirectional communication via Socket Mode.

Supports:
- Slash commands: /jarvis-status, /jarvis-approve, /jarvis-deny, /jarvis-run
- App mentions for natural language task routing
- Interactive approve/deny buttons (Block Kit)
- Auto-notifications from EventCollector
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import TYPE_CHECKING

try:
    from slack_bolt.async_app import AsyncApp
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    from slack_sdk.web.async_client import AsyncWebClient

    HAS_SLACK = True
except ImportError:
    HAS_SLACK = False

if TYPE_CHECKING:
    from jarvis.events import EventCollector

logger = logging.getLogger(__name__)


def _require_slack():
    if not HAS_SLACK:
        raise ImportError(
            "slack-bolt and slack-sdk are required for Slack integration. "
            "Install with: pip install 'jarvis-mac[slack]' or pip install slack-bolt slack-sdk"
        )


class JarvisSlackBot:
    """Slack bot using Socket Mode (no public URL needed)."""

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        default_channel: str,
        research_channel: str = "#jarvisresearch",
        event_collector: EventCollector | None = None,
        orchestrator=None,
    ):
        _require_slack()
        self._bot_token = bot_token
        self._app_token = app_token
        self._default_channel = default_channel
        self._research_channel = research_channel
        self._event_collector = event_collector
        self._orchestrator = orchestrator

        self._app = AsyncApp(token=bot_token)
        self._handler: AsyncSocketModeHandler | None = None
        self._client = AsyncWebClient(token=bot_token)
        self._notify_dedupe_window_secs = int(os.environ.get("JARVIS_SLACK_DEDUPE_SECS", "180"))
        self._last_notify_at: dict[str, float] = {}

        self._register_commands()
        self._register_events()
        self._register_actions()

        # Subscribe to EventCollector
        if self._event_collector:
            self._event_collector.add_listener(self._on_event)

    # --- Command handlers ---

    def _register_commands(self):
        @self._app.command("/jarvis-status")
        async def handle_status(ack, respond):
            await ack()
            if self._orchestrator:
                status = await self._orchestrator.get_status()
                blocks = self._build_status_blocks(status)
                await respond(blocks=blocks)
            else:
                await respond(text="Jarvis orchestrator not connected.")

        @self._app.command("/jarvis-run")
        async def handle_run(ack, respond, command):
            await ack()
            task_text = command.get("text", "").strip()
            if not task_text:
                await respond(text="Usage: `/jarvis-run <task description>`")
                return
            await respond(text=f"Starting task: _{task_text}_")
            if self._orchestrator:
                asyncio.create_task(self._run_task(task_text))

        @self._app.command("/jarvis-approve")
        async def handle_approve(ack, respond, command):
            await ack()
            task_id = command.get("text", "").strip()
            if not task_id:
                await respond(text="Usage: `/jarvis-approve <task-id>`")
                return
            # Emit approval event
            if self._event_collector:
                self._event_collector.emit(
                    "approval_granted",
                    f"Approved via Slack: {task_id}",
                    task_id=task_id,
                )
            await respond(text=f"Approved: {task_id}")

        @self._app.command("/jarvis-deny")
        async def handle_deny(ack, respond, command):
            await ack()
            task_id = command.get("text", "").strip()
            if not task_id:
                await respond(text="Usage: `/jarvis-deny <task-id>`")
                return
            if self._event_collector:
                self._event_collector.emit(
                    "approval_denied",
                    f"Denied via Slack: {task_id}",
                    task_id=task_id,
                )
            await respond(text=f"Denied: {task_id}")

    def _register_events(self):
        @self._app.event("app_mention")
        async def handle_mention(event, say):
            text = event.get("text", "")
            # Strip bot mention
            parts = text.split(">", 1)
            chat_text = parts[1].strip() if len(parts) > 1 else text
            if not chat_text:
                await say("Mention me with a task, e.g. `@Jarvis fix the failing tests`")
                return
            if self._orchestrator:
                asyncio.create_task(self._run_chat_from_event(event, say, chat_text))

        @self._app.event("message")
        async def handle_message(event, say):
            # Only handle direct conversations and ignore bot/system messages.
            if event.get("channel_type") not in {"im", "mpim"}:
                return
            if event.get("bot_id") or event.get("subtype"):
                return
            chat_text = (event.get("text") or "").strip()
            if not chat_text:
                return
            if self._orchestrator:
                asyncio.create_task(self._run_chat_from_event(event, say, chat_text))

    def _register_actions(self):
        @self._app.action("jarvis_approve")
        async def handle_approve_button(ack, body, respond):
            await ack()
            action_value = body["actions"][0].get("value", "")
            if self._event_collector:
                self._event_collector.emit(
                    "approval_granted",
                    f"Approved via button: {action_value}",
                    task_id=action_value,
                )
            await respond(text=f"Approved: {action_value}", replace_original=False)

        @self._app.action("jarvis_deny")
        async def handle_deny_button(ack, body, respond):
            await ack()
            action_value = body["actions"][0].get("value", "")
            if self._event_collector:
                self._event_collector.emit(
                    "approval_denied",
                    f"Denied via button: {action_value}",
                    task_id=action_value,
                )
            await respond(text=f"Denied: {action_value}", replace_original=False)

    # --- Event listener ---

    def _on_event(self, event_data: dict):
        """Handle events from EventCollector - send to Slack."""
        event_type = event_data.get("event_type", "")
        metadata = event_data.get("metadata") or {}
        if metadata.get("slack_notify") is False:
            return
        auto_notify_types = {
            "feature_complete", "error", "approval_needed",
            "task_complete", "trust_change",
        }
        if event_type in auto_notify_types:
            asyncio.create_task(self._send_event_notification(event_data))

    async def _send_event_notification(self, event_data: dict):
        """Send event notification to default Slack channel."""
        event_type = event_data["event_type"]
        summary = event_data.get("summary", "")
        task_id = event_data.get("task_id", "")
        dedupe_key = f"{event_type}|{task_id}|{summary[:180]}"
        now = time.time()
        last = self._last_notify_at.get(dedupe_key, 0.0)
        if (now - last) < self._notify_dedupe_window_secs:
            logger.info("Skipping duplicate Slack notification within window: %s", dedupe_key)
            return
        self._last_notify_at[dedupe_key] = now

        if event_type == "approval_needed":
            blocks = self._build_approval_blocks(task_id, summary)
            await self._client.chat_postMessage(
                channel=self._default_channel,
                text=f"Approval needed: {summary}",
                blocks=blocks,
            )
        elif event_type == "error":
            await self._client.chat_postMessage(
                channel=self._default_channel,
                text=f":red_circle: Error: {summary}",
            )
        elif event_type == "feature_complete":
            cost = event_data.get("cost_usd", 0.0)
            await self._client.chat_postMessage(
                channel=self._default_channel,
                text=f":white_check_mark: Feature complete: {summary} (${cost:.2f})",
            )
        elif event_type == "task_complete":
            cost = event_data.get("cost_usd", 0.0)
            await self._client.chat_postMessage(
                channel=self._default_channel,
                text=f":checkered_flag: Task complete: {summary} (${cost:.2f})",
            )
        elif event_type == "trust_change":
            await self._client.chat_postMessage(
                channel=self._default_channel,
                text=f":shield: Trust change: {summary}",
            )

    # --- Task execution ---

    async def _run_task(self, task_text: str):
        """Run a task and report results to Slack."""
        if not self._orchestrator:
            return
        try:
            result = await self._orchestrator.run_task(task_text)
            status = result.get("status", "unknown")
            output = result.get("output", "").strip()
            emoji = ":white_check_mark:" if status == "completed" else ":x:"

            # Truncate output if too long (Slack limit: 40,000 chars)
            max_length = 35000
            truncated = False
            if len(output) > max_length:
                output = output[:max_length] + "\n\n... (output truncated)"
                truncated = True

            # Format message
            message = f"{emoji} *Task {status}*\n\n{output}"
            if truncated:
                message += "\n\n_Output was truncated due to size_"

            await self._client.chat_postMessage(
                channel=self._default_channel,
                text=message,
            )
        except Exception as e:
            await self._client.chat_postMessage(
                channel=self._default_channel,
                text=f":x: Task failed: {e}",
            )

    async def _run_chat_from_event(self, event: dict, say, chat_text: str):
        """Handle conversational Slack message via orchestrator.chat."""
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        user = event.get("user", "unknown")
        logger.info("Slack chat message from %s in %s: %s", user, channel, chat_text[:120])

        try:
            result = await self._orchestrator.handle_message(
                chat_text,
                origin=f"slack:{channel or 'unknown'}",
            )
            route = result.get("route")
            reply = (result.get("reply") or "").strip()
            if not reply:
                reply = "No response generated."
            await say(reply[:35000], thread_ts=thread_ts)
        except Exception as e:
            await say(f":x: Chat failed: {e}", thread_ts=thread_ts)

    # --- Block Kit builders ---

    @staticmethod
    def _build_status_blocks(status: dict) -> list[dict]:
        trust = status.get("trust", {})
        budget = status.get("budget", {})
        recent = status.get("recent_tasks", [])

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Jarvis Status"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Trust:* T{trust.get('tier', '?')} ({trust.get('tier_name', '?')})"},
                    {"type": "mrkdwn", "text": f"*Budget:* {budget.get('session', '?')}"},
                    {"type": "mrkdwn", "text": f"*Active containers:* {status.get('containers', 0)}"},
                    {"type": "mrkdwn", "text": f"*Project:* {status.get('project', '?')}"},
                ],
            },
        ]

        if recent:
            task_lines = []
            for t in recent[:5]:
                emoji = {"completed": ":white_check_mark:", "failed": ":x:", "in_progress": ":hourglass:"}.get(
                    t.get("status", ""), ":grey_question:"
                )
                task_lines.append(f"{emoji} `{t['id']}` {t['description'][:50]} ({t['cost']})")
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Recent Tasks:*\n" + "\n".join(task_lines)},
            })

        return blocks

    @staticmethod
    def _build_approval_blocks(task_id: str, summary: str) -> list[dict]:
        return [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Approval Needed"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Task:* `{task_id}`\n{summary}"},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve"},
                        "style": "primary",
                        "action_id": "jarvis_approve",
                        "value": task_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Deny"},
                        "style": "danger",
                        "action_id": "jarvis_deny",
                        "value": task_id,
                    },
                ],
            },
        ]

    # --- Lifecycle ---

    async def start(self):
        """Start the Slack bot in Socket Mode."""
        self._handler = AsyncSocketModeHandler(self._app, self._app_token)
        await self._handler.start_async()
        logger.info("Slack bot started in Socket Mode")

    async def stop(self):
        """Stop the Slack bot."""
        if self._handler:
            await self._handler.close_async()
            logger.info("Slack bot stopped")

    async def send_message(self, text: str, channel: str | None = None):
        """Send a message to a Slack channel."""
        await self._client.chat_postMessage(
            channel=channel or self._default_channel,
            text=text,
        )
