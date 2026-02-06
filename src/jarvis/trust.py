"""Trust engine: 5-tier graduated autonomy system (T0-T4).

Solves the "constantly reminding" problem by earning trust through
successful task completions and de-escalating on failures.
"""

import json
import sqlite3
import time
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

from jarvis.config import JARVIS_DB, JARVIS_HOME


class TrustTier(IntEnum):
    """Trust levels from Observer to Autonomous."""

    OBSERVER = 0      # Read-only
    ASSISTANT = 1     # Edit files, run tests
    DEVELOPER = 2     # + git commit, install packages, run servers
    TRUSTED_DEV = 3   # + git push, create PRs
    AUTONOMOUS = 4    # Everything local, only prod deploys need approval


# Actions that require specific trust tiers
TIER_REQUIREMENTS: dict[str, TrustTier] = {
    # T0: Observer can do these
    "read_file": TrustTier.OBSERVER,
    "search_code": TrustTier.OBSERVER,
    "analyze": TrustTier.OBSERVER,
    # T1: Assistant
    "edit_file": TrustTier.ASSISTANT,
    "run_tests": TrustTier.ASSISTANT,
    "lint": TrustTier.ASSISTANT,
    "format": TrustTier.ASSISTANT,
    # T2: Developer
    "git_commit": TrustTier.DEVELOPER,
    "install_package": TrustTier.DEVELOPER,
    "run_server": TrustTier.DEVELOPER,
    "container_run": TrustTier.DEVELOPER,
    "container_exec": TrustTier.DEVELOPER,
    # T3: Trusted Dev
    "git_push": TrustTier.TRUSTED_DEV,
    "create_pr": TrustTier.TRUSTED_DEV,
    "run_any_command": TrustTier.TRUSTED_DEV,
    # T4: Autonomous
    "deploy_staging": TrustTier.AUTONOMOUS,
}

# Always requires human approval regardless of trust tier
ALWAYS_APPROVE = {"deploy_production", "modify_ci_cd", "delete_branch_main"}


@dataclass
class TrustScore:
    """Per-project trust tracking."""

    project_path: str
    tier: TrustTier
    successful_tasks: int = 0
    total_tasks: int = 0
    rollbacks: int = 0
    consecutive_successes: int = 0
    last_rollback_time: float = 0.0


class TrustEngine:
    """Manages trust tiers with earned escalation."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or JARVIS_DB
        self._init_db()

    def _init_db(self) -> None:
        JARVIS_HOME.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trust_scores (
                project_path TEXT PRIMARY KEY,
                tier INTEGER DEFAULT 1,
                successful_tasks INTEGER DEFAULT 0,
                total_tasks INTEGER DEFAULT 0,
                rollbacks INTEGER DEFAULT 0,
                consecutive_successes INTEGER DEFAULT 0,
                last_rollback_time REAL DEFAULT 0.0
            )
        """)
        conn.commit()
        conn.close()

    def get_score(self, project_path: str) -> TrustScore:
        """Get trust score for a project."""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT * FROM trust_scores WHERE project_path = ?",
            (project_path,),
        ).fetchone()
        conn.close()

        if row:
            return TrustScore(
                project_path=row[0],
                tier=TrustTier(row[1]),
                successful_tasks=row[2],
                total_tasks=row[3],
                rollbacks=row[4],
                consecutive_successes=row[5],
                last_rollback_time=row[6],
            )

        # New project defaults to T1
        score = TrustScore(project_path=project_path, tier=TrustTier.ASSISTANT)
        self._save_score(score)
        return score

    def _save_score(self, score: TrustScore) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO trust_scores
            (project_path, tier, successful_tasks, total_tasks, rollbacks,
             consecutive_successes, last_rollback_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            score.project_path, int(score.tier), score.successful_tasks,
            score.total_tasks, score.rollbacks, score.consecutive_successes,
            score.last_rollback_time,
        ))
        conn.commit()
        conn.close()

    def can_perform(self, project_path: str, action: str) -> tuple[bool, str]:
        """Check if an action is allowed at the current trust tier.

        Returns (allowed, reason).
        """
        if action in ALWAYS_APPROVE:
            return False, f"'{action}' always requires human approval"

        required_tier = TIER_REQUIREMENTS.get(action)
        if required_tier is None:
            # Unknown action - default to T2 requirement
            required_tier = TrustTier.DEVELOPER

        score = self.get_score(project_path)

        if score.tier >= required_tier:
            return True, f"Allowed at T{score.tier} (requires T{required_tier})"

        return False, (
            f"Action '{action}' requires T{required_tier} ({TrustTier(required_tier).name}), "
            f"current tier is T{score.tier} ({score.tier.name}). "
            f"Complete {10 - score.consecutive_successes} more tasks to earn upgrade."
        )

    def record_success(self, project_path: str) -> str | None:
        """Record a successful task. Returns upgrade message if tier escalated."""
        score = self.get_score(project_path)
        score.successful_tasks += 1
        score.total_tasks += 1
        score.consecutive_successes += 1

        upgrade_msg = None

        # Auto-escalation: 10 consecutive successes
        if score.consecutive_successes >= 10 and score.tier < TrustTier.AUTONOMOUS:
            old_tier = score.tier
            score.tier = TrustTier(int(score.tier) + 1)
            score.consecutive_successes = 0
            upgrade_msg = (
                f"Trust upgraded: T{old_tier} ({TrustTier(old_tier).name}) -> "
                f"T{score.tier} ({score.tier.name}) after 10 consecutive successes"
            )

        self._save_score(score)
        return upgrade_msg

    def record_failure(self, project_path: str) -> None:
        """Record a task failure (not a rollback, just a failure)."""
        score = self.get_score(project_path)
        score.total_tasks += 1
        score.consecutive_successes = 0
        self._save_score(score)

    def record_rollback(self, project_path: str) -> str | None:
        """Record a rollback. Returns downgrade message if tier dropped."""
        score = self.get_score(project_path)
        score.rollbacks += 1
        score.consecutive_successes = 0
        score.last_rollback_time = time.time()

        downgrade_msg = None

        # 2+ rollbacks in session -> drop one tier
        recent_rollbacks = score.rollbacks  # Simplified; full impl would track per-session
        if recent_rollbacks >= 2 and score.tier > TrustTier.OBSERVER:
            old_tier = score.tier
            score.tier = TrustTier(int(score.tier) - 1)
            downgrade_msg = (
                f"Trust downgraded: T{old_tier} ({TrustTier(old_tier).name}) -> "
                f"T{score.tier} ({score.tier.name}) after repeated rollbacks"
            )

        self._save_score(score)
        return downgrade_msg

    def set_tier(self, project_path: str, tier: int) -> str:
        """Manually set trust tier."""
        if not 0 <= tier <= 4:
            return f"Invalid tier: {tier}. Must be 0-4."

        score = self.get_score(project_path)
        old_tier = score.tier
        score.tier = TrustTier(tier)
        score.consecutive_successes = 0
        self._save_score(score)
        return f"Trust set: T{old_tier} -> T{tier} ({TrustTier(tier).name})"

    def status(self, project_path: str) -> dict:
        """Get trust status summary."""
        score = self.get_score(project_path)
        return {
            "tier": int(score.tier),
            "tier_name": score.tier.name,
            "successful_tasks": score.successful_tasks,
            "total_tasks": score.total_tasks,
            "rollbacks": score.rollbacks,
            "consecutive_successes": score.consecutive_successes,
            "tasks_until_upgrade": max(0, 10 - score.consecutive_successes),
        }
