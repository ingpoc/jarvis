"""Budget controller: hard spending caps to prevent runaway costs.

Enforces per-session and per-day limits. Tracks costs via
Agent SDK ResultMessage.total_cost_usd.

Includes skill shortcutting: when a matching skill exists for a task,
bypass the cloud model and apply the skill directly, saving tokens.
"""

import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from jarvis.config import JARVIS_DB, JARVIS_HOME, JarvisConfig


@dataclass
class BudgetStatus:
    """Current budget consumption."""

    session_spent_usd: float
    session_limit_usd: float
    day_spent_usd: float
    day_limit_usd: float
    session_turns: int
    max_turns: int
    skills_shortcut_savings_usd: float = 0.0

    @property
    def session_remaining(self) -> float:
        return max(0.0, self.session_limit_usd - self.session_spent_usd)

    @property
    def day_remaining(self) -> float:
        return max(0.0, self.day_limit_usd - self.day_spent_usd)

    @property
    def can_continue(self) -> bool:
        return self.session_remaining > 0 and self.day_remaining > 0

    @property
    def turns_remaining(self) -> int:
        return max(0, self.max_turns - self.session_turns)


class BudgetController:
    """Tracks and enforces spending limits.

    Enhanced with skill shortcutting: tracks savings from skill-based
    task resolution that bypasses cloud model calls.
    """

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or JARVIS_DB
        self.config = JarvisConfig.load().budget
        self._session_id = f"session-{int(time.time())}"
        self._session_spent = 0.0
        self._session_turns = 0
        self._skill_shortcut_savings = 0.0
        self._skill_shortcuts_count = 0
        self._init_db()

    def _init_db(self) -> None:
        JARVIS_HOME.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cost_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp REAL,
                date TEXT,
                cost_usd REAL,
                turns INTEGER,
                task_description TEXT
            )
        """)
        conn.commit()
        conn.close()

    def record_cost(self, cost_usd: float, turns: int = 1, task_desc: str = "") -> None:
        """Record API cost from a completed agent turn."""
        self._session_spent += cost_usd
        self._session_turns += turns

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO cost_log (session_id, timestamp, date, cost_usd, turns, task_description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                self._session_id,
                time.time(),
                datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                cost_usd,
                turns,
                task_desc,
            ),
        )
        conn.commit()
        conn.close()

    def record_skill_shortcut(self, estimated_savings_usd: float = 0.02) -> None:
        """Record a skill shortcut that avoided a cloud model call.

        Args:
            estimated_savings_usd: Estimated cost that was saved by using
                                   a skill instead of a cloud API call.
        """
        self._skill_shortcut_savings += estimated_savings_usd
        self._skill_shortcuts_count += 1

    def try_skill_shortcut(
        self,
        task_description: str,
        memory=None,
    ) -> dict | None:
        """Attempt to shortcut a task using a matching skill.

        Checks if a promoted skill matches the task description. If so,
        returns the skill data for direct application, avoiding a cloud
        model call.

        Args:
            task_description: The task to check
            memory: MemoryStore instance for skill lookup

        Returns:
            dict with skill info if shortcut possible, None otherwise
        """
        if memory is None:
            return None

        try:
            from jarvis.skill_generator import select_session_skills

            session_skills = select_session_skills(memory)
            if not session_skills:
                return None

            task_lower = task_description.lower()

            for skill in session_skills:
                pattern_desc = skill.get("pattern_description", "").lower()
                # Check if the task matches the skill's pattern
                pattern_words = set(pattern_desc.split())
                task_words = set(task_lower.split())
                overlap = pattern_words & task_words
                # Require at least 40% word overlap for a match
                if len(pattern_words) > 0 and len(overlap) / len(pattern_words) >= 0.4:
                    self.record_skill_shortcut()
                    return {
                        "skill_name": skill.get("pattern_description", ""),
                        "pattern_hash": skill.get("pattern_hash", ""),
                        "confidence": skill.get("confidence", 0.5),
                        "shortcut": True,
                    }
        except Exception:
            pass

        return None

    def get_day_spent(self) -> float:
        """Get total spent today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_log WHERE date = ?",
            (today,),
        ).fetchone()
        conn.close()
        return row[0] if row else 0.0

    def check_budget(self) -> BudgetStatus:
        """Get current budget status."""
        return BudgetStatus(
            session_spent_usd=self._session_spent,
            session_limit_usd=self.config.max_per_session_usd,
            day_spent_usd=self.get_day_spent(),
            day_limit_usd=self.config.max_per_day_usd,
            session_turns=self._session_turns,
            max_turns=self.config.max_turns_per_task,
            skills_shortcut_savings_usd=self._skill_shortcut_savings,
        )

    def enforce(self) -> tuple[bool, str]:
        """Check if we can continue. Returns (can_continue, reason)."""
        status = self.check_budget()

        if not status.can_continue:
            if status.session_remaining <= 0:
                return False, (
                    f"Session budget exhausted: ${status.session_spent_usd:.2f} / "
                    f"${status.session_limit_usd:.2f}"
                )
            return False, (
                f"Daily budget exhausted: ${status.day_spent_usd:.2f} / "
                f"${status.day_limit_usd:.2f}"
            )

        if status.turns_remaining <= 0:
            return False, (
                f"Turn limit reached: {status.session_turns} / {status.max_turns}"
            )

        return True, "OK"

    def summary(self) -> dict:
        """Get budget summary for display."""
        status = self.check_budget()
        return {
            "session": f"${status.session_spent_usd:.2f} / ${status.session_limit_usd:.2f}",
            "daily": f"${status.day_spent_usd:.2f} / ${status.day_limit_usd:.2f}",
            "turns": f"{status.session_turns} / {status.max_turns}",
            "can_continue": status.can_continue,
            "skill_shortcuts": self._skill_shortcuts_count,
            "skill_savings_usd": f"${self._skill_shortcut_savings:.2f}",
        }
