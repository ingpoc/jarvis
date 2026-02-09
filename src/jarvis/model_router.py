"""Model routing: 3-tier intelligence system for optimal cost/latency/quality.

Tier 1: Qwen3 4B (Local MLX) - Fast, cheap, private
  - Task classification
  - Context pre-filtering (file selection)
  - Simple queries that fit in 4K context
  - Offline fallback

Tier 2: GLM 4.7 (Cloud API) - Powerful, 200K context, thinking mode
  - Complex coding tasks
  - Multi-file refactoring
  - Skill generation
  - Primary task execution

Tier 3: Foundation Models (macOS) - Ultra-fast classification
  - Intent classification
  - Quick categorization (<4K context)
  - Sentiment analysis

Router Logic:
1. Use Foundation Models for quick classification (<100ms)
2. Use Qwen3 for simple tasks and context filtering (200-500ms)
3. Use GLM 4.7 for everything else
4. Fallback: GLM always available if local models fail
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ModelTier(Enum):
    """Model tier selection."""
    FOUNDATION = "foundation"  # macOS Foundation Models
    QWEN3_LOCAL = "qwen3-4b"   # Local MLX inference
    GLM_CLOUD = "glm-4.7"      # Cloud API (Claude)


@dataclass
class RoutingDecision:
    """Model routing decision with reasoning."""
    tier: ModelTier
    model: str
    reason: str
    context_filter: list[str] | None = None  # Files to include (if pre-filtered)
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0


class ModelRouter:
    """Routes tasks to appropriate model tier based on complexity."""

    def __init__(self):
        self.qwen3_available = False  # Will be True when MLX integration complete
        self.foundation_available = False  # Will be True when XPC bridge complete
        self._token_savings_total = 0
        self._routing_stats = {
            "foundation": 0,
            "qwen3": 0,
            "glm": 0,
            "fallback": 0,
        }

    async def route_task(
        self,
        task_description: str,
        context_files: list[str] | None = None,
        budget_remaining_usd: float = 1.0,
        offline_mode: bool = False,
    ) -> RoutingDecision:
        """Route a task to the appropriate model tier.

        Args:
            task_description: Natural language task description
            context_files: Available context files
            budget_remaining_usd: Remaining budget for this session
            offline_mode: If True, only use local models

        Returns:
            RoutingDecision with tier, model, and reasoning
        """
        # Check if this is a simple classification task
        if self._is_classification_task(task_description):
            if self.foundation_available:
                self._routing_stats["foundation"] += 1
                return RoutingDecision(
                    tier=ModelTier.FOUNDATION,
                    model="foundation-models",
                    reason="Simple classification task (<4K context)",
                    estimated_tokens=1000,
                    estimated_cost_usd=0.0,  # Local, no cost
                )

        # Check if this is a simple task that fits in Qwen3's 4K window
        if self._is_simple_task(task_description, context_files):
            if self.qwen3_available:
                # Use Qwen3 for context pre-filtering
                filtered_files = await self._qwen3_filter_context(
                    task_description, context_files or []
                )
                self._routing_stats["qwen3"] += 1
                token_savings = len(context_files or []) - len(filtered_files or [])
                self._token_savings_total += token_savings * 1000  # Approx 1K per file

                return RoutingDecision(
                    tier=ModelTier.QWEN3_LOCAL,
                    model="qwen3-4b-mlx",
                    reason=f"Simple task, local execution. Filtered {len(context_files or [])} → {len(filtered_files or [])} files",
                    context_filter=filtered_files,
                    estimated_tokens=len(filtered_files or []) * 1000,
                    estimated_cost_usd=0.0,  # Local, no cost
                )

        # Complex task or offline unavailable → use GLM (Claude)
        if offline_mode and not self.qwen3_available:
            # Can't execute offline without local models
            self._routing_stats["fallback"] += 1
            return RoutingDecision(
                tier=ModelTier.GLM_CLOUD,
                model="claude-sonnet-4.5",
                reason="Offline mode requested but no local models available (fallback)",
                estimated_tokens=len(context_files or []) * 1000,
                estimated_cost_usd=0.015 * len(context_files or []),  # Rough estimate
            )

        # Default: use GLM for complex tasks
        self._routing_stats["glm"] += 1
        return RoutingDecision(
            tier=ModelTier.GLM_CLOUD,
            model="claude-sonnet-4.5",
            reason="Complex task requiring full context and 200K window",
            estimated_tokens=len(context_files or []) * 1000,
            estimated_cost_usd=0.015 * len(context_files or []),
        )

    def _is_classification_task(self, task_description: str) -> bool:
        """Check if task is a simple classification (Foundation Models capable)."""
        classification_keywords = [
            "classify", "categorize", "is this", "does this", "check if",
            "sentiment", "intent", "language", "framework",
        ]
        task_lower = task_description.lower()
        return any(keyword in task_lower for keyword in classification_keywords)

    def _is_simple_task(self, task_description: str, context_files: list[str] | None) -> bool:
        """Check if task is simple enough for Qwen3 4B (4K context limit)."""
        # Must fit in 4K tokens (~3 files max)
        if context_files and len(context_files) > 3:
            return False

        # Check for complexity signals
        simple_keywords = [
            "fix typo", "add comment", "rename", "format", "lint",
            "simple change", "quick fix", "update string",
        ]
        complex_keywords = [
            "refactor", "redesign", "architecture", "implement feature",
            "build", "create new", "full stack", "end to end",
        ]

        task_lower = task_description.lower()

        # Explicitly simple
        if any(keyword in task_lower for keyword in simple_keywords):
            return True

        # Explicitly complex
        if any(keyword in task_lower for keyword in complex_keywords):
            return False

        # Default: if context is small, consider simple
        return len(context_files or []) <= 2

    async def _qwen3_filter_context(
        self, task_description: str, context_files: list[str]
    ) -> list[str]:
        """Use Qwen3 to filter context files to only relevant ones.

        This is a stub - will be implemented when MLX integration is complete.
        For now, use simple heuristics.
        """
        if not self.qwen3_available:
            # Fallback: simple keyword matching
            return self._heuristic_filter_context(task_description, context_files)

        # TODO: Implement actual Qwen3 inference via MLX
        # For now, return heuristic filter
        return self._heuristic_filter_context(task_description, context_files)

    def _heuristic_filter_context(
        self, task_description: str, context_files: list[str]
    ) -> list[str]:
        """Heuristic context filtering based on keywords.

        This is a placeholder until Qwen3 is integrated.
        """
        # Extract potential file names from task description
        task_lower = task_description.lower()

        # Look for explicit file mentions
        relevant = []
        for file_path in context_files:
            file_name = file_path.split("/")[-1].lower()
            file_base = file_name.split(".")[0]

            # Check if file name mentioned in task
            if file_name in task_lower or file_base in task_lower:
                relevant.append(file_path)

        # If no explicit mentions, return all files (up to limit)
        if not relevant:
            return context_files[:3]  # Max 3 files for 4K context

        return relevant[:3]

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        total = sum(self._routing_stats.values())
        return {
            "total_routes": total,
            "foundation_pct": (self._routing_stats["foundation"] / total * 100) if total else 0,
            "qwen3_pct": (self._routing_stats["qwen3"] / total * 100) if total else 0,
            "glm_pct": (self._routing_stats["glm"] / total * 100) if total else 0,
            "fallback_pct": (self._routing_stats["fallback"] / total * 100) if total else 0,
            "token_savings_total": self._token_savings_total,
            "qwen3_available": self.qwen3_available,
            "foundation_available": self.foundation_available,
        }

    def enable_local_models(self, qwen3: bool = False, foundation: bool = False) -> None:
        """Enable local model tiers (called when MLX/Foundation Models ready)."""
        self.qwen3_available = qwen3
        self.foundation_available = foundation
        logger.info(
            f"Model router updated: Qwen3={qwen3}, Foundation={foundation}"
        )


# Singleton router instance
_router_instance: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    """Get the global model router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ModelRouter()
    return _router_instance
