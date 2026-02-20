"""Model routing for foundation/cloud execution.

Tier 1: Foundation Models (on-device, fast classification)
Tier 2: Cloud (Anthropic/OpenCode execution)
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ModelTier(Enum):
    """Model tier selection."""

    FOUNDATION = "foundation"
    GLM_CLOUD = "glm-4.7"


class TaskComplexity(Enum):
    """Task complexity classification from triage."""

    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    UNKNOWN = "unknown"


@dataclass
class TriageResult:
    """Result of task triage."""

    complexity: TaskComplexity
    suggested_files: list[str]
    estimated_tokens: int
    confidence: float
    reasoning: str


@dataclass
class RoutingDecision:
    """Model routing decision with reasoning."""

    tier: ModelTier
    model: str
    reason: str
    context_filter: list[str] | None = None
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0
    triage: TriageResult | None = None


class ModelRouter:
    """Routes tasks to foundation or cloud based on task shape."""

    def __init__(self):
        self.foundation_available = False
        self._token_savings_total = 0
        self._routing_stats = {
            "foundation": 0,
            "glm": 0,
            "fallback": 0,
            "triage_hits": 0,
        }
        self._foundation_client = None

    async def initialize(self) -> dict[str, Any]:
        """Initialize local tiers (foundation if available)."""
        result: dict[str, Any] = {"foundation": False}

        try:
            from jarvis.foundation_models import get_foundation_client

            self._foundation_client = get_foundation_client()
            available = await self._foundation_client.is_available()
            if available:
                self.foundation_available = True
                result["foundation"] = True
                logger.info("Foundation Models bridge connected")
        except ImportError:
            pass
        except Exception as e:
            logger.debug("Foundation Models check failed: %s", e)

        logger.info("Model router initialized: Foundation=%s", self.foundation_available)
        return result

    async def triage_task(
        self,
        task_description: str,
        context_files: list[str] | None = None,
    ) -> TriageResult:
        """Heuristic task triage with context filtering."""
        triage = self._heuristic_triage(task_description, context_files)
        self._routing_stats["triage_hits"] += 1
        return triage

    def _heuristic_triage(
        self,
        task_description: str,
        context_files: list[str] | None = None,
    ) -> TriageResult:
        task_lower = task_description.lower()

        trivial_keywords = ["fix typo", "add comment", "update string", "format"]
        simple_keywords = ["rename", "lint", "quick fix", "simple change", "small bug"]
        complex_keywords = [
            "refactor",
            "redesign",
            "architecture",
            "implement feature",
            "build",
            "create new",
            "full stack",
            "end to end",
            "migrate",
        ]

        if any(kw in task_lower for kw in trivial_keywords):
            complexity = TaskComplexity.TRIVIAL
        elif any(kw in task_lower for kw in simple_keywords):
            complexity = TaskComplexity.SIMPLE
        elif any(kw in task_lower for kw in complex_keywords):
            complexity = TaskComplexity.COMPLEX
        elif context_files and len(context_files) > 5:
            complexity = TaskComplexity.MODERATE
        else:
            complexity = TaskComplexity.SIMPLE

        suggested = self._heuristic_filter_context(task_description, context_files or [])

        return TriageResult(
            complexity=complexity,
            suggested_files=suggested,
            estimated_tokens=len(suggested) * 1000,
            confidence=0.4,
            reasoning="Heuristic triage",
        )

    async def route_task(
        self,
        task_description: str,
        context_files: list[str] | None = None,
        budget_remaining_usd: float = 1.0,
        offline_mode: bool = False,
    ) -> RoutingDecision:
        """Route task to foundation/cloud tiers."""
        triage = await self.triage_task(task_description, context_files)

        if self._is_classification_task(task_description):
            if self.foundation_available and self._foundation_client:
                try:
                    classification = await self._foundation_client.classify_task_complexity(
                        task_description
                    )
                    self._routing_stats["foundation"] += 1
                    return RoutingDecision(
                        tier=ModelTier.FOUNDATION,
                        model="foundation-models",
                        reason=(
                            f"On-device classification: {classification['label']} "
                            f"({classification['latency_ms']:.0f}ms)"
                        ),
                        estimated_tokens=0,
                        estimated_cost_usd=0.0,
                        triage=triage,
                    )
                except Exception as e:
                    logger.debug("Foundation Models fallthrough: %s", e)

        if offline_mode and not self.foundation_available:
            self._routing_stats["fallback"] += 1
            return RoutingDecision(
                tier=ModelTier.GLM_CLOUD,
                model="unavailable",
                reason="Offline mode: no local model available",
                estimated_tokens=0,
                estimated_cost_usd=0.0,
                triage=triage,
            )

        self._routing_stats["glm"] += 1
        filtered = triage.suggested_files if triage.suggested_files else context_files
        return RoutingDecision(
            tier=ModelTier.GLM_CLOUD,
            model="claude-sonnet-4.5",
            reason=(
                f"Triage: {triage.complexity.value} task, routing to cloud. "
                f"Context: {len(filtered or [])} files"
            ),
            context_filter=filtered,
            estimated_tokens=len(filtered or []) * 1000,
            estimated_cost_usd=0.015 * len(filtered or []),
            triage=triage,
        )

    def _is_classification_task(self, task_description: str) -> bool:
        classification_keywords = [
            "classify",
            "categorize",
            "is this",
            "does this",
            "check if",
            "sentiment",
            "intent",
            "language",
            "framework",
        ]
        task_lower = task_description.lower()
        return any(keyword in task_lower for keyword in classification_keywords)

    def _heuristic_filter_context(self, task_description: str, context_files: list[str]) -> list[str]:
        task_lower = task_description.lower()
        task_words = set(re.findall(r"\b\w+\b", task_lower))

        relevant = []
        for file_path in context_files:
            file_name = file_path.split("/")[-1].lower()
            file_base = file_name.split(".")[0]
            if file_name in task_lower or (len(file_base) >= 2 and file_base in task_words):
                relevant.append(file_path)

        if not relevant:
            return context_files[:3]
        return relevant[:3]

    async def shutdown(self) -> None:
        """Shutdown local resources."""
        if self._foundation_client:
            try:
                await self._foundation_client.close()
            except Exception:
                pass

    def get_stats(self) -> dict[str, Any]:
        total = (
            self._routing_stats["foundation"]
            + self._routing_stats["glm"]
            + self._routing_stats["fallback"]
        )
        stats = {
            "total_routes": total,
            "foundation_pct": (self._routing_stats["foundation"] / total * 100) if total else 0,
            "glm_pct": (self._routing_stats["glm"] / total * 100) if total else 0,
            "fallback_pct": (self._routing_stats["fallback"] / total * 100) if total else 0,
            "triage_hits": self._routing_stats["triage_hits"],
            "token_savings_total": self._token_savings_total,
            "foundation_available": self.foundation_available,
        }
        if self._foundation_client:
            stats["foundation_client"] = self._foundation_client.get_stats()
        return stats

    def enable_local_models(self, foundation: bool = False, **_kwargs) -> None:
        self.foundation_available = foundation
        logger.info("Model router updated: Foundation=%s", foundation)


_router_instance: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    """Get the global model router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ModelRouter()
    return _router_instance
