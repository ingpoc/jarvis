"""A2A (Agent-to-Agent) protocol support."""

from .models import A2AArtifact, A2ATask, A2ATaskState, INTERNAL_TO_A2A, map_internal_to_a2a
from .client import JarvisA2AClient, A2AClientError, TERMINAL_TASK_STATES

__all__ = [
    "A2ATaskState",
    "INTERNAL_TO_A2A",
    "map_internal_to_a2a",
    "A2AArtifact",
    "A2ATask",
    "JarvisA2AClient",
    "A2AClientError",
    "TERMINAL_TASK_STATES",
]
