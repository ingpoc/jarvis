"""Decision trace memory: query precedents before deciding, store traces after.

Wraps context-graph MCP tools with local SQLite fallback.
Implements trust thresholds for recommendation confidence:
- >0.75: use precedent without re-evaluation
- 0.60-0.75: use precedent but verify
- <0.60: new decision needed
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TraceCategory(Enum):
    """Categories for decision traces."""

    TASK_EXECUTION = "task_execution"
    CONTAINER_SETUP = "container_setup"
    ERROR_RESOLUTION = "error_resolution"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    GIT_WORKFLOW = "git_workflow"
    DEPENDENCY_MGMT = "dependency_mgmt"


@dataclass
class TraceResult:
    """A decision trace record."""

    trace_id: str
    category: str
    description: str
    decision: str
    outcome: str = "pending"
    confidence: float = 0.0
    similarity: float = 0.0


class DecisionTracer:
    """Decision trace memory with MCP + local SQLite dual backend.

    Tries context-graph MCP tools first, falls back to local SQLite.
    Always writes to local for durability.
    """

    def __init__(self, memory=None, mcp_client=None):
        """Initialize tracer.

        Args:
            memory: MemoryStore instance for local SQLite access
            mcp_client: Optional MCP client for context-graph tools
        """
        self._memory = memory
        self._mcp = mcp_client

    async def query_precedents(
        self,
        query: str,
        category: TraceCategory | None = None,
        limit: int = 5,
    ) -> list[TraceResult]:
        """Query for similar past decisions.

        Tries MCP context_query_traces first, falls back to local.
        """
        results = []

        # Try MCP first
        if self._mcp:
            try:
                mcp_args = {"query": query, "limit": limit}
                if category:
                    mcp_args["category"] = category.value
                response = await self._mcp.call_tool("context_query_traces", mcp_args)
                if response and isinstance(response, list):
                    for item in response:
                        results.append(TraceResult(
                            trace_id=item.get("id", ""),
                            category=item.get("category", ""),
                            description=item.get("description", ""),
                            decision=item.get("decision", ""),
                            outcome=item.get("outcome", "pending"),
                            confidence=item.get("confidence", 0.0),
                            similarity=item.get("similarity", 0.0),
                        ))
                    return results
            except Exception as e:
                logger.debug(f"MCP query_traces failed, using local: {e}")

        # Fallback to local
        if self._memory:
            cat_value = category.value if category else None
            local_traces = self._memory.query_local_traces(
                project_path=None, category=cat_value, limit=limit
            )
            for t in local_traces:
                results.append(TraceResult(
                    trace_id=t["id"],
                    category=t["category"],
                    description=t["description"],
                    decision=t["decision"],
                    outcome=t["outcome"],
                    confidence=0.5,  # Local traces have no similarity scoring
                    similarity=0.0,
                ))

        return results

    async def store_trace(
        self,
        category: TraceCategory,
        description: str,
        decision: str,
        context: dict | None = None,
        outcome: str = "pending",
        project_path: str | None = None,
    ) -> str:
        """Store a new decision trace.

        Writes to MCP (if available) and always to local.
        Returns the trace ID.
        """
        trace_id = f"trace-{uuid.uuid4().hex[:8]}"

        # Try MCP
        if self._mcp:
            try:
                await self._mcp.call_tool("context_store_trace", {
                    "id": trace_id,
                    "category": category.value,
                    "description": description,
                    "decision": decision,
                    "context": json.dumps(context or {}),
                    "outcome": outcome,
                })
            except Exception as e:
                logger.debug(f"MCP store_trace failed: {e}")

        # Always write local
        if self._memory:
            self._memory.store_local_trace(
                trace_id=trace_id,
                category=category.value,
                description=description,
                decision=decision,
                context=context,
                project_path=project_path or "",
                outcome=outcome,
            )

        return trace_id

    async def update_outcome(
        self,
        trace_id: str,
        outcome: str,
        notes: str | None = None,
    ) -> None:
        """Update the outcome of a stored trace.

        Args:
            trace_id: The trace to update
            outcome: New outcome (e.g., "success", "failure", "partial")
            notes: Optional notes about the outcome
        """
        # Try MCP
        if self._mcp:
            try:
                mcp_args = {"id": trace_id, "outcome": outcome}
                if notes:
                    mcp_args["notes"] = notes
                await self._mcp.call_tool("context_update_outcome", mcp_args)
            except Exception as e:
                logger.debug(f"MCP update_outcome failed: {e}")

        # Always update local
        if self._memory:
            self._memory.update_local_trace_outcome(trace_id, outcome, notes)

    @staticmethod
    def get_recommendation(traces: list[TraceResult]) -> dict:
        """Apply trust thresholds to determine recommendation.

        Returns:
            {
                "action": "use" | "verify" | "new_decision",
                "trace": TraceResult | None,
                "reason": str,
            }
        """
        if not traces:
            return {
                "action": "new_decision",
                "trace": None,
                "reason": "No precedents found",
            }

        # Find the best match (highest confidence with successful outcome)
        successful = [t for t in traces if t.outcome == "success"]
        if not successful:
            return {
                "action": "new_decision",
                "trace": traces[0] if traces else None,
                "reason": "No successful precedents found",
            }

        best = max(successful, key=lambda t: t.confidence)

        if best.confidence > 0.75:
            return {
                "action": "use",
                "trace": best,
                "reason": f"High confidence precedent ({best.confidence:.2f}): {best.decision}",
            }
        elif best.confidence >= 0.60:
            return {
                "action": "verify",
                "trace": best,
                "reason": f"Moderate confidence ({best.confidence:.2f}), verify: {best.decision}",
            }
        else:
            return {
                "action": "new_decision",
                "trace": best,
                "reason": f"Low confidence ({best.confidence:.2f}), decide fresh",
            }
