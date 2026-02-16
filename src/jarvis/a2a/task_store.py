"""A2A Task Store: wraps MemoryStore for A2A protocol tasks."""

import json
import logging
import sqlite3
import threading
import time
import uuid

from jarvis.a2a.models import A2AArtifact, A2ATask, A2ATaskState, map_internal_to_a2a
from jarvis.config import JARVIS_HOME
from jarvis.memory import MemoryStore

logger = logging.getLogger(__name__)


# Dedicated A2A tasks table (separate from internal tasks)
A2A_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS a2a_tasks (
    id TEXT PRIMARY KEY,
    status TEXT,
    message TEXT,
    context_id TEXT,
    result TEXT,
    error TEXT,
    artifacts_json TEXT,
    created_at REAL,
    updated_at REAL
)
"""


class A2ATaskStore:
    """Manages A2A tasks with MemoryStore persistence."""

    _lock = threading.Lock()

    def __init__(self, memory: MemoryStore | None = None):
        logger.info("A2ATaskStore.__init__: starting")
        self.memory = memory or MemoryStore()
        logger.info("A2ATaskStore.__init__: MemoryStore created")
        self._a2a_tasks: dict[str, A2ATask] = {}  # In-memory cache
        self._db_path = self.memory.db_path
        logger.info("A2ATaskStore.__init__: db_path set")
        self._local_conn: sqlite3.Connection | None = None
        self._init_a2a_table()
        logger.info("A2ATaskStore.__init__: a2a_table initialized")
        # Load cached tasks - but don't block startup if database is slow
        try:
            self._load_cached_tasks()
            logger.info("A2ATaskStore.__init__: cached tasks loaded")
        except Exception as e:
            logger.warning("A2ATaskStore.__init__: failed to load cached tasks (non-blocking): %s", e)
        logger.info("A2ATaskStore.__init__: initialization complete")

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a single connection for this instance.

        IMPORTANT: Caller must hold self._lock to prevent race conditions.
        """
        if self._local_conn is None:
            logger.info("_get_connection: creating new sqlite3 connection to %s", self._db_path)
            self._local_conn = sqlite3.connect(
                self._db_path,
                timeout=5.0,  # Reduced from 30s to avoid long hangs
                check_same_thread=False,
            )
            logger.info("_get_connection: sqlite3 connection established")
            self._local_conn.execute("PRAGMA journal_mode=WAL")
            logger.info("_get_connection: WAL mode enabled")
        return self._local_conn

    def _init_a2a_table(self) -> None:
        """Initialize A2A tasks table in database."""
        logger.info("_init_a2a_table: starting")
        try:
            with self._lock:
                logger.info("_init_a2a_table: lock acquired")
                conn = self._get_connection()
                logger.info("_init_a2a_table: connection obtained")
                conn.executescript(A2A_TASKS_TABLE)
                logger.info("_init_a2a_table: script executed")
                conn.commit()
                logger.info("_init_a2a_table: commit successful")
        except Exception as e:
            logger.error("_init_a2a_table failed (non-blocking): %s", e)

    def _load_cached_tasks(self) -> None:
        """Load recent non-terminal tasks from database on startup."""
        terminal_states = {"completed", "failed", "canceled", "rejected"}
        try:
            with self._lock:
                rows = self._get_connection().execute(
                    "SELECT id, status, message, context_id, result, error, artifacts_json, created_at, updated_at "
                    "FROM a2a_tasks WHERE status NOT IN (?, ?, ?, ?) ORDER BY updated_at DESC LIMIT 100",
                    list(terminal_states),
                ).fetchall()

            for row in rows:
                task = A2ATask(
                    id=row[0],
                    status=A2ATaskState(row[1]),
                    message=row[2],
                    context_id=row[3],
                    result=row[4],
                    error=row[5],
                    artifacts=self._parse_artifacts(row[6]),
                    created_at=row[7],
                    updated_at=row[8],
                )
                self._a2a_tasks[task.id] = task
        except Exception as e:
            logger.debug("Failed to load cached tasks: %s", e)

    def _parse_artifacts(self, artifacts_json: str | None) -> list[A2AArtifact]:
        """Parse artifacts from JSON string."""
        if not artifacts_json:
            return []
        try:
            data = json.loads(artifacts_json)
            return [A2AArtifact(**a) for a in data]
        except (json.JSONDecodeError, TypeError):
            return []

    def _persist_task(self, task: A2ATask) -> None:
        """Persist task to database."""
        artifacts_json = json.dumps([
            {"name": a.name, "content": a.content, "mime_type": a.mime_type}
            for a in task.artifacts
        ]) if task.artifacts else None

        with self._lock:
            self._get_connection().execute(
                "INSERT OR REPLACE INTO a2a_tasks "
                "(id, status, message, context_id, result, error, artifacts_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (task.id, task.status.value, task.message, task.context_id,
                 task.result, task.error, artifacts_json, task.created_at, task.updated_at),
            )
            self._get_connection().commit()

    def create_task(
        self,
        message: str,
        context_id: str | None = None,
    ) -> A2ATask:
        """Create a new A2A task."""
        task_id = f"a2a-{uuid.uuid4().hex[:12]}"
        task = A2ATask(
            id=task_id,
            status=A2ATaskState.SUBMITTED,
            message=message,
            context_id=context_id,
            created_at=time.time(),
            updated_at=time.time(),
        )
        self._a2a_tasks[task_id] = task
        self._persist_task(task)
        return task

    def get_task(self, task_id: str) -> A2ATask | None:
        """Get task by ID. Checks cache first, then database."""
        # Check cache
        if task_id in self._a2a_tasks:
            return self._a2a_tasks[task_id]

        # Check database
        try:
            with self._lock:
                row = self._get_connection().execute(
                    "SELECT id, status, message, context_id, result, error, artifacts_json, created_at, updated_at "
                    "FROM a2a_tasks WHERE id = ?",
                    (task_id,),
                ).fetchone()

            if row:
                task = A2ATask(
                    id=row[0],
                    status=A2ATaskState(row[1]),
                    message=row[2],
                    context_id=row[3],
                    result=row[4],
                    error=row[5],
                    artifacts=self._parse_artifacts(row[6]),
                    created_at=row[7],
                    updated_at=row[8],
                )
                self._a2a_tasks[task_id] = task  # Cache it
                return task
        except Exception as e:
            logger.debug("Failed to get task %s from database: %s", task_id, e)

        return None

    def update_task_status(
        self,
        task_id: str,
        status: A2ATaskState,
        result: str | None = None,
        error: str | None = None,
    ) -> A2ATask | None:
        """Update task status and optional result/error."""
        task = self._a2a_tasks.get(task_id)
        if not task:
            # Try loading from database
            task = self.get_task(task_id)
            if not task:
                return None

        task.status = status
        task.result = result
        task.error = error
        task.updated_at = time.time()
        self._persist_task(task)
        return task

    def add_artifact(
        self,
        task_id: str,
        name: str,
        content: str,
        mime_type: str = "text/plain",
    ) -> A2AArtifact | None:
        """Add an artifact to a task."""
        task = self._a2a_tasks.get(task_id) or self.get_task(task_id)
        if not task:
            return None
        artifact = A2AArtifact(name=name, content=content, mime_type=mime_type)
        task.artifacts.append(artifact)
        task.updated_at = time.time()
        self._persist_task(task)
        return artifact

    def map_internal_status(self, internal_status: str) -> A2ATaskState:
        """Map internal Jarvis status to A2A status."""
        return map_internal_to_a2a(internal_status)

    def list_tasks(
        self,
        context_id: str | None = None,
        status: A2ATaskState | None = None,
        limit: int = 50,
    ) -> list[A2ATask]:
        """List tasks with optional filters."""
        # Query from database for complete list
        try:
            query = "SELECT id, status, message, context_id, result, error, artifacts_json, created_at, updated_at FROM a2a_tasks WHERE 1=1"
            params: list = []

            if context_id:
                query += " AND context_id = ?"
                params.append(context_id)
            if status:
                query += " AND status = ?"
                params.append(status.value)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            with self._lock:
                rows = self._get_connection().execute(query, params).fetchall()

            tasks = []
            for row in rows:
                task = A2ATask(
                    id=row[0],
                    status=A2ATaskState(row[1]),
                    message=row[2],
                    context_id=row[3],
                    result=row[4],
                    error=row[5],
                    artifacts=self._parse_artifacts(row[6]),
                    created_at=row[7],
                    updated_at=row[8],
                )
                tasks.append(task)
            return tasks
        except Exception as e:
            logger.debug("Failed to list tasks from database, using cache: %s", e)
            # Fallback to in-memory cache
            tasks = list(self._a2a_tasks.values())
            if context_id:
                tasks = [t for t in tasks if t.context_id == context_id]
            if status:
                tasks = [t for t in tasks if t.status == status]
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            return tasks[:limit]

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._local_conn is not None:
                self._local_conn.close()
                self._local_conn = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection."""
        self.close()
        return False
