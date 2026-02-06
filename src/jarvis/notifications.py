"""macOS native notifications for Jarvis.

Uses osascript for native Notification Center integration.
Also dispatches to Slack and voice when enabled.
4 priority levels matching the UX proposal:
- Low: menu bar badge only (no notification)
- Medium: banner (auto-dismiss)
- High: alert (requires interaction)
- Critical: alert + sound
"""

from __future__ import annotations

import asyncio
import logging
import os
from enum import Enum

logger = logging.getLogger(__name__)

# Global references set by daemon/orchestrator at startup
_slack_bot = None
_voice_client = None


def set_slack_bot(bot) -> None:
    """Register Slack bot for notification dispatch."""
    global _slack_bot
    _slack_bot = bot


def set_voice_client(client) -> None:
    """Register voice client for notification dispatch."""
    global _voice_client
    _voice_client = client


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


async def notify(
    title: str,
    message: str,
    priority: Priority = Priority.MEDIUM,
    subtitle: str = "",
    sound: bool | None = None,
) -> None:
    """Send a notification via osascript + Slack + voice (when enabled).

    Args:
        title: Notification title
        message: Body text
        priority: Priority level
        subtitle: Optional subtitle
        sound: Override sound (None = auto based on priority)
    """
    if sound is None:
        sound = priority in (Priority.HIGH, Priority.CRITICAL)

    # macOS native notification
    await _notify_osascript(title, message, subtitle, sound, priority)

    # Slack dispatch
    if _slack_bot:
        try:
            slack_text = f"*{title}*"
            if subtitle:
                slack_text += f" ({subtitle})"
            slack_text += f"\n{message}"
            await _slack_bot.send_message(slack_text)
        except Exception as e:
            logger.debug(f"Slack notification failed: {e}")

    # Voice dispatch for critical/high priority
    if _voice_client and priority in (Priority.HIGH, Priority.CRITICAL):
        try:
            await _voice_client.speak(f"{title}. {message}")
        except Exception as e:
            logger.debug(f"Voice notification failed: {e}")


async def _notify_osascript(
    title: str, message: str, subtitle: str, sound: bool, priority: Priority,
) -> None:
    """Send macOS native notification via osascript."""
    script_parts = [f'display notification "{_escape(message)}"']
    script_parts.append(f'with title "{_escape(title)}"')

    if subtitle:
        script_parts.append(f'subtitle "{_escape(subtitle)}"')

    if sound:
        sound_name = "Ping" if priority == Priority.HIGH else "Sosumi"
        script_parts.append(f'sound name "{sound_name}"')

    script = " ".join(script_parts)

    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=5)
    except Exception:
        pass  # Notifications are best-effort


def notify_sync(
    title: str,
    message: str,
    priority: Priority = Priority.MEDIUM,
    subtitle: str = "",
) -> None:
    """Synchronous notification wrapper."""
    try:
        asyncio.get_event_loop().run_until_complete(
            notify(title, message, priority, subtitle)
        )
    except RuntimeError:
        asyncio.run(notify(title, message, priority, subtitle))


def _escape(text: str) -> str:
    """Escape string for AppleScript."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


# --- Convenience functions ---


async def notify_task_started(task_id: str, description: str) -> None:
    await notify(
        "Jarvis: Task Started",
        description[:100],
        Priority.LOW,
        subtitle=task_id,
    )


async def notify_task_completed(task_id: str, description: str, cost: float) -> None:
    await notify(
        "Jarvis: Task Complete",
        f"{description[:80]} (${cost:.2f})",
        Priority.MEDIUM,
        subtitle=task_id,
    )


async def notify_task_failed(task_id: str, description: str, error: str) -> None:
    await notify(
        "Jarvis: Task Failed",
        f"{description[:60]} - {error[:40]}",
        Priority.HIGH,
        subtitle=task_id,
    )


async def notify_approval_needed(task_id: str, action: str) -> None:
    await notify(
        "Jarvis: Approval Needed",
        f"Action requires approval: {action}",
        Priority.HIGH,
        subtitle=task_id,
        sound=True,
    )


async def notify_budget_warning(spent: float, limit: float) -> None:
    pct = (spent / limit) * 100 if limit > 0 else 100
    await notify(
        "Jarvis: Budget Warning",
        f"${spent:.2f} / ${limit:.2f} ({pct:.0f}% used)",
        Priority.CRITICAL,
    )


async def notify_trust_change(old_tier: int, new_tier: int, direction: str) -> None:
    await notify(
        f"Jarvis: Trust {direction}",
        f"T{old_tier} -> T{new_tier}",
        Priority.MEDIUM,
    )


async def notify_review_complete(approved: bool, issues: int) -> None:
    status = "Approved" if approved else f"Changes Requested ({issues} issues)"
    priority = Priority.MEDIUM if approved else Priority.HIGH
    await notify(
        "Jarvis: Code Review",
        status,
        priority,
    )
