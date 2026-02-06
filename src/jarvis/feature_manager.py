"""Feature lifecycle manager: tracks features from plan to tested."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Valid status transitions
VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"in_progress"},
    "in_progress": {"implemented", "blocked"},
    "implemented": {"tested"},
    "blocked": {"pending"},
}


@dataclass
class Feature:
    """A single feature in the build plan."""

    id: str
    description: str
    priority: int  # 1 = highest
    status: str = "pending"
    phase: str = "core"
    dependencies: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    attempts: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "phase": self.phase,
            "dependencies": self.dependencies,
            "acceptance_criteria": self.acceptance_criteria,
            "attempts": self.attempts,
            "cost_usd": self.cost_usd,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Feature:
        return cls(
            id=data["id"],
            description=data["description"],
            priority=data.get("priority", 99),
            status=data.get("status", "pending"),
            phase=data.get("phase", "core"),
            dependencies=data.get("dependencies", []),
            acceptance_criteria=data.get("acceptance_criteria", []),
            attempts=data.get("attempts", 0),
            cost_usd=data.get("cost_usd", 0.0),
        )


class FeatureManager:
    """Manages feature lifecycle from plan to tested.

    Features are persisted in .jarvis/feature-list.json within the project.
    Supports topological ordering based on dependencies and priority.
    """

    def __init__(self, project_path: str | Path):
        self._project_path = Path(project_path)
        self._features_path = self._project_path / ".jarvis" / "feature-list.json"
        self._features: dict[str, Feature] = {}

    @property
    def features(self) -> list[Feature]:
        return list(self._features.values())

    def load(self) -> FeatureManager:
        """Load features from disk. Returns self for chaining."""
        if not self._features_path.exists():
            return self
        try:
            data = json.loads(self._features_path.read_text())
            self._features = {
                f["id"]: Feature.from_dict(f) for f in data.get("features", [])
            }
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load features: {e}")
        return self

    def save(self) -> None:
        """Persist features to disk."""
        self._features_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "features": [f.to_dict() for f in self._features.values()],
        }
        self._features_path.write_text(json.dumps(data, indent=2))

    def get_feature(self, feature_id: str) -> Feature | None:
        """Look up a feature by ID."""
        return self._features.get(feature_id)

    def get_next_pending(self) -> Feature | None:
        """Get the next feature ready for implementation.

        Uses topological sort: all dependencies must be tested.
        Then sorts by priority (lowest number = highest priority).
        Returns the first pending feature, or None.
        """
        ready: list[Feature] = []
        for feat in self._features.values():
            if feat.status != "pending":
                continue
            # All deps must be tested
            deps_met = all(
                self._features.get(dep_id) and self._features[dep_id].status == "tested"
                for dep_id in feat.dependencies
            )
            if deps_met:
                ready.append(feat)

        if not ready:
            return None

        ready.sort(key=lambda f: f.priority)
        return ready[0]

    def mark_status(self, feature_id: str, status: str) -> None:
        """Update feature status with transition validation.

        Valid transitions:
            pending -> in_progress
            in_progress -> implemented | blocked
            implemented -> tested
            blocked -> pending
        """
        feat = self._features.get(feature_id)
        if not feat:
            raise ValueError(f"Unknown feature: {feature_id}")

        allowed = VALID_STATUS_TRANSITIONS.get(feat.status, set())
        if status not in allowed:
            raise ValueError(
                f"Invalid transition: {feat.status} -> {status} "
                f"(allowed: {allowed})"
            )

        feat.status = status
        logger.info(f"Feature {feature_id}: {feat.status} -> {status}")

    def progress(self) -> dict:
        """Return progress counts by status."""
        counts = {
            "total": 0,
            "pending": 0,
            "in_progress": 0,
            "implemented": 0,
            "tested": 0,
            "blocked": 0,
        }
        for feat in self._features.values():
            counts["total"] += 1
            if feat.status in counts:
                counts[feat.status] += 1
        return counts

    def create_from_plan(self, plan_json: str | dict) -> None:
        """Parse a plan and create Feature objects.

        Expects JSON with a "subtasks" array, each having:
            id, description, priority, phase, dependencies, acceptance_criteria
        """
        if isinstance(plan_json, str):
            plan_json = json.loads(plan_json)

        subtasks = plan_json.get("subtasks", [])
        for i, task in enumerate(subtasks):
            feature_id = task.get("id", f"feat-{i + 1}")
            feat = Feature(
                id=feature_id,
                description=task.get("description", ""),
                priority=task.get("priority", i + 1),
                phase=task.get("phase", "core"),
                dependencies=task.get("dependencies", []),
                acceptance_criteria=task.get("acceptance_criteria", []),
            )
            self._features[feature_id] = feat

        logger.info(f"Created {len(subtasks)} features from plan")

    def validate_features(self) -> list[str]:
        """Validate feature graph integrity.

        Checks:
        - All IDs unique (enforced by dict)
        - All dependency IDs exist
        - No circular dependencies
        """
        errors: list[str] = []
        all_ids = set(self._features.keys())

        # Check dependency references
        for feat in self._features.values():
            for dep_id in feat.dependencies:
                if dep_id not in all_ids:
                    errors.append(
                        f"Feature '{feat.id}' depends on unknown '{dep_id}'"
                    )

        # Check circular dependencies via DFS
        visited: set[str] = set()
        in_stack: set[str] = set()

        def _dfs(fid: str) -> bool:
            """Returns True if cycle detected."""
            if fid in in_stack:
                return True
            if fid in visited:
                return False
            visited.add(fid)
            in_stack.add(fid)
            feat = self._features.get(fid)
            if feat:
                for dep_id in feat.dependencies:
                    if dep_id in all_ids and _dfs(dep_id):
                        errors.append(
                            f"Circular dependency detected involving '{fid}'"
                        )
                        return True
            in_stack.discard(fid)
            return False

        for fid in all_ids:
            if fid not in visited:
                _dfs(fid)

        return errors
