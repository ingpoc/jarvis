"""Autonomous build harness: state machine that loops through features."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from jarvis.container_templates import detect_template
from jarvis.decision_tracer import DecisionTracer, TraceCategory
from jarvis.feature_manager import FeatureManager

logger = logging.getLogger(__name__)

MAX_FEATURE_ATTEMPTS = 3
MAX_TEST_RETRIES = 3


class HarnessState(Enum):
    """Build harness state machine states."""

    START = "start"
    INIT = "init"
    IMPLEMENT = "implement"
    TEST = "test"
    COMPLETE = "complete"


VALID_TRANSITIONS: dict[HarnessState, set[HarnessState]] = {
    HarnessState.START: {HarnessState.INIT},
    HarnessState.INIT: {HarnessState.IMPLEMENT},
    HarnessState.IMPLEMENT: {HarnessState.TEST, HarnessState.IMPLEMENT},
    HarnessState.TEST: {HarnessState.IMPLEMENT, HarnessState.COMPLETE},
    HarnessState.COMPLETE: set(),
}


@dataclass
class HarnessContext:
    """Runtime context for the build harness."""

    state: HarnessState = HarnessState.START
    feature_id: str | None = None
    attempts: int = 0
    history: list[dict] = field(default_factory=list)
    health_status: str = "unknown"
    project_path: str = ""
    session_id: str = field(default_factory=lambda: f"harness-{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "feature_id": self.feature_id,
            "attempts": self.attempts,
            "history": self.history,
            "health_status": self.health_status,
            "project_path": self.project_path,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> HarnessContext:
        return cls(
            state=HarnessState(data.get("state", "start")),
            feature_id=data.get("feature_id"),
            attempts=data.get("attempts", 0),
            history=data.get("history", []),
            health_status=data.get("health_status", "unknown"),
            project_path=data.get("project_path", ""),
            session_id=data.get("session_id", f"harness-{uuid.uuid4().hex[:8]}"),
        )


class BuildHarness:
    """Autonomous build harness: loops through features via state machine.

    Uses the orchestrator's run_task() and budget.enforce() to drive
    autonomous implementation with safety guardrails.
    """

    def __init__(self, project_path: str, orchestrator):
        self._project_path = Path(project_path)
        self._orchestrator = orchestrator
        self._state_path = self._project_path / ".jarvis" / "state.json"
        self._ctx = self._load_state()
        self._ctx.project_path = project_path
        self._feature_mgr: FeatureManager | None = None

    @property
    def context(self) -> HarnessContext:
        return self._ctx

    def transition(self, target: HarnessState) -> None:
        """Validate and execute a state transition.

        Raises ValueError if transition is not in VALID_TRANSITIONS.
        Persists state to .jarvis/state.json with timestamp.
        """
        allowed = VALID_TRANSITIONS.get(self._ctx.state, set())
        if target not in allowed:
            raise ValueError(
                f"Invalid transition: {self._ctx.state.value} -> {target.value} "
                f"(allowed: {[s.value for s in allowed]})"
            )

        prev = self._ctx.state
        self._ctx.state = target
        self._ctx.history.append({
            "from": prev.value,
            "to": target.value,
            "timestamp": time.time(),
            "feature_id": self._ctx.feature_id,
        })
        self._save_state()
        logger.info(f"Harness: {prev.value} -> {target.value}")

    async def run(self, callback=None) -> dict:
        """Main autonomous loop.

        Runs the state machine until COMPLETE or budget exhausted.

        Args:
            callback: Optional callback(event_type, data) for progress.

        Returns:
            Final harness context as dict.
        """
        self._ctx.health_status = self._health_check()
        if self._ctx.health_status != "healthy":
            logger.error(f"Health check failed: {self._ctx.health_status}")
            return self._ctx.to_dict()

        while self._ctx.state != HarnessState.COMPLETE:
            # Budget gate
            can_continue, reason = self._orchestrator.budget.enforce()
            if not can_continue:
                logger.warning(f"Budget exhausted: {reason}")
                if callback:
                    callback("budget_exhausted", {"reason": reason})
                break

            state = self._ctx.state

            if state == HarnessState.START:
                self.transition(HarnessState.INIT)

            elif state == HarnessState.INIT:
                await self._run_init(callback)

            elif state == HarnessState.IMPLEMENT:
                await self._run_implement(callback)

            elif state == HarnessState.TEST:
                await self._run_test(callback)

        self._save_state()
        return self._ctx.to_dict()

    async def _run_init(self, callback=None) -> None:
        """Initialize: detect template, generate plan, populate features."""
        template = detect_template(self._project_path)
        logger.info(f"Detected template: {template.name}")

        if callback:
            callback("init_started", {"template": template.name})

        # Generate feature plan via orchestrator
        plan_prompt = (
            f"Analyze the project at {self._project_path} (template: {template.name}). "
            f"Create a build plan as JSON with a 'subtasks' array. Each subtask needs: "
            f"id, description, priority (1=highest), phase (foundation/core/enhancement/polish), "
            f"dependencies (list of subtask IDs), acceptance_criteria (list of strings). "
            f"Return ONLY valid JSON, no markdown."
        )

        result = await self._orchestrator.run_task(plan_prompt, callback=callback)

        # Parse plan from result
        self._feature_mgr = FeatureManager(self._project_path)
        plan_text = result.get("output", "")

        try:
            # Try to extract JSON from output
            plan_data = self._extract_json(plan_text)
            self._feature_mgr.create_from_plan(plan_data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Plan parse failed, creating minimal plan: {e}")
            self._feature_mgr.create_from_plan({
                "subtasks": [{
                    "id": "feat-1",
                    "description": "Implement core functionality",
                    "priority": 1,
                    "phase": "core",
                    "dependencies": [],
                    "acceptance_criteria": ["Code compiles", "Basic tests pass"],
                }]
            })

        # Validate and save
        errors = self._feature_mgr.validate_features()
        if errors:
            logger.warning(f"Feature validation errors: {errors}")

        self._feature_mgr.save()

        if callback:
            callback("init_complete", self._feature_mgr.progress())

        self.transition(HarnessState.IMPLEMENT)

    async def _run_implement(self, callback=None) -> None:
        """Implement the next pending feature."""
        if not self._feature_mgr:
            self._feature_mgr = FeatureManager(self._project_path).load()

        feature = self._feature_mgr.get_next_pending()
        if not feature:
            # No more pending features
            self.transition(HarnessState.TEST)
            return

        self._ctx.feature_id = feature.id
        self._ctx.attempts += 1
        self._save_state()

        if callback:
            callback("implement_started", {
                "feature_id": feature.id,
                "description": feature.description,
                "attempt": self._ctx.attempts,
            })

        # Query decision traces for precedents
        precedent_ctx = ""
        try:
            tracer = self._orchestrator.tracer
            precedents = await tracer.query_precedents(
                feature.description,
                category=TraceCategory.TASK_EXECUTION,
                limit=3,
            )
            rec = DecisionTracer.get_recommendation(precedents)
            if rec["action"] != "new_decision" and rec["trace"]:
                trace = rec["trace"]
                precedent_ctx = (
                    f"\n[Precedent] Similar task ({rec['action']}): "
                    f"{trace.description} -> {trace.decision} "
                    f"(outcome: {trace.outcome})"
                )
        except Exception:
            pass

        # Build implementation prompt
        criteria = "\n".join(f"  - {c}" for c in feature.acceptance_criteria)
        impl_prompt = (
            f"Implement feature '{feature.id}': {feature.description}\n"
            f"Phase: {feature.phase}\n"
            f"Acceptance criteria:\n{criteria}\n"
            f"Project path: {self._project_path}"
            f"{precedent_ctx}"
        )

        self._feature_mgr.mark_status(feature.id, "in_progress")
        self._feature_mgr.save()

        result = await self._orchestrator.run_task(impl_prompt, callback=callback)

        if result.get("status") == "completed":
            self._feature_mgr.mark_status(feature.id, "implemented")
            feature.cost_usd += result.get("cost_usd", 0.0)
            self._ctx.attempts = 0
            self._feature_mgr.save()
            if callback:
                callback("implement_success", {"feature_id": feature.id})
        else:
            feature.attempts += 1
            if feature.attempts >= MAX_FEATURE_ATTEMPTS:
                self._feature_mgr.mark_status(feature.id, "blocked")
                self._ctx.attempts = 0
                logger.warning(f"Feature {feature.id} blocked after {MAX_FEATURE_ATTEMPTS} attempts")
                if callback:
                    callback("implement_blocked", {"feature_id": feature.id})
                # Move to TEST to run what we have
                self.transition(HarnessState.TEST)
            else:
                self._feature_mgr.save()
                if callback:
                    callback("implement_retry", {
                        "feature_id": feature.id,
                        "attempt": feature.attempts,
                    })
                # Stay in IMPLEMENT (self-transition)

    async def _run_test(self, callback=None) -> None:
        """Test recently implemented features."""
        if not self._feature_mgr:
            self._feature_mgr = FeatureManager(self._project_path).load()

        implemented = [
            f for f in self._feature_mgr.features
            if f.status == "implemented"
        ]

        if not implemented:
            # Nothing to test - check if more pending features remain
            pending = [f for f in self._feature_mgr.features if f.status == "pending"]
            if pending:
                self.transition(HarnessState.IMPLEMENT)
            else:
                self.transition(HarnessState.COMPLETE)
            return

        if callback:
            callback("test_started", {
                "features": [f.id for f in implemented],
            })

        # Build test prompt
        feature_list = "\n".join(
            f"  - {f.id}: {f.description}" for f in implemented
        )
        test_prompt = (
            f"Run tests for the following implemented features:\n{feature_list}\n"
            f"Project path: {self._project_path}\n"
            f"Verify each feature with exit codes (0 = pass). "
            f"Report which features pass and which fail."
        )

        result = await self._orchestrator.run_task(test_prompt, callback=callback)
        output = result.get("output", "").lower()

        if result.get("status") == "completed":
            # Mark all implemented features as tested on success
            for feat in implemented:
                self._feature_mgr.mark_status(feat.id, "tested")
            self._feature_mgr.save()

            if callback:
                callback("test_success", {
                    "features": [f.id for f in implemented],
                })

            # Check for more pending features
            pending = [f for f in self._feature_mgr.features if f.status == "pending"]
            if pending:
                self.transition(HarnessState.IMPLEMENT)
            else:
                self.transition(HarnessState.COMPLETE)
        else:
            self._ctx.attempts += 1
            if self._ctx.attempts >= MAX_TEST_RETRIES:
                logger.warning(f"Tests failed after {MAX_TEST_RETRIES} retries")
                # Move failed features back to in_progress for retry
                for feat in implemented:
                    # Mark blocked since tests failed repeatedly
                    self._feature_mgr.mark_status(feat.id, "blocked")
                self._feature_mgr.save()
                self._ctx.attempts = 0
                self.transition(HarnessState.COMPLETE)
            else:
                if callback:
                    callback("test_retry", {"attempt": self._ctx.attempts})
                # Stay in TEST for retry

    def _health_check(self) -> str:
        """Verify harness prerequisites.

        Returns 'healthy' or 'unhealthy' with reason.
        """
        if not self._project_path.exists():
            return f"unhealthy: project path does not exist: {self._project_path}"

        jarvis_dir = self._project_path / ".jarvis"
        if not jarvis_dir.exists():
            jarvis_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created .jarvis directory at {jarvis_dir}")

        return "healthy"

    def _save_state(self) -> None:
        """Persist harness state to .jarvis/state.json."""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(self._ctx.to_dict(), indent=2))

    def _load_state(self) -> HarnessContext:
        """Load harness state from .jarvis/state.json, or return fresh context."""
        if self._state_path.exists():
            try:
                data = json.loads(self._state_path.read_text())
                logger.info(f"Resumed harness state: {data.get('state', 'start')}")
                return HarnessContext.from_dict(data)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load state, starting fresh: {e}")
        return HarnessContext()

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract JSON object from text that may contain markdown fences."""
        # Try direct parse first
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code fence
        for marker in ("```json", "```"):
            if marker in text:
                start = text.index(marker) + len(marker)
                end = text.index("```", start)
                return json.loads(text[start:end].strip())

        # Try finding first { to last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1:
            return json.loads(text[first_brace:last_brace + 1])

        raise ValueError("No JSON found in text")
