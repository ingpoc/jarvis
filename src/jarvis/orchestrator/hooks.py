"""Tool hooks for Jarvis orchestrator.

Handles pre-tool, post-tool, and post-message hooks for budget enforcement,
trust checks, event emission, and loop detection.
"""

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from jarvis.events import EVENT_TOOL_USE
from jarvis.loop_detector import LoopDetector, LoopAction, build_intervention_message
from jarvis.jarvis_hooks import build_deny_response

if TYPE_CHECKING:
    from jarvis.trust import TrustEngine
    from jarvis.budget import BudgetController
    from jarvis.memory import MemoryStore

logger = logging.getLogger(__name__)


def _is_tool_error(tool_name: str, tool_response: str) -> bool:
    """Determine if a tool response represents a real error.

    Uses tool-specific heuristics to avoid false positives from responses
    that merely mention 'error' (e.g., reading error-handling code).
    """
    if not isinstance(tool_response, str):
        return False

    # Read/Glob/Grep: reading code that mentions "error" is NOT an error
    if tool_name in ("Read", "Glob", "Grep", "WebFetch", "WebSearch"):
        return False

    response_lower = tool_response.lower()

    # Bash: look for common failure patterns
    if tool_name == "Bash":
        failure_signals = [
            "command not found",
            "no such file or directory",
            "permission denied",
            "segmentation fault",
            "killed",
            "npm err!",
            "syntaxerror:",
            "modulenotfounderror:",
            "importerror:",
            "typeerror:",
            "nameerror:",
            "valueerror:",
            "compilation failed",
            "build failed",
            "test failed",
            "tests failed",
            "exit code",
            "exited with",
        ]
        return any(sig in response_lower for sig in failure_signals)

    # Edit/Write: tool-level failures (not content)
    if tool_name in ("Edit", "Write"):
        return "error" in response_lower and len(tool_response) < 200

    return False


class OrchestratorHooks:
    """Manages hooks for the Jarvis orchestrator."""

    def __init__(
        self,
        trust: "TrustEngine",
        budget: "BudgetController",
        memory: "MemoryStore",
        loop_detector: LoopDetector,
        events: Any,
        project_path: str,
        notifications_module: Any = None,
    ):
        self.trust = trust
        self.budget = budget
        self.memory = memory
        self.loop_detector = loop_detector
        self.events = events
        self.project_path = project_path
        self._notifications = notifications_module

    async def pre_tool_hook(self, input_data: dict, tool_use_id: str | None, context: dict) -> dict:
        """Hook: enforce trust and budget before tool execution."""
        import time as _time
        context["_tool_start_time"] = _time.monotonic()

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Budget check
        can_continue, reason = self.budget.enforce()
        if not can_continue:
            return build_deny_response(f"Budget limit: {reason}")

        # Trust check for container operations
        if "container" in tool_name.lower():
            action = tool_name.split("__")[-1] if "__" in tool_name else tool_name
            allowed, reason = self.trust.can_perform(self.project_path, action)
            if not allowed:
                return build_deny_response(reason)

        # Trust check for git push
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if "git push" in command:
                allowed, reason = self.trust.can_perform(self.project_path, "git_push")
                if not allowed:
                    return build_deny_response(reason)

        return {}

    def _extract_error_info(self, tool_name: str, tool_response: str, tool_input: dict) -> tuple[str | None, int]:
        """Extract error message and exit code from tool response."""
        if not isinstance(tool_response, str):
            return None, 0

        response_lower = tool_response.lower()

        # Bash tool: check for non-zero exit code
        if tool_name == "Bash" and tool_input.get("exit_code", 0) != 0:
            return tool_response[:500], tool_input.get("exit_code", 1)

        # Tool-level error signals: lines starting with error/traceback
        if any(response_lower.lstrip().startswith(p) for p in ("error:", "error!", "traceback ", "fatal:", "panic:")):
            return tool_response[:500], 1

        # Explicit failure patterns
        if _is_tool_error(tool_name, tool_response):
            return tool_response[:500], 1

        return None, 0

    def _extract_files_touched(self, tool_name: str, tool_input: dict) -> list[str]:
        """Extract files touched by Edit/Write tools."""
        if tool_name in ["Edit", "Write"] and isinstance(tool_input, dict):
            if "file_path" in tool_input:
                return [tool_input["file_path"]]
        return []

    def _track_container_from_response(self, tool_name: str, tool_response: str) -> str | None:
        """Extract container ID from container_run response if running."""
        if "container_run" not in tool_name or not isinstance(tool_response, str):
            return None
        try:
            data = json.loads(tool_response)
            if data.get("status") == "running":
                return data.get("container_id")
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    def _check_loop_detection(self, tool_name: str, tool_input: dict, tool_response: str, task_id: str) -> dict | None:
        """Check for loops and return intervention response if needed."""
        tool_input_str = json.dumps(tool_input)
        tool_output_str = str(tool_response)[:5120]
        error = tool_response[:1024] if isinstance(tool_response, str) and "error" in tool_response.lower() else None

        action = self.loop_detector.record_iteration(task_id, tool_name, tool_input_str, tool_output_str, error)

        if action == LoopAction.CONTINUE:
            return None

        tracker = self.loop_detector.get_tracker(task_id)
        message = build_intervention_message(action, tracker)

        if action == LoopAction.ESCALATE:
            import asyncio
            if self._notifications:
                asyncio.create_task(self._notifications.notify_approval_needed(task_id, "loop_escalation"))

        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "message": message,
            }
        }

    async def post_tool_hook(self, input_data: dict, tool_use_id: str | None, context: dict) -> dict:
        """Hook: track container lifecycle, emit events, detect loops, capture execution records."""
        tool_name = input_data.get("tool_name", "")
        tool_response = input_data.get("tool_response", "")
        tool_input = input_data.get("tool_input", {})

        # Emit tool use event
        self.events.emit(EVENT_TOOL_USE, tool_name, task_id=context.get("task_id"), metadata={"tool": tool_name})

        task_id = context.get("task_id", "unknown")

        # Extract error info and files touched
        error_message, exit_code = self._extract_error_info(tool_name, tool_response, tool_input)
        files_touched = self._extract_files_touched(tool_name, tool_input)

        # Calculate duration
        duration_ms = 0.0
        if "_tool_start_time" in context:
            duration_ms = (time.monotonic() - context["_tool_start_time"]) * 1000

        # Record execution (best effort - required for learning loop)
        try:
            self.memory.record_execution(
                task_id=task_id,
                session_id=context.get("session_id", "unknown"),
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_response,
                exit_code=exit_code,
                files_touched=files_touched or None,
                error_message=error_message,
                duration_ms=duration_ms,
                project_path=self.project_path,
            )
        except Exception as e:
            # Log warning instead of silent failure - execution records are critical for learning
            logger.warning(f"Failed to record execution for task {task_id}, tool {tool_name}: {e}")

        # Loop detection
        loop_response = self._check_loop_detection(tool_name, tool_input, tool_response, task_id)
        return loop_response if loop_response else {}

    async def post_message_hook(self, input_data: dict, context: dict) -> dict:
        """Hook: track token usage and costs from ResultMessage events."""
        message_type = input_data.get("type", "")

        if message_type == "result":
            cost_usd = input_data.get("total_cost_usd", 0.0)
            num_turns = input_data.get("num_turns", 0)
            input_tokens = input_data.get("usage", {}).get("input_tokens", 0)
            output_tokens = input_data.get("usage", {}).get("output_tokens", 0)

            # Record token usage for analytics
            task_id = context.get("task_id", "unknown")
            model = context.get("model", "unknown")
            try:
                self.memory.record_token_usage(
                    session_id=context.get("session_id", "unknown"),
                    task_id=task_id,
                    model=model,
                    prompt_tokens=input_tokens,
                    completion_tokens=output_tokens,
                    cost_usd=cost_usd,
                    project_path=self.project_path,
                )
            except Exception:
                pass  # Token tracking is best-effort

            # Record cost in budget controller
            if cost_usd > 0:
                self.budget.record_cost(cost_usd, num_turns)

        return {}
