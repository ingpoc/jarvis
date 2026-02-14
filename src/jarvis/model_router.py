"""Model routing: 3-tier intelligence system for optimal cost/latency/quality.

Tier 1: Qwen3 4B (Local MLX) - Fast, cheap, private
  - Task classification and triage
  - Context pre-filtering (file selection)
  - Simple queries that fit in 4K context
  - Offline fallback
  - Error summarization

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
2. Use Qwen3 for triage, simple tasks, and context filtering (200-500ms)
3. Use GLM 4.7 for everything else
4. Fallback: GLM always available if local models fail
"""

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


class TaskComplexity(Enum):
    """Task complexity classification from triage."""
    TRIVIAL = "trivial"       # Typo fix, comment add, simple rename
    SIMPLE = "simple"         # Single-file change, small bug fix
    MODERATE = "moderate"     # Multi-file change, feature addition
    COMPLEX = "complex"       # Architecture change, refactoring
    UNKNOWN = "unknown"       # Could not classify


@dataclass
class TriageResult:
    """Result of Qwen3 task triage."""
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
    context_filter: list[str] | None = None  # Files to include (if pre-filtered)
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0
    triage: TriageResult | None = None


class ModelRouter:
    """Routes tasks to appropriate model tier based on complexity.

    On Apple Silicon with MLX installed, automatically loads Qwen3 4B
    for local inference. On macOS with JarvisApp running, connects to
    Foundation Models for ultra-fast classification.

    Enhanced with Qwen3 triage: before routing to cloud, Qwen3 analyzes
    the task to determine complexity and pre-filter context.
    """

    def __init__(self):
        self.qwen3_available = False
        self.foundation_available = False
        self._token_savings_total = 0
        self._routing_stats = {
            "foundation": 0,
            "qwen3": 0,
            "glm": 0,
            "fallback": 0,
            "triage_hits": 0,
        }

        # MLX engine (lazy-loaded)
        self._mlx_engine = None
        # Foundation Models client (lazy-loaded)
        self._foundation_client = None

    async def initialize(self) -> dict[str, Any]:
        """Initialize local model tiers (call once at startup).

        Probes for MLX and Foundation Models availability and loads
        the local model if MLX is present.

        Returns stats about what was initialized.
        """
        result: dict[str, Any] = {"mlx": False, "foundation": False}

        # Try MLX / Qwen3
        try:
            from jarvis.mlx_inference import get_mlx_engine, is_mlx_available
            if is_mlx_available():
                self._mlx_engine = get_mlx_engine()
                loaded = await self._mlx_engine.load_model()
                if loaded:
                    self.qwen3_available = True
                    result["mlx"] = True
                    result["mlx_model"] = self._mlx_engine.model_name
                    logger.info("MLX Qwen3 model loaded — Tier 1 active")
        except ImportError:
            logger.info("MLX not available on this platform")
        except Exception as e:
            logger.warning(f"MLX initialization failed: {e}")

        # Try Foundation Models
        try:
            from jarvis.foundation_models import get_foundation_client
            self._foundation_client = get_foundation_client()
            available = await self._foundation_client.is_available()
            if available:
                self.foundation_available = True
                result["foundation"] = True
                logger.info("Foundation Models bridge connected — Tier 3 active")
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Foundation Models check failed: {e}")

        logger.info(
            f"Model router initialized: Qwen3={self.qwen3_available}, "
            f"Foundation={self.foundation_available}"
        )
        return result

    async def triage_task(
        self,
        task_description: str,
        context_files: list[str] | None = None,
    ) -> TriageResult:
        """Use Qwen3 to triage a task before routing.

        Classifies task complexity and suggests relevant files.
        Falls back to heuristic triage if Qwen3 is unavailable.
        """
        # Try Qwen3-based triage
        if self.qwen3_available and self._mlx_engine and self._mlx_engine.loaded:
            try:
                classification = await self._mlx_engine.classify_task(task_description)
                complexity_map = {
                    "trivial": TaskComplexity.TRIVIAL,
                    "simple": TaskComplexity.SIMPLE,
                    "moderate": TaskComplexity.MODERATE,
                    "complex": TaskComplexity.COMPLEX,
                }
                complexity = complexity_map.get(
                    classification.get("complexity", "unknown"),
                    TaskComplexity.UNKNOWN,
                )

                # Filter context files
                suggested_files = context_files or []
                if context_files and len(context_files) > 3:
                    suggested_files = await self._mlx_filter_context(
                        task_description, context_files
                    )

                self._routing_stats["triage_hits"] += 1
                return TriageResult(
                    complexity=complexity,
                    suggested_files=suggested_files,
                    estimated_tokens=len(suggested_files) * 1000,
                    confidence=classification.get("confidence", 0.5),
                    reasoning=classification.get("reasoning", "Qwen3 triage"),
                )
            except Exception as e:
                logger.debug(f"Qwen3 triage failed, using heuristic: {e}")

        # Heuristic fallback triage
        return self._heuristic_triage(task_description, context_files)

    def _heuristic_triage(
        self,
        task_description: str,
        context_files: list[str] | None = None,
    ) -> TriageResult:
        """Heuristic-based task triage fallback."""
        task_lower = task_description.lower()

        trivial_keywords = ["fix typo", "add comment", "update string", "format"]
        simple_keywords = ["rename", "lint", "quick fix", "simple change", "small bug"]
        complex_keywords = [
            "refactor", "redesign", "architecture", "implement feature",
            "build", "create new", "full stack", "end to end", "migrate",
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

        suggested = self._heuristic_filter_context(
            task_description, context_files or []
        )

        return TriageResult(
            complexity=complexity,
            suggested_files=suggested,
            estimated_tokens=len(suggested) * 1000,
            confidence=0.4,
            reasoning="Heuristic triage (Qwen3 unavailable)",
        )

    async def route_task(
        self,
        task_description: str,
        context_files: list[str] | None = None,
        budget_remaining_usd: float = 1.0,
        offline_mode: bool = False,
    ) -> RoutingDecision:
        """Route a task to the appropriate model tier.

        Enhanced with Qwen3 triage: tasks are pre-classified before
        routing to determine the optimal model tier.

        Args:
            task_description: Natural language task description
            context_files: Available context files
            budget_remaining_usd: Remaining budget for this session
            offline_mode: If True, only use local models

        Returns:
            RoutingDecision with tier, model, and reasoning
        """
        # Step 1: Triage the task
        triage = await self.triage_task(task_description, context_files)

        # Tier 3: Foundation Models for classification tasks
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
                        reason=f"On-device classification: {classification['label']} "
                               f"({classification['latency_ms']:.0f}ms)",
                        estimated_tokens=0,
                        estimated_cost_usd=0.0,
                        triage=triage,
                    )
                except Exception as e:
                    logger.debug(f"Foundation Models fallthrough: {e}")

        # Tier 1: Qwen3 for trivial/simple tasks (determined by triage)
        if triage.complexity in (TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE):
            if self.qwen3_available and self._mlx_engine:
                try:
                    self._routing_stats["qwen3"] += 1
                    token_savings = len(context_files or []) - len(triage.suggested_files)
                    self._token_savings_total += token_savings * 1000

                    return RoutingDecision(
                        tier=ModelTier.QWEN3_LOCAL,
                        model="qwen3-4b-mlx",
                        reason=f"Triage: {triage.complexity.value} task. "
                               f"Filtered {len(context_files or [])} → "
                               f"{len(triage.suggested_files)} files",
                        context_filter=triage.suggested_files,
                        estimated_tokens=triage.estimated_tokens,
                        estimated_cost_usd=0.0,
                        triage=triage,
                    )
                except Exception as e:
                    logger.debug(f"Qwen3 fallthrough: {e}")

        # Offline mode: must use local models
        if offline_mode:
            if self.qwen3_available and self._mlx_engine:
                self._routing_stats["qwen3"] += 1
                return RoutingDecision(
                    tier=ModelTier.QWEN3_LOCAL,
                    model="qwen3-4b-mlx",
                    reason="Offline mode: routing to local Qwen3 model",
                    context_filter=triage.suggested_files,
                    estimated_tokens=triage.estimated_tokens,
                    estimated_cost_usd=0.0,
                    triage=triage,
                )
            else:
                self._routing_stats["fallback"] += 1
                return RoutingDecision(
                    tier=ModelTier.GLM_CLOUD,
                    model="unavailable",
                    reason="Offline mode: no local models available, task cannot be executed offline",
                    estimated_tokens=0,
                    estimated_cost_usd=0.0,
                    triage=triage,
                )

        # Tier 2: Cloud API for moderate/complex tasks
        self._routing_stats["glm"] += 1

        # Use triage-filtered context for cloud too (save tokens)
        filtered = triage.suggested_files if triage.suggested_files else context_files

        return RoutingDecision(
            tier=ModelTier.GLM_CLOUD,
            model="claude-sonnet-4.5",
            reason=f"Triage: {triage.complexity.value} task, routing to cloud. "
                   f"Context: {len(filtered or [])} files",
            context_filter=filtered,
            estimated_tokens=len(filtered or []) * 1000,
            estimated_cost_usd=0.015 * len(filtered or []),
            triage=triage,
        )

    def _is_classification_task(self, task_description: str) -> bool:
        """Check if task is a simple classification (Foundation Models capable)."""
        classification_keywords = [
            "classify", "categorize", "is this", "does this", "check if",
            "sentiment", "intent", "language", "framework",
        ]
        task_lower = task_description.lower()
        return any(keyword in task_lower for keyword in classification_keywords)

    async def _mlx_filter_context(
        self, task_description: str, context_files: list[str]
    ) -> list[str]:
        """Use MLX Qwen3 to filter context files to only relevant ones."""
        if self.qwen3_available and self._mlx_engine and self._mlx_engine.loaded:
            try:
                return await self._mlx_engine.filter_context_files(
                    task_description, context_files, max_files=3
                )
            except Exception as e:
                logger.debug(f"MLX context filter failed, using heuristic: {e}")

        return self._heuristic_filter_context(task_description, context_files)

    def _heuristic_filter_context(
        self, task_description: str, context_files: list[str]
    ) -> list[str]:
        """Heuristic context filtering based on keywords (fallback)."""
        task_lower = task_description.lower()

        relevant = []
        for file_path in context_files:
            file_name = file_path.split("/")[-1].lower()
            file_base = file_name.split(".")[0]

            if file_name in task_lower or file_base in task_lower:
                relevant.append(file_path)

        if not relevant:
            return context_files[:3]

        return relevant[:3]

    async def shutdown(self) -> None:
        """Shutdown local models (free memory)."""
        if self._mlx_engine and self._mlx_engine.loaded:
            await self._mlx_engine.unload_model()
            self.qwen3_available = False
            logger.info("MLX model unloaded")

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        total = sum(self._routing_stats.values())
        stats = {
            "total_routes": total,
            "foundation_pct": (self._routing_stats["foundation"] / total * 100) if total else 0,
            "qwen3_pct": (self._routing_stats["qwen3"] / total * 100) if total else 0,
            "glm_pct": (self._routing_stats["glm"] / total * 100) if total else 0,
            "fallback_pct": (self._routing_stats["fallback"] / total * 100) if total else 0,
            "triage_hits": self._routing_stats["triage_hits"],
            "token_savings_total": self._token_savings_total,
            "qwen3_available": self.qwen3_available,
            "foundation_available": self.foundation_available,
        }

        # Add engine-specific stats
        if self._mlx_engine:
            stats["mlx"] = self._mlx_engine.get_stats()
        if self._foundation_client:
            stats["foundation_client"] = self._foundation_client.get_stats()

        return stats

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
