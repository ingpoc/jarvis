"""Budget controller: hard spending caps to prevent runaway costs.

Enforces per-session and per-day limits. Tracks costs via
Agent SDK ResultMessage.total_cost_usd.
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
    """Tracks and enforces spending limits."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or JARVIS_DB
        self.config = JarvisConfig.load().budget
        self._session_id = f"session-{int(time.time())}"
        self._session_spent = 0.0
        self._session_turns = 0
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
        }
