"""Memory layer: multi-tier persistence for cross-session continuity.

Tier 1: Session (Agent SDK sessions - handled externally)
Tier 2: Task memory (SQLite - goals, progress, checkpoints)
Tier 3: Project rules (JARVIS.md - version controlled)
Tier 4: Learned patterns (SQLite - developer preferences, decisions)
"""

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from jarvis.config import JARVIS_DB, JARVIS_HOME


@dataclass
class Task:
    """Tracked task with status and checkpoints."""

    id: str
    description: str
    status: str  # pending, in_progress, completed, failed, paused
    project_path: str
    created_at: float
    updated_at: float
    session_id: str | None = None
    plan: str | None = None
    result: str | None = None
    cost_usd: float = 0.0
    turns: int = 0
    container_id: str | None = None


class MemoryStore:
    """SQLite-backed persistent memory."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or JARVIS_DB
        self._init_db()

    def _init_db(self) -> None:
        JARVIS_HOME.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                description TEXT,
                status TEXT DEFAULT 'pending',
                project_path TEXT,
                created_at REAL,
                updated_at REAL,
                session_id TEXT,
                plan TEXT,
                result TEXT,
                cost_usd REAL DEFAULT 0.0,
                turns INTEGER DEFAULT 0,
                container_id TEXT
            );

            CREATE TABLE IF NOT EXISTS session_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                project_path TEXT,
                timestamp REAL,
                summary TEXT,
                tasks_completed TEXT,
                tasks_remaining TEXT
            );

            CREATE TABLE IF NOT EXISTS learned_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_path TEXT,
                pattern_type TEXT,
                pattern TEXT,
                confidence REAL DEFAULT 0.5,
                created_at REAL,
                last_used REAL
            );

            CREATE TABLE IF NOT EXISTS decision_traces (
                id TEXT PRIMARY KEY,
                category TEXT,
                description TEXT,
                decision TEXT,
                context_json TEXT,
                outcome TEXT DEFAULT 'pending',
                outcome_notes TEXT,
                project_path TEXT,
                created_at REAL,
                updated_at REAL
            );

            CREATE TABLE IF NOT EXISTS timeline_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                event_type TEXT,
                summary TEXT,
                session_id TEXT,
                task_id TEXT,
                feature_id TEXT,
                cost_usd REAL DEFAULT 0.0,
                metadata_json TEXT
            );

            CREATE TABLE IF NOT EXISTS execution_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                session_id TEXT,
                tool_name TEXT,
                tool_input_json TEXT,
                tool_output_json TEXT,
                exit_code INTEGER,
                files_touched TEXT,
                error_message TEXT,
                timestamp REAL,
                duration_ms REAL,
                project_path TEXT
            );

            CREATE TABLE IF NOT EXISTS learnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_path TEXT,
                language TEXT,
                error_pattern_hash TEXT,
                error_message TEXT,
                fix_description TEXT,
                fix_diff TEXT,
                confidence REAL DEFAULT 0.7,
                occurrence_count INTEGER DEFAULT 1,
                created_at REAL,
                last_used REAL,
                needs_revalidation INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS skill_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_hash TEXT UNIQUE,
                pattern_description TEXT,
                occurrence_count INTEGER DEFAULT 1,
                first_seen REAL,
                last_seen REAL,
                example_tasks TEXT,
                confidence REAL DEFAULT 0.5,
                promoted_to_skill INTEGER DEFAULT 0,
                project_path TEXT
            );

            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                task_id TEXT,
                model TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                cost_usd REAL,
                timestamp REAL,
                project_path TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_timeline_ts ON timeline_events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_timeline_type ON timeline_events(event_type);
            CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_path);
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_patterns_project ON learned_patterns(project_path);
            CREATE INDEX IF NOT EXISTS idx_traces_project ON decision_traces(project_path);
            CREATE INDEX IF NOT EXISTS idx_traces_category ON decision_traces(category);
            CREATE INDEX IF NOT EXISTS idx_execution_records_task ON execution_records(task_id);
            CREATE INDEX IF NOT EXISTS idx_execution_records_tool ON execution_records(tool_name);
            CREATE INDEX IF NOT EXISTS idx_learnings_project ON learnings(project_path);
            CREATE INDEX IF NOT EXISTS idx_learnings_hash ON learnings(error_pattern_hash);
            CREATE INDEX IF NOT EXISTS idx_skill_candidates_hash ON skill_candidates(pattern_hash);
            CREATE INDEX IF NOT EXISTS idx_token_usage_session ON token_usage(session_id);
        """)
        conn.commit()
        conn.close()

    # --- Task management ---

    def create_task(self, task_id: str, description: str, project_path: str) -> Task:
        now = time.time()
        task = Task(
            id=task_id,
            description=description,
            status="pending",
            project_path=project_path,
            created_at=now,
            updated_at=now,
        )
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO tasks (id, description, status, project_path, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (task.id, task.description, task.status, task.project_path, now, now),
        )
        conn.commit()
        conn.close()
        return task

    def update_task(self, task_id: str, **kwargs) -> None:
        kwargs["updated_at"] = time.time()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [task_id]
        conn = sqlite3.connect(self.db_path)
        conn.execute(f"UPDATE tasks SET {sets} WHERE id = ?", values)
        conn.commit()
        conn.close()

    def get_task(self, task_id: str) -> Task | None:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return Task(*row)

    def list_tasks(self, project_path: str | None = None, status: str | None = None) -> list[Task]:
        conn = sqlite3.connect(self.db_path)
        query = "SELECT * FROM tasks WHERE 1=1"
        params: list = []
        if project_path:
            query += " AND project_path = ?"
            params.append(project_path)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [Task(*r) for r in rows]

    # --- Session summaries ---

    def save_session_summary(
        self,
        session_id: str,
        project_path: str,
        summary: str,
        tasks_completed: list[str],
        tasks_remaining: list[str],
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO session_summaries "
            "(session_id, project_path, timestamp, summary, tasks_completed, tasks_remaining) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                session_id, project_path, time.time(), summary,
                json.dumps(tasks_completed), json.dumps(tasks_remaining),
            ),
        )
        conn.commit()
        conn.close()

    def get_last_summary(self, project_path: str) -> dict | None:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT * FROM session_summaries WHERE project_path = ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (project_path,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "session_id": row[1],
            "project_path": row[2],
            "timestamp": row[3],
            "summary": row[4],
            "tasks_completed": json.loads(row[5]),
            "tasks_remaining": json.loads(row[6]),
        }

    # --- Learned patterns ---

    def learn_pattern(self, project_path: str, pattern_type: str, pattern: str) -> None:
        now = time.time()
        conn = sqlite3.connect(self.db_path)
        # Check if pattern exists
        existing = conn.execute(
            "SELECT id, confidence FROM learned_patterns "
            "WHERE project_path = ? AND pattern_type = ? AND pattern = ?",
            (project_path, pattern_type, pattern),
        ).fetchone()

        if existing:
            # Reinforce existing pattern
            new_confidence = min(1.0, existing[1] + 0.1)
            conn.execute(
                "UPDATE learned_patterns SET confidence = ?, last_used = ? WHERE id = ?",
                (new_confidence, now, existing[0]),
            )
        else:
            conn.execute(
                "INSERT INTO learned_patterns "
                "(project_path, pattern_type, pattern, confidence, created_at, last_used) "
                "VALUES (?, ?, ?, 0.5, ?, ?)",
                (project_path, pattern_type, pattern, now, now),
            )
        conn.commit()
        conn.close()

    def get_patterns(self, project_path: str, pattern_type: str | None = None) -> list[dict]:
        conn = sqlite3.connect(self.db_path)
        query = "SELECT pattern_type, pattern, confidence FROM learned_patterns WHERE project_path = ?"
        params: list = [project_path]
        if pattern_type:
            query += " AND pattern_type = ?"
            params.append(pattern_type)
        query += " ORDER BY confidence DESC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [
            {"type": r[0], "pattern": r[1], "confidence": r[2]}
            for r in rows
        ]

    # --- Decision traces ---

    def store_local_trace(
        self,
        trace_id: str,
        category: str,
        description: str,
        decision: str,
        context: dict | None,
        project_path: str,
        outcome: str = "pending",
    ) -> None:
        now = time.time()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO decision_traces "
            "(id, category, description, decision, context_json, outcome, project_path, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (trace_id, category, description, decision,
             json.dumps(context) if context else None,
             outcome, project_path, now, now),
        )
        conn.commit()
        conn.close()

    def query_local_traces(
        self,
        project_path: str | None = None,
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        conn = sqlite3.connect(self.db_path)
        query = "SELECT id, category, description, decision, outcome, project_path FROM decision_traces WHERE 1=1"
        params: list = []
        if project_path:
            query += " AND project_path = ?"
            params.append(project_path)
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [
            {"id": r[0], "category": r[1], "description": r[2],
             "decision": r[3], "outcome": r[4], "project_path": r[5]}
            for r in rows
        ]

    def update_local_trace_outcome(
        self,
        trace_id: str,
        outcome: str,
        notes: str | None = None,
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE decision_traces SET outcome = ?, outcome_notes = ?, updated_at = ? WHERE id = ?",
            (outcome, notes, time.time(), trace_id),
        )
        conn.commit()
        conn.close()

    # --- Timeline events ---

    def record_event(
        self,
        event_type: str,
        summary: str,
        session_id: str | None = None,
        task_id: str | None = None,
        feature_id: str | None = None,
        cost_usd: float = 0.0,
        metadata: dict | None = None,
    ) -> int:
        """Record a timeline event. Returns the event ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "INSERT INTO timeline_events "
            "(timestamp, event_type, summary, session_id, task_id, feature_id, cost_usd, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (time.time(), event_type, summary, session_id, task_id, feature_id,
             cost_usd, json.dumps(metadata) if metadata else None),
        )
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return event_id

    def get_timeline(
        self,
        session_id: str | None = None,
        limit: int = 50,
        event_type: str | None = None,
        date_range: tuple[float, float] | None = None,
    ) -> list[dict]:
        """Query timeline events with optional filters."""
        conn = sqlite3.connect(self.db_path)
        query = "SELECT id, timestamp, event_type, summary, session_id, task_id, feature_id, cost_usd, metadata_json FROM timeline_events WHERE 1=1"
        params: list = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if date_range:
            query += " AND timestamp >= ? AND timestamp <= ?"
            params.extend(date_range)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [
            {
                "id": r[0], "timestamp": r[1], "event_type": r[2], "summary": r[3],
                "session_id": r[4], "task_id": r[5], "feature_id": r[6],
                "cost_usd": r[7], "metadata": json.loads(r[8]) if r[8] else None,
            }
            for r in rows
        ]

    def get_day_summary(self, date: float | None = None) -> dict:
        """Get aggregate summary for a day."""
        import datetime
        if date is None:
            date = time.time()
        dt = datetime.datetime.fromtimestamp(date)
        day_start = datetime.datetime(dt.year, dt.month, dt.day).timestamp()
        day_end = day_start + 86400

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT event_type, COUNT(*), SUM(cost_usd) FROM timeline_events "
            "WHERE timestamp >= ? AND timestamp < ? GROUP BY event_type",
            (day_start, day_end),
        ).fetchall()
        total_cost = conn.execute(
            "SELECT SUM(cost_usd) FROM timeline_events WHERE timestamp >= ? AND timestamp < ?",
            (day_start, day_end),
        ).fetchone()[0] or 0.0
        conn.close()
        return {
            "date": dt.strftime("%Y-%m-%d"),
            "events_by_type": {r[0]: {"count": r[1], "cost": r[2] or 0.0} for r in rows},
            "total_events": sum(r[1] for r in rows),
            "total_cost": total_cost,
        }

    # --- Execution records ---

    def record_execution(
        self,
        task_id: str,
        session_id: str,
        tool_name: str,
        tool_input: dict,
        tool_output: str | dict,
        exit_code: int = 0,
        files_touched: list[str] | None = None,
        error_message: str | None = None,
        duration_ms: float = 0.0,
        project_path: str = "",
    ) -> int:
        """Record a tool execution."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "INSERT INTO execution_records "
            "(task_id, session_id, tool_name, tool_input_json, tool_output_json, "
            "exit_code, files_touched, error_message, timestamp, duration_ms, project_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task_id, session_id, tool_name,
                json.dumps(tool_input),
                json.dumps(tool_output) if isinstance(tool_output, dict) else tool_output,
                exit_code,
                json.dumps(files_touched) if files_touched else None,
                error_message,
                time.time(),
                duration_ms,
                project_path,
            ),
        )
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return record_id

    def get_execution_records(
        self,
        task_id: str | None = None,
        project_path: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query execution records."""
        conn = sqlite3.connect(self.db_path)
        query = "SELECT * FROM execution_records WHERE 1=1"
        params: list = []
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)
        if project_path:
            query += " AND project_path = ?"
            params.append(project_path)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [
            {
                "id": r[0], "task_id": r[1], "session_id": r[2], "tool_name": r[3],
                "tool_input": json.loads(r[4]) if r[4] else {},
                "tool_output": r[5], "exit_code": r[6],
                "files_touched": json.loads(r[7]) if r[7] else [],
                "error_message": r[8], "timestamp": r[9], "duration_ms": r[10],
                "project_path": r[11],
            }
            for r in rows
        ]

    # --- Learnings ---

    def save_learning(
        self,
        project_path: str,
        language: str,
        error_pattern_hash: str,
        error_message: str,
        fix_description: str,
        fix_diff: str,
        confidence: float = 0.7,
    ) -> int:
        """Save a new learning or update existing one."""
        now = time.time()
        conn = sqlite3.connect(self.db_path)

        # Check if learning exists
        existing = conn.execute(
            "SELECT id, occurrence_count FROM learnings "
            "WHERE project_path = ? AND error_pattern_hash = ?",
            (project_path, error_pattern_hash),
        ).fetchone()

        if existing:
            # Update occurrence count and confidence
            new_count = existing[1] + 1
            new_confidence = min(1.0, confidence + 0.1 * new_count)
            conn.execute(
                "UPDATE learnings SET occurrence_count = ?, confidence = ?, "
                "last_used = ?, needs_revalidation = 0 WHERE id = ?",
                (new_count, new_confidence, now, existing[0]),
            )
            learning_id = existing[0]
        else:
            # Insert new learning
            cursor = conn.execute(
                "INSERT INTO learnings "
                "(project_path, language, error_pattern_hash, error_message, "
                "fix_description, fix_diff, confidence, created_at, last_used) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (project_path, language, error_pattern_hash, error_message,
                 fix_description, fix_diff, confidence, now, now),
            )
            learning_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return learning_id

    def get_learnings(
        self,
        project_path: str | None = None,
        error_pattern_hash: str | None = None,
        min_confidence: float = 0.5,
        limit: int = 20,
    ) -> list[dict]:
        """Query learnings."""
        conn = sqlite3.connect(self.db_path)
        query = "SELECT * FROM learnings WHERE confidence >= ?"
        params: list = [min_confidence]
        if project_path:
            query += " AND project_path = ?"
            params.append(project_path)
        if error_pattern_hash:
            query += " AND error_pattern_hash = ?"
            params.append(error_pattern_hash)
        query += " ORDER BY confidence DESC, occurrence_count DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [
            {
                "id": r[0], "project_path": r[1], "language": r[2],
                "error_pattern_hash": r[3], "error_message": r[4],
                "fix_description": r[5], "fix_diff": r[6], "confidence": r[7],
                "occurrence_count": r[8], "created_at": r[9], "last_used": r[10],
                "needs_revalidation": r[11],
            }
            for r in rows
        ]

    def mark_learning_for_revalidation(self, learning_id: int) -> None:
        """Mark a learning as needing revalidation."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE learnings SET needs_revalidation = 1 WHERE id = ?",
            (learning_id,),
        )
        conn.commit()
        conn.close()

    # --- Skill candidates ---

    def record_skill_candidate(
        self,
        pattern_hash: str,
        pattern_description: str,
        example_task: str,
        project_path: str,
    ) -> int:
        """Record or update a skill candidate pattern."""
        now = time.time()
        conn = sqlite3.connect(self.db_path)

        # Check if candidate exists
        existing = conn.execute(
            "SELECT id, occurrence_count, example_tasks FROM skill_candidates "
            "WHERE pattern_hash = ?",
            (pattern_hash,),
        ).fetchone()

        if existing:
            # Update occurrence count
            new_count = existing[1] + 1
            examples = json.loads(existing[2]) if existing[2] else []
            if example_task not in examples:
                examples.append(example_task)
            conn.execute(
                "UPDATE skill_candidates SET occurrence_count = ?, "
                "last_seen = ?, example_tasks = ? WHERE id = ?",
                (new_count, now, json.dumps(examples), existing[0]),
            )
            candidate_id = existing[0]
        else:
            # Insert new candidate
            cursor = conn.execute(
                "INSERT INTO skill_candidates "
                "(pattern_hash, pattern_description, occurrence_count, "
                "first_seen, last_seen, example_tasks, project_path) "
                "VALUES (?, ?, 1, ?, ?, ?, ?)",
                (pattern_hash, pattern_description, now, now,
                 json.dumps([example_task]), project_path),
            )
            candidate_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return candidate_id

    def get_skill_candidates(
        self,
        min_occurrences: int = 3,
        promoted: bool = False,
        limit: int = 20,
    ) -> list[dict]:
        """Query skill candidates ready for promotion."""
        conn = sqlite3.connect(self.db_path)
        query = "SELECT * FROM skill_candidates WHERE occurrence_count >= ? AND promoted_to_skill = ?"
        rows = conn.execute(query, (min_occurrences, 1 if promoted else 0)).fetchall()
        conn.close()
        return [
            {
                "id": r[0], "pattern_hash": r[1], "pattern_description": r[2],
                "occurrence_count": r[3], "first_seen": r[4], "last_seen": r[5],
                "example_tasks": json.loads(r[6]) if r[6] else [],
                "confidence": r[7], "promoted_to_skill": r[8],
                "project_path": r[9],
            }
            for r in rows
        ]

    def mark_skill_promoted(self, candidate_id: int) -> None:
        """Mark a skill candidate as promoted."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE skill_candidates SET promoted_to_skill = 1 WHERE id = ?",
            (candidate_id,),
        )
        conn.commit()
        conn.close()

    # --- Token usage ---

    def record_token_usage(
        self,
        session_id: str,
        task_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        project_path: str,
    ) -> int:
        """Record token usage for a model call."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "INSERT INTO token_usage "
            "(session_id, task_id, model, prompt_tokens, completion_tokens, "
            "total_tokens, cost_usd, timestamp, project_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, task_id, model, prompt_tokens, completion_tokens,
             prompt_tokens + completion_tokens, cost_usd, time.time(), project_path),
        )
        usage_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return usage_id

    def get_token_usage(
        self,
        session_id: str | None = None,
        project_path: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query token usage records."""
        conn = sqlite3.connect(self.db_path)
        query = "SELECT * FROM token_usage WHERE 1=1"
        params: list = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if project_path:
            query += " AND project_path = ?"
            params.append(project_path)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [
            {
                "id": r[0], "session_id": r[1], "task_id": r[2], "model": r[3],
                "prompt_tokens": r[4], "completion_tokens": r[5],
                "total_tokens": r[6], "cost_usd": r[7], "timestamp": r[8],
                "project_path": r[9],
            }
            for r in rows
        ]


# --- JARVIS.md template ---


JARVIS_MD_TEMPLATE = """# JARVIS.md - Project Configuration

## Project Info

- **Name**: {project_name}
- **Type**: {project_type}
- **Path**: {project_path}

## Conventions

- Test runner: {test_runner}
- Package manager: {package_manager}
- Git branch strategy: feature branches off main

## Rules

- Always run tests before committing
- Use conventional commit format
- Never commit .env files or secrets

## Trust Level

Current: T{trust_tier} ({trust_tier_name})

## Container Template

Image: {container_image}
CPUs: {cpus}
Memory: {memory}
"""


def generate_jarvis_md(project_path: Path, config: dict) -> str:
    """Generate JARVIS.md content for a project."""
    return JARVIS_MD_TEMPLATE.format(**config)
