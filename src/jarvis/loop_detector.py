"""Ralph Loop Detection: prevents agents from spinning on repeated failures.

Detects:
- Max iteration limits (hard stop)
- Repeated identical errors (change approach)
- Stagnant output (escalate)
- Approaching limits (warn)
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum


class LoopAction(Enum):
    """Action to take based on loop detection."""

    CONTINUE = "continue"
    WARN = "warn"
    CHANGE_APPROACH = "change_approach"
    ESCALATE = "escalate"
    HARD_STOP = "hard_stop"


@dataclass
class IterationRecord:
    """Record of a single tool iteration."""

    iteration: int
    tool_name: str
    input_hash: str
    output_hash: str
    error: str | None = None
    error_hash: str | None = None
    timestamp: float = field(default_factory=time.time)


def _hash_content(content: str) -> str:
    """SHA-256 truncated to 16 chars on first 5KB."""
    truncated = content[:5120]
    return hashlib.sha256(truncated.encode()).hexdigest()[:16]


class SubtaskTracker:
    """Per-subtask iteration tracking with analysis properties."""

    def __init__(self, subtask_id: str, max_iterations: int = 10):
        self.subtask_id = subtask_id
        self.max_iterations = max_iterations
        self.iterations: list[IterationRecord] = []
        self._warned_at_50: bool = False

    @property
    def count(self) -> int:
        return len(self.iterations)

    @property
    def remaining(self) -> int:
        return max(0, self.max_iterations - self.count)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.iterations if r.error)

    @property
    def unique_errors(self) -> int:
        hashes = {r.error_hash for r in self.iterations if r.error_hash}
        return len(hashes)

    def last_n_same_error(self, n: int = 3) -> bool:
        """Check if the last n iterations had the same error."""
        if len(self.iterations) < n:
            return False
        recent = self.iterations[-n:]
        if not all(r.error_hash for r in recent):
            return False
        return len({r.error_hash for r in recent}) == 1

    def output_stagnant(self, n: int = 3) -> bool:
        """Check if the last n iterations had identical output."""
        if len(self.iterations) < n:
            return False
        recent = self.iterations[-n:]
        return len({r.output_hash for r in recent}) == 1

    def add(self, record: IterationRecord) -> None:
        self.iterations.append(record)


class LoopDetector:
    """Main loop detection engine.

    Tracks iterations per subtask and evaluates whether to continue,
    warn, change approach, escalate, or hard stop.
    """

    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        self._trackers: dict[str, SubtaskTracker] = {}

    def _get_tracker(self, subtask_id: str) -> SubtaskTracker:
        if subtask_id not in self._trackers:
            self._trackers[subtask_id] = SubtaskTracker(subtask_id, self.max_iterations)
        return self._trackers[subtask_id]

    def record_iteration(
        self,
        subtask_id: str,
        tool_name: str,
        tool_input: str,
        tool_output: str,
        error: str | None = None,
    ) -> LoopAction:
        """Record a tool iteration and evaluate loop status.

        Returns the recommended LoopAction.
        """
        tracker = self._get_tracker(subtask_id)

        record = IterationRecord(
            iteration=tracker.count + 1,
            tool_name=tool_name,
            input_hash=_hash_content(tool_input),
            output_hash=_hash_content(tool_output),
            error=error,
            error_hash=_hash_content(error) if error else None,
        )
        tracker.add(record)

        return self._evaluate(tracker)

    def _evaluate(self, tracker: SubtaskTracker) -> LoopAction:
        """Evaluate loop status and return recommended action."""
        # Hard stop at max iterations
        if tracker.count >= tracker.max_iterations:
            return LoopAction.HARD_STOP

        # Same error 3 times in a row → change approach
        if tracker.last_n_same_error(3):
            return LoopAction.CHANGE_APPROACH

        # Output stagnant 3 times in a row → escalate
        if tracker.output_stagnant(3):
            return LoopAction.ESCALATE

        # At 80% of cap → change approach
        if tracker.count >= int(tracker.max_iterations * 0.8):
            return LoopAction.CHANGE_APPROACH

        # At 50% of cap (first time) → warn
        halfway = int(tracker.max_iterations * 0.5)
        if tracker.count >= halfway and not tracker._warned_at_50:
            tracker._warned_at_50 = True
            return LoopAction.WARN

        return LoopAction.CONTINUE

    def get_tracker(self, subtask_id: str) -> SubtaskTracker | None:
        """Get tracker for a subtask (for inspection)."""
        return self._trackers.get(subtask_id)

    def reset(self, subtask_id: str) -> None:
        """Reset tracking for a subtask."""
        self._trackers.pop(subtask_id, None)


def build_intervention_message(action: LoopAction, tracker: SubtaskTracker) -> str:
    """Build a human-readable intervention message for the given action."""
    messages = {
        LoopAction.CONTINUE: "",
        LoopAction.WARN: (
            f"[Loop Detection] Subtask '{tracker.subtask_id}' at {tracker.count}/{tracker.max_iterations} iterations. "
            f"{tracker.remaining} remaining. Errors: {tracker.error_count}. "
            f"Consider whether current approach is working."
        ),
        LoopAction.CHANGE_APPROACH: (
            f"[Loop Detection] Subtask '{tracker.subtask_id}' is stuck at {tracker.count}/{tracker.max_iterations} iterations. "
            f"Unique errors: {tracker.unique_errors}. "
            f"MUST change approach: try a different strategy, simplify the task, or break it into smaller steps."
        ),
        LoopAction.ESCALATE: (
            f"[Loop Detection] Subtask '{tracker.subtask_id}' output is stagnant after {tracker.count} iterations. "
            f"Escalating to human review. The current approach is not making progress."
        ),
        LoopAction.HARD_STOP: (
            f"[Loop Detection] Subtask '{tracker.subtask_id}' hit max iterations ({tracker.max_iterations}). "
            f"STOPPING. Errors: {tracker.error_count}/{tracker.count}. "
            f"Task needs human intervention or re-scoping."
        ),
    }
    return messages.get(action, "")
