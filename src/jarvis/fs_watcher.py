"""File system watcher for knowledge invalidation.

Monitors workspace files for changes and marks relevant learnings
as needing revalidation when files they reference are modified.

Uses a polling-based approach (cross-platform) with configurable
debounce to avoid excessive invalidation from rapid saves.
"""

import asyncio
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Any

from jarvis.memory import MemoryStore

# Try to import macOS FSEvents via pyobjc
try:
    from Foundation import NSObject
    from FSEvents import (
        FSEventStreamCreate,
        FSEventStreamScheduleWithRunLoop,
        FSEventStreamStart,
        FSEventStreamStop,
        FSEventStreamInvalidate,
        FSEventStreamRelease,
        kFSEventStreamEventFlagItemCreated,
        kFSEventStreamEventFlagItemRemoved,
        kFSEventStreamEventFlagItemModified,
        kFSEventStreamEventFlagItemRenamed,
        kFSEventStreamCreateFlagFileEvents,
        kFSEventStreamCreateFlagNoDefer,
    )
    from CoreFoundation import CFRunLoopGetCurrent, CFRunLoopRun, kCFRunLoopDefaultMode
    HAS_FSEVENTS = True
except ImportError:
    HAS_FSEVENTS = False

logger = logging.getLogger(__name__)

# Default debounce window in seconds to coalesce rapid changes
DEBOUNCE_SECONDS = 5.0

# File extensions to monitor
WATCHED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".java",
    ".swift", ".c", ".cpp", ".h", ".hpp", ".rb", ".php",
    ".json", ".yaml", ".yml", ".toml", ".xml",
    ".html", ".css", ".scss", ".less",
    ".sql", ".sh", ".bash", ".zsh",
}

# Directories to ignore
IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".build", "target", ".next", ".nuxt",
    "coverage", ".coverage", ".eggs", "*.egg-info",
}


def _should_watch(path: Path) -> bool:
    """Check if a file should be watched."""
    if path.suffix not in WATCHED_EXTENSIONS:
        return False
    for part in path.parts:
        if part in IGNORED_DIRS:
            return False
    return True


def _file_hash(path: Path) -> str | None:
    """Compute a quick content hash for change detection."""
    try:
        content = path.read_bytes()
        return hashlib.md5(content).hexdigest()
    except (OSError, PermissionError):
        return None


class FileSnapshot:
    """Snapshot of file state for change detection."""

    def __init__(self, path: Path, mtime: float, content_hash: str | None = None):
        self.path = path
        self.mtime = mtime
        self.content_hash = content_hash


class FSEventsWatcher:
    """Native macOS FSEvents-based file watcher.

    Uses the macOS FSEvents API for efficient, low-latency file change
    detection. Falls back to polling if FSEvents is unavailable.
    """

    def __init__(
        self,
        project_path: str,
        memory: MemoryStore,
        debounce: float = DEBOUNCE_SECONDS,
    ):
        self.project_path = Path(project_path)
        self.memory = memory
        self.debounce = debounce
        self._running = False
        self._thread = None
        self._pending_changes: dict[str, float] = {}
        self._change_callbacks: list = []
        self._stream = None

    def _fsevents_callback(self, stream, client_info, num_events, event_paths, event_flags, event_ids):
        """FSEvents callback: receives file change events from the OS."""
        import time
        now = time.time()
        for i in range(num_events):
            path = event_paths[i]
            if isinstance(path, bytes):
                path = path.decode("utf-8")
            rel_path = os.path.relpath(path, str(self.project_path))
            p = Path(rel_path)
            if _should_watch(Path(path)):
                self._pending_changes[rel_path] = now

    def _run_loop(self):
        """Run the CFRunLoop for FSEvents (runs in a background thread)."""
        context = None
        paths = [str(self.project_path)]
        self._stream = FSEventStreamCreate(
            None,
            self._fsevents_callback,
            context,
            paths,
            0,  # since_when (now)
            self.debounce,
            kFSEventStreamCreateFlagFileEvents | kFSEventStreamCreateFlagNoDefer,
        )
        FSEventStreamScheduleWithRunLoop(
            self._stream, CFRunLoopGetCurrent(), kCFRunLoopDefaultMode
        )
        FSEventStreamStart(self._stream)
        logger.info(f"FSEvents watcher active for {self.project_path}")
        CFRunLoopRun()

    async def start(self) -> None:
        """Start the FSEvents watcher in a background thread."""
        if self._running:
            return
        self._running = True
        import threading
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        # Start async processing loop
        asyncio.create_task(self._process_changes_loop())

    async def _process_changes_loop(self) -> None:
        """Process debounced FSEvents changes."""
        while self._running:
            try:
                await asyncio.sleep(self.debounce)
                if not self._pending_changes:
                    continue

                import time
                now = time.time()
                ready = [
                    p for p, t in self._pending_changes.items()
                    if now - t >= self.debounce
                ]
                for p in ready:
                    self._pending_changes.pop(p, None)

                if ready:
                    for callback in self._change_callbacks:
                        try:
                            callback(ready)
                        except Exception as e:
                            logger.warning(f"FSEvents change callback error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"FSEvents change processing error: {e}")
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop the FSEvents watcher."""
        self._running = False
        if self._stream:
            try:
                FSEventStreamStop(self._stream)
                FSEventStreamInvalidate(self._stream)
                FSEventStreamRelease(self._stream)
            except Exception:
                pass
        self._stream = None
        logger.info("FSEvents watcher stopped")

    def add_change_callback(self, callback) -> None:
        """Register a callback for file changes."""
        if callback not in self._change_callbacks:
            self._change_callbacks.append(callback)

    def get_stats(self) -> dict[str, Any]:
        """Get watcher statistics."""
        return {
            "project_path": str(self.project_path),
            "backend": "fsevents",
            "pending_changes": len(self._pending_changes),
            "running": self._running,
        }


class FileSystemWatcher:
    """Watches a project directory for file changes and invalidates learnings.

    Uses polling rather than OS-specific APIs for portability.
    The poll interval is configurable (default 30s).
    """

    def __init__(
        self,
        project_path: str,
        memory: MemoryStore,
        poll_interval: float = 30.0,
        debounce: float = DEBOUNCE_SECONDS,
    ):
        self.project_path = Path(project_path)
        self.memory = memory
        self.poll_interval = poll_interval
        self.debounce = debounce
        self._snapshots: dict[str, FileSnapshot] = {}
        self._pending_changes: dict[str, float] = {}  # path -> first_change_time
        self._running = False
        self._task: asyncio.Task | None = None
        self._change_callbacks: list = []

    def _scan_files(self) -> dict[str, FileSnapshot]:
        """Scan project directory and build file snapshots."""
        snapshots: dict[str, FileSnapshot] = {}
        try:
            for root, dirs, files in os.walk(self.project_path):
                # Skip ignored directories
                dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
                for name in files:
                    path = Path(root) / name
                    if not _should_watch(path):
                        continue
                    try:
                        stat = path.stat()
                        key = str(path.relative_to(self.project_path))
                        snapshots[key] = FileSnapshot(
                            path=path,
                            mtime=stat.st_mtime,
                        )
                    except (OSError, ValueError):
                        continue
        except OSError:
            pass
        return snapshots

    def _detect_changes(self, new_snapshots: dict[str, FileSnapshot]) -> dict[str, str]:
        """Compare snapshots and detect changes.

        Returns dict of {relative_path: change_type} where change_type
        is one of 'modified', 'created', 'deleted'.
        """
        changes: dict[str, str] = {}
        old_keys = set(self._snapshots.keys())
        new_keys = set(new_snapshots.keys())

        # Deleted files
        for key in old_keys - new_keys:
            changes[key] = "deleted"

        # Created files
        for key in new_keys - old_keys:
            changes[key] = "created"

        # Modified files (mtime changed)
        for key in old_keys & new_keys:
            if new_snapshots[key].mtime != self._snapshots[key].mtime:
                changes[key] = "modified"

        return changes

    def _invalidate_learnings(self, changed_files: list[str]) -> int:
        """Mark learnings referencing changed files for revalidation.

        Returns number of learnings invalidated.
        """
        invalidated = 0
        learnings = self.memory.get_learnings(
            project_path=str(self.project_path),
            min_confidence=0.0,
        )

        for learning in learnings:
            if learning.get("needs_revalidation"):
                continue  # Already marked

            # Check if the learning's fix_diff references any changed file
            fix_diff = learning.get("fix_diff", "")
            error_msg = learning.get("error_message", "")
            combined = f"{fix_diff} {error_msg}".lower()

            for changed_file in changed_files:
                # Check filename match (just the filename, not full path)
                filename = Path(changed_file).name.lower()
                if filename in combined:
                    self.memory.mark_learning_for_revalidation(learning["id"])
                    invalidated += 1
                    logger.info(
                        f"Marked learning {learning['id']} for revalidation "
                        f"(file changed: {changed_file})"
                    )
                    break

        return invalidated

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        # Initial snapshot
        self._snapshots = self._scan_files()
        logger.info(
            f"File watcher started for {self.project_path} "
            f"({len(self._snapshots)} files tracked)"
        )

        while self._running:
            try:
                await asyncio.sleep(self.poll_interval)

                new_snapshots = self._scan_files()
                changes = self._detect_changes(new_snapshots)

                if changes:
                    now = time.time()
                    for path, change_type in changes.items():
                        if path not in self._pending_changes:
                            self._pending_changes[path] = now
                            logger.debug(f"File {change_type}: {path}")

                    # Process debounced changes
                    ready_changes = []
                    still_pending = {}
                    for path, first_seen in self._pending_changes.items():
                        if now - first_seen >= self.debounce:
                            ready_changes.append(path)
                        else:
                            still_pending[path] = first_seen
                    self._pending_changes = still_pending

                    if ready_changes:
                        invalidated = self._invalidate_learnings(ready_changes)
                        if invalidated > 0:
                            logger.info(
                                f"Invalidated {invalidated} learnings due to "
                                f"{len(ready_changes)} file changes"
                            )

                        # Notify callbacks
                        for callback in self._change_callbacks:
                            try:
                                callback(ready_changes)
                            except Exception as e:
                                logger.warning(f"File change callback error: {e}")

                # Update snapshots
                self._snapshots = new_snapshots

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"File watcher error: {e}")
                await asyncio.sleep(self.poll_interval)

    async def start(self) -> None:
        """Start the file system watcher."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop the file system watcher."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("File watcher stopped")

    def add_change_callback(self, callback) -> None:
        """Register a callback for file changes. callback(changed_files: list[str])"""
        if callback not in self._change_callbacks:
            self._change_callbacks.append(callback)

    def get_stats(self) -> dict[str, Any]:
        """Get watcher statistics."""
        return {
            "project_path": str(self.project_path),
            "files_tracked": len(self._snapshots),
            "pending_changes": len(self._pending_changes),
            "running": self._running,
            "poll_interval": self.poll_interval,
        }


def create_file_watcher(
    project_path: str,
    memory: MemoryStore,
    poll_interval: float = 30.0,
    debounce: float = DEBOUNCE_SECONDS,
) -> FileSystemWatcher | FSEventsWatcher:
    """Create the best available file watcher for the platform.

    Uses native FSEvents on macOS if available, falls back to polling.
    """
    if HAS_FSEVENTS:
        logger.info("Using native FSEvents file watcher")
        return FSEventsWatcher(
            project_path=project_path,
            memory=memory,
            debounce=debounce,
        )
    else:
        logger.info("Using polling-based file watcher (FSEvents unavailable)")
        return FileSystemWatcher(
            project_path=project_path,
            memory=memory,
            poll_interval=poll_interval,
            debounce=debounce,
        )
