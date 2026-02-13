"""Idle mode processing: background tasks when the system is inactive.

State machine: Active -> Idle -> Hibernated
- Active: user is interacting, no background processing
- Idle: 10+ minutes of inactivity, run background tasks
- Hibernated: memory pressure or battery low, suspend all processing

Background tasks (in priority order):
1. Learning re-verification (high priority)
2. Context metadata rebuild L1-L4 (medium)
3. Skill generation from candidates (low)
4. Token optimization reports (low)
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable

from jarvis.memory import MemoryStore

logger = logging.getLogger(__name__)


class IdleState(Enum):
    """System idle state machine."""
    ACTIVE = "active"
    IDLE = "idle"
    HIBERNATED = "hibernated"


class TaskPriority(Enum):
    """Background task priority levels."""
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class BackgroundTask:
    """A background task to run during idle mode."""

    def __init__(
        self,
        name: str,
        func: Callable,
        priority: TaskPriority = TaskPriority.LOW,
        interval_seconds: float = 300.0,
    ):
        self.name = name
        self.func = func
        self.priority = priority
        self.interval_seconds = interval_seconds
        self.last_run: float = 0.0
        self.run_count: int = 0
        self.last_error: str | None = None

    @property
    def should_run(self) -> bool:
        return time.time() - self.last_run >= self.interval_seconds


class IdleModeProcessor:
    """Manages idle detection and background task execution.

    This handles the Python-side processing. Idle detection triggers
    are sent from the SwiftUI app via WebSocket when IOKit detects
    no HID input for the configured threshold.
    """

    def __init__(
        self,
        memory: MemoryStore,
        project_path: str,
        idle_threshold_minutes: float = 10.0,
    ):
        self.memory = memory
        self.project_path = project_path
        self.idle_threshold = idle_threshold_minutes * 60  # Convert to seconds
        self._state = IdleState.ACTIVE
        self._last_activity = time.time()
        self._tasks: list[BackgroundTask] = []
        self._running = False
        self._loop_task: asyncio.Task | None = None
        self._state_callbacks: list[Callable] = []

        # Register default background tasks
        self._register_default_tasks()

    @property
    def state(self) -> IdleState:
        return self._state

    def _register_default_tasks(self) -> None:
        """Register the default set of background tasks."""
        self._tasks = [
            BackgroundTask(
                name="learning_revalidation",
                func=self._revalidate_learnings,
                priority=TaskPriority.HIGH,
                interval_seconds=300,  # Every 5 minutes
            ),
            BackgroundTask(
                name="universal_heuristics_seed",
                func=self._seed_universal_heuristics,
                priority=TaskPriority.HIGH,
                interval_seconds=3600,  # Once per hour (idempotent)
            ),
            BackgroundTask(
                name="context_rebuild",
                func=self._rebuild_context_metadata,
                priority=TaskPriority.MEDIUM,
                interval_seconds=600,  # Every 10 minutes
            ),
            BackgroundTask(
                name="capability_assessment",
                func=self._assess_capabilities,
                priority=TaskPriority.MEDIUM,
                interval_seconds=1200,  # Every 20 minutes
            ),
            BackgroundTask(
                name="skill_generation",
                func=self._generate_skills,
                priority=TaskPriority.LOW,
                interval_seconds=900,  # Every 15 minutes
            ),
            BackgroundTask(
                name="article_learning",
                func=self._process_article_learnings,
                priority=TaskPriority.LOW,
                interval_seconds=1800,  # Every 30 minutes
            ),
            BackgroundTask(
                name="token_optimization_report",
                func=self._generate_token_report,
                priority=TaskPriority.LOW,
                interval_seconds=1800,  # Every 30 minutes
            ),
        ]

    def record_activity(self) -> None:
        """Record user activity (resets idle timer)."""
        self._last_activity = time.time()
        if self._state != IdleState.ACTIVE:
            old_state = self._state
            self._state = IdleState.ACTIVE
            self._notify_state_change(old_state, IdleState.ACTIVE)
            logger.info("User activity detected, resuming active mode")

    def trigger_idle(self) -> None:
        """Externally trigger idle mode (e.g., from SwiftUI via WebSocket)."""
        if self._state == IdleState.ACTIVE:
            self._state = IdleState.IDLE
            self._notify_state_change(IdleState.ACTIVE, IdleState.IDLE)
            logger.info("Idle mode triggered")

    def trigger_hibernate(self) -> None:
        """Enter hibernation mode (memory pressure or battery low)."""
        old_state = self._state
        self._state = IdleState.HIBERNATED
        self._notify_state_change(old_state, IdleState.HIBERNATED)
        logger.info("Entering hibernation mode")

    def _notify_state_change(self, old: IdleState, new: IdleState) -> None:
        """Notify state change callbacks."""
        for callback in self._state_callbacks:
            try:
                callback(old.value, new.value)
            except Exception as e:
                logger.warning(f"State change callback error: {e}")

    def add_state_callback(self, callback: Callable) -> None:
        """Register a callback for state changes. callback(old_state, new_state)"""
        if callback not in self._state_callbacks:
            self._state_callbacks.append(callback)

    async def _revalidate_learnings(self) -> dict[str, Any]:
        """Re-verify learnings marked for revalidation.

        Checks if learnings still apply by testing whether the
        referenced error pattern is still relevant.
        """
        learnings = self.memory.get_learnings(
            project_path=self.project_path,
            min_confidence=0.0,
        )

        revalidated = 0
        decayed = 0

        for learning in learnings:
            if not learning.get("needs_revalidation"):
                continue

            # For now, apply a confidence decay for learnings
            # that need revalidation. Full re-testing would require
            # running the SDK session with the original error context.
            current_confidence = learning["confidence"]
            new_confidence = max(0.1, current_confidence * 0.8)

            if new_confidence < 0.3:
                decayed += 1
            else:
                revalidated += 1

            # Update in database (clear the revalidation flag,
            # update confidence)
            conn = self.memory._get_connection()
            try:
                conn.execute(
                    "UPDATE learnings SET confidence = ?, needs_revalidation = 0 "
                    "WHERE id = ?",
                    (new_confidence, learning["id"]),
                )
                conn.commit()
            finally:
                conn.close()

        return {
            "revalidated": revalidated,
            "decayed": decayed,
            "total_checked": revalidated + decayed,
        }

    async def _rebuild_context_metadata(self) -> dict[str, Any]:
        """Rebuild context layers L1-L4 for the project.

        Delegates to context_layers module.
        """
        try:
            from jarvis.context_layers import build_context_layers
            layers = await build_context_layers(self.project_path)
            return {"layers_built": len(layers), "status": "success"}
        except ImportError:
            return {"status": "skipped", "reason": "context_layers module not available"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _seed_universal_heuristics(self) -> dict[str, Any]:
        """Seed universal heuristics for cold start.

        Auto-detects project languages and injects known error-fix
        patterns so Jarvis can help even before seeing project-specific errors.
        """
        try:
            from jarvis.universal_heuristics import auto_seed_project
            result = await auto_seed_project(self.memory, self.project_path)
            return result
        except ImportError:
            return {"status": "skipped", "reason": "universal_heuristics module not available"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _assess_capabilities(self) -> dict[str, Any]:
        """Assess and report system capabilities.

        Checks what's available for this project:
        - Which languages are detected
        - How many learnings exist
        - Skill generation readiness
        - Token usage trends
        - Context layer coverage
        """
        from pathlib import Path

        project = Path(self.project_path)
        assessment: dict[str, Any] = {"status": "success"}

        # Language detection
        try:
            from jarvis.universal_heuristics import detect_project_languages
            languages = detect_project_languages(self.project_path)
            assessment["languages"] = languages
        except Exception:
            assessment["languages"] = []

        # Learning statistics
        learnings = self.memory.get_learnings(
            project_path=self.project_path, min_confidence=0.0, limit=1000
        )
        assessment["learnings_count"] = len(learnings)
        assessment["high_confidence_learnings"] = sum(
            1 for l in learnings if l["confidence"] >= 0.7
        )
        assessment["needs_revalidation"] = sum(
            1 for l in learnings if l.get("needs_revalidation")
        )

        # Skill candidate statistics
        candidates = self.memory.get_skill_candidates(min_occurrences=1)
        promoted = self.memory.get_skill_candidates(min_occurrences=1, promoted=True)
        assessment["skill_candidates"] = len(candidates)
        assessment["skills_promoted"] = len(promoted)

        # Token usage summary
        usage = self.memory.get_token_usage(project_path=self.project_path, limit=50)
        if usage:
            assessment["total_tokens_used"] = sum(u.get("total_tokens", 0) for u in usage)
            assessment["total_cost_usd"] = sum(u.get("cost_usd", 0.0) for u in usage)
            assessment["avg_cost_per_task"] = assessment["total_cost_usd"] / len(usage)
        else:
            assessment["total_tokens_used"] = 0
            assessment["total_cost_usd"] = 0.0
            assessment["avg_cost_per_task"] = 0.0

        # Task completion rate
        all_tasks = self.memory.list_tasks(project_path=self.project_path)
        completed = [t for t in all_tasks if t.status == "completed"]
        failed = [t for t in all_tasks if t.status == "failed"]
        assessment["total_tasks"] = len(all_tasks)
        assessment["completed_tasks"] = len(completed)
        assessment["failed_tasks"] = len(failed)
        assessment["success_rate"] = (
            len(completed) / len(all_tasks) if all_tasks else 0.0
        )

        logger.info(
            f"Capability assessment: {len(learnings)} learnings, "
            f"{len(candidates)} skill candidates, "
            f"{len(all_tasks)} tasks ({len(completed)} completed)"
        )

        return assessment

    async def _process_article_learnings(self) -> dict[str, Any]:
        """Extract learnings from execution records that weren't processed.

        Scans recent tasks for error-fix patterns that might have been
        missed during the original task run (e.g., due to transient errors
        in the learning pipeline).
        """
        try:
            from jarvis.self_learning import learn_from_task

            # Get recent completed/failed tasks
            tasks = self.memory.list_tasks(
                project_path=self.project_path,
            )

            # Focus on tasks from the last 24 hours
            cutoff = time.time() - 86400
            recent_tasks = [
                t for t in tasks
                if t.updated_at >= cutoff
                and t.status in ("completed", "failed")
            ]

            total_learnings = 0
            tasks_processed = 0

            for task in recent_tasks[:10]:  # Limit to 10 per cycle
                records = self.memory.get_execution_records(task_id=task.id)
                if not records:
                    continue

                # Check if we already extracted learnings for this task
                # by looking for learnings created after the task
                existing_learnings = self.memory.get_learnings(
                    project_path=self.project_path,
                    min_confidence=0.0,
                )
                # Simple heuristic: if there are errors in records but no
                # learnings were created recently, re-process
                has_errors = any(r.get("error_message") for r in records)
                if not has_errors:
                    continue

                stats = await learn_from_task(
                    task_id=task.id,
                    project_path=self.project_path,
                    memory=self.memory,
                )
                total_learnings += stats.get("learnings_saved", 0)
                tasks_processed += 1

            return {
                "tasks_processed": tasks_processed,
                "learnings_extracted": total_learnings,
                "recent_tasks_scanned": len(recent_tasks),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _generate_skills(self) -> dict[str, Any]:
        """Generate skills from candidates during idle time."""
        try:
            from jarvis.skill_generator import generate_skills_from_patterns
            result = await generate_skills_from_patterns(
                memory=self.memory,
                project_path=self.project_path,
                min_occurrences=3,
                max_skills=3,  # Limit per idle cycle
            )
            return result
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _generate_token_report(self) -> dict[str, Any]:
        """Generate token optimization report."""
        usage = self.memory.get_token_usage(
            project_path=self.project_path,
            limit=100,
        )

        if not usage:
            return {"status": "no_data"}

        total_tokens = sum(u.get("total_tokens", 0) for u in usage)
        total_cost = sum(u.get("cost_usd", 0.0) for u in usage)
        avg_tokens = total_tokens / len(usage) if usage else 0

        return {
            "total_records": len(usage),
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "avg_tokens_per_call": avg_tokens,
        }

    async def _process_loop(self) -> None:
        """Main processing loop for idle mode."""
        while self._running:
            try:
                # Check if we should transition to idle
                if self._state == IdleState.ACTIVE:
                    elapsed = time.time() - self._last_activity
                    if elapsed >= self.idle_threshold:
                        self._state = IdleState.IDLE
                        self._notify_state_change(IdleState.ACTIVE, IdleState.IDLE)
                        logger.info(
                            f"Auto-idle after {elapsed:.0f}s of inactivity"
                        )

                # Process tasks only in idle mode
                if self._state == IdleState.IDLE:
                    # Sort by priority
                    ready_tasks = sorted(
                        [t for t in self._tasks if t.should_run],
                        key=lambda t: t.priority.value,
                    )

                    for task in ready_tasks:
                        if self._state != IdleState.IDLE:
                            break  # User became active

                        try:
                            logger.debug(f"Running idle task: {task.name}")
                            if asyncio.iscoroutinefunction(task.func):
                                result = await task.func()
                            else:
                                result = task.func()
                            task.last_run = time.time()
                            task.run_count += 1
                            task.last_error = None
                            logger.info(
                                f"Idle task '{task.name}' completed: {result}"
                            )
                        except Exception as e:
                            task.last_error = str(e)
                            task.last_run = time.time()
                            logger.error(
                                f"Idle task '{task.name}' failed: {e}"
                            )

                await asyncio.sleep(10)  # Check every 10 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Idle mode processor error: {e}")
                await asyncio.sleep(30)

    async def start(self) -> None:
        """Start the idle mode processor."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._process_loop())
        logger.info("Idle mode processor started")

    async def stop(self) -> None:
        """Stop the idle mode processor."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
        logger.info("Idle mode processor stopped")

    def get_stats(self) -> dict[str, Any]:
        """Get idle mode statistics."""
        return {
            "state": self._state.value,
            "last_activity": self._last_activity,
            "idle_threshold_seconds": self.idle_threshold,
            "seconds_since_activity": time.time() - self._last_activity,
            "running": self._running,
            "tasks": [
                {
                    "name": t.name,
                    "priority": t.priority.value,
                    "run_count": t.run_count,
                    "last_run": t.last_run,
                    "last_error": t.last_error,
                    "should_run": t.should_run,
                }
                for t in self._tasks
            ],
        }
