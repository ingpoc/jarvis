"""A2A (Agent-to-Agent) protocol models."""

import time
from dataclasses import dataclass, field
from enum import Enum


class A2ATaskState(str, Enum):
    """A2A task states as defined in the protocol."""

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input_required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    AUTH_REQUIRED = "auth_required"
    REJECTED = "rejected"


# Mapping from internal task states to A2A protocol states
# Note: Both "cancelled" and "canceled" spellings are supported for robustness
INTERNAL_TO_A2A = {
    "pending": A2ATaskState.SUBMITTED,
    "in_progress": A2ATaskState.WORKING,
    "paused": A2ATaskState.INPUT_REQUIRED,
    "completed": A2ATaskState.COMPLETED,
    "failed": A2ATaskState.FAILED,
    "cancelled": A2ATaskState.CANCELED,
    "canceled": A2ATaskState.CANCELED,  # Support both spellings
    # A2A-only states (no internal equivalent, used for policy decisions)
    "auth_pending": A2ATaskState.AUTH_REQUIRED,
    "rejected": A2ATaskState.REJECTED,
}


def map_internal_to_a2a(internal_status: str) -> A2ATaskState:
    """Map internal Jarvis status to A2A status with fallback.

    Args:
        internal_status: Internal task status string

    Returns:
        A2ATaskState enum value
    """
    # Normalize to lowercase for matching
    normalized = (internal_status or "").strip().lower()
    return INTERNAL_TO_A2A.get(normalized, A2ATaskState.WORKING)


@dataclass
class A2AArtifact:
    """Artifact produced by an A2A task."""

    name: str
    content: str
    mime_type: str = "text/plain"


@dataclass
class A2ATask:
    """A2A task representation."""

    id: str
    run_id: str
    status: A2ATaskState
    message: str
    context_id: str | None = None
    artifacts: list[A2AArtifact] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    result: str | None = None
    error: str | None = None
