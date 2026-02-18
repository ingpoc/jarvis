"""Jarvis hook utilities: shared hook response builders and validators."""
from typing import Any


def build_hook_response(event_name: str, **kwargs) -> dict:
    """Build a standardized hook response.

    Args:
        event_name: The hook event name (PreToolUse, PostToolUse, etc.)
        **kwargs: Additional fields to include in hookSpecificOutput

    Returns:
        Hook response dict
    """
    return {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            **kwargs,
        }
    }


def build_deny_response(reason: str, event_name: str = "PreToolUse") -> dict:
    """Build a deny response for hooks."""
    return build_hook_response(
        event_name,
        permissionDecision="deny",
        permissionDecisionReason=reason,
    )


def build_approve_response(event_name: str = "PreToolUse") -> dict:
    """Build an approve response for hooks."""
    return build_hook_response(
        event_name,
        permissionDecision="approve",
    )


class TrustChecker:
    """Utility for checking trust levels for tool operations."""

    # Tools requiring specific trust tiers
    TIER_REQUIREMENTS = {
        "container_create": 2,  # T2+ for container creation
        "container_destroy": 2,
        "git_push": 2,  # T2+ for pushing
        "git_reset": 3,  # T3 for destructive git ops
        "rm_rf": 3,  # T3 for recursive delete
    }

    def __init__(self, current_tier: int = 1):
        self.current_tier = current_tier

    def can_perform(self, action: str) -> tuple[bool, str]:
        """Check if current trust tier allows action.

        Returns:
            (allowed, reason) tuple
        """
        required = self.TIER_REQUIREMENTS.get(action, 1)
        if self.current_tier >= required:
            return True, ""
        return False, f"Requires T{required}, currently T{self.current_tier}"

    def check_tool(self, tool_name: str, tool_input: dict) -> tuple[bool, str]:
        """Check if tool use is allowed by trust tier.

        Args:
            tool_name: Name of the tool being used
            tool_input: Tool input parameters

        Returns:
            (allowed, reason) tuple
        """
        # Check container operations
        if "container" in tool_name.lower():
            action = tool_name.split("__")[-1] if "__" in tool_name else tool_name
            return self.can_perform(f"container_{action}")

        # Check git push
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if "git push" in command:
                return self.can_perform("git_push")
            if "git reset --hard" in command or "git reset -" in command:
                return self.can_perform("git_reset")
            if "rm -rf" in command:
                return self.can_perform("rm_rf")

        return True, ""


class ToolExecutionTracker:
    """Tracks tool execution for event emission and learning."""

    def __init__(self):
        self.executions: list[dict] = []

    def record(
        self,
        tool_name: str,
        tool_input: dict,
        tool_response: Any,
        exit_code: int = 0,
        duration_ms: float = 0.0,
        error_message: str | None = None,
        files_touched: list[str] | None = None,
    ) -> dict:
        """Record a tool execution."""
        record = {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_response": tool_response,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "error_message": error_message,
            "files_touched": files_touched or [],
        }
        self.executions.append(record)
        return record

    def get_executions(self, tool_name: str | None = None) -> list[dict]:
        """Get recorded executions, optionally filtered by tool."""
        if tool_name:
            return [e for e in self.executions if e["tool_name"] == tool_name]
        return list(self.executions)
