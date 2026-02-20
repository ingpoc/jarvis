"""Idle-time introspection processor for Jarvis.

Implements the _idle_processor interface expected by daemon._iokit_idle_loop().
When the system has been idle for config.idle.idle_threshold_minutes, this
processor:

  Stage 1 — Cluster: embed skill_candidates + learnings using
             TF-IDF Jaccard similarity.

  Stage 2 — Synthesize: generate deterministic draft .md rule content
             for significant clusters and write to
             .claude/rules/draft-introspect-*.md.

Human review is required before a draft rule becomes active.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

INTROSPECT_LOG = Path.home() / ".jarvis" / "logs" / "introspect.log"
MAX_RUNS_PER_DAY = 2
MIN_CLUSTER_SIZE = 2


# ---------------------------------------------------------------------------
# Thermal check
# ---------------------------------------------------------------------------

def _is_thermal_ok() -> bool:
    """Return True if macOS thermal state is Nominal (0) or Fair (1)."""
    try:
        result = subprocess.run(
            [
                "python3", "-c",
                "from Foundation import NSProcessInfo; "
                "print(NSProcessInfo.processInfo().thermalState())",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return int(result.stdout.strip()) <= 1
    except Exception:
        pass
    return True  # assume OK when check unavailable


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class IntrospectionProcessor:
    """Idle-time pattern analysis and draft rule generation.

    Interface (called by daemon._iokit_idle_loop):
      trigger_idle()      — sync, schedules async pipeline
      record_activity()   — sync, cancels in-flight pipeline
      trigger_hibernate() — sync, same as record_activity
      stop()              — async, cleanup on daemon shutdown
    """

    def __init__(self, memory, project_path: str | None = None):
        self.memory = memory
        self.project_path = project_path

        self._idle = False
        self._task: asyncio.Task | None = None
        self._runs_today: int = 0
        self._runs_day: str = date.today().isoformat()

    # ------------------------------------------------------------------
    # Sync interface — called from daemon's IOKit loop
    # ------------------------------------------------------------------

    def trigger_idle(self) -> None:
        """System has been idle long enough — start introspection."""
        if self._idle:
            return
        self._idle = True

        today = date.today().isoformat()
        if today != self._runs_day:
            self._runs_day = today
            self._runs_today = 0
        if self._runs_today >= MAX_RUNS_PER_DAY:
            logger.debug("Introspection skipped: daily limit reached")
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.debug("Introspection skipped: no running event loop")
            return

        if self._task and not self._task.done():
            return  # Already running

        self._task = loop.create_task(self._run(), name="jarvis-introspection")
        logger.info("Idle introspection pipeline started")

    def record_activity(self) -> None:
        """User activity detected — cancel in-flight introspection."""
        self._idle = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
            logger.debug("Introspection cancelled — user active")

    def trigger_hibernate(self) -> None:
        """Memory pressure — stop immediately (same as activity)."""
        self.record_activity()

    async def stop(self) -> None:
        """Daemon shutdown — cancel and clean up."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Async pipeline
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        """Full two-stage introspection pipeline."""
        try:
            if not _is_thermal_ok():
                self._log("Skipped: thermal state elevated")
                return

            self._runs_today += 1
            self._log(f"=== Run #{self._runs_today} — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")

            candidates = self.memory.get_skill_candidates(min_occurrences=3, limit=30)
            learnings = self.memory.get_learnings(
                project_path=self.project_path,
                min_confidence=0.5,
                limit=30,
            )

            items = self._build_corpus(candidates, learnings)
            if len(items) < MIN_CLUSTER_SIZE:
                self._log(f"Only {len(items)} pattern(s) — need ≥{MIN_CLUSTER_SIZE} to cluster.")
                return

            self._log(f"Analyzing {len(items)} patterns...")

            clusters = await self._cluster(items)
            significant = [c for c in clusters if len(c) >= MIN_CLUSTER_SIZE]
            self._log(f"Found {len(clusters)} cluster(s), {len(significant)} significant.")

            for i, cluster in enumerate(significant):
                self._log(f"Cluster {i + 1} ({len(cluster)} patterns): generating draft rule...")
                draft = await self._generate_rule(cluster)
                if draft:
                    path = self._write_draft(draft, i)
                    self._log(f"  → {path}")

            self._log("Complete.")

        except asyncio.CancelledError:
            self._log("Cancelled.")
        except Exception as e:
            logger.exception("Introspection pipeline error")
            self._log(f"ERROR: {e}")

    # ------------------------------------------------------------------
    # Stage 0: Build corpus
    # ------------------------------------------------------------------

    def _build_corpus(self, candidates: list[dict], learnings: list[dict]) -> list[dict]:
        items: list[dict] = []

        for c in candidates:
            text = " ".join(filter(None, [
                c.get("pattern_description", ""),
                c.get("suggested_skill", ""),
            ])).strip()
            if text:
                items.append({"text": text, "source": "skill_candidate", "raw": c})

        for lrn in learnings:
            text = " ".join(filter(None, [
                lrn.get("error_pattern", ""),
                lrn.get("fix_description", ""),
            ])).strip()
            if text:
                items.append({"text": text, "source": "learning", "raw": lrn})

        return items

    # ------------------------------------------------------------------
    # Stage 1: Clustering
    # ------------------------------------------------------------------

    async def _cluster(self, items: list[dict]) -> list[list[dict]]:
        self._log("  Embedding: TF-IDF Jaccard")
        return self._tfidf_clusters(items, threshold=0.3)

    def _tfidf_clusters(self, items: list[dict], threshold: float) -> list[list[dict]]:
        def tokens(text: str) -> set[str]:
            return set(text.lower().split())

        visited = [False] * len(items)
        clusters: list[list[dict]] = []

        for i, item in enumerate(items):
            if visited[i]:
                continue
            cluster = [item]
            visited[i] = True
            ti = tokens(item["text"])
            for j in range(i + 1, len(items)):
                if visited[j]:
                    continue
                tj = tokens(items[j]["text"])
                union = ti | tj
                if union:
                    jaccard = len(ti & tj) / len(union)
                    if jaccard >= threshold:
                        cluster.append(items[j])
                        visited[j] = True
            clusters.append(cluster)

        return sorted(clusters, key=lambda c: len(c), reverse=True)

    # ------------------------------------------------------------------
    # Stage 2: Rule generation
    # ------------------------------------------------------------------

    async def _generate_rule(self, cluster: list[dict]) -> str | None:
        examples = "\n".join(f"- {it['text']}" for it in cluster[:5])
        return (
            "## Pattern\n"
            f"{len(cluster)} recurring patterns indicate a repeated implementation gap.\n\n"
            "## Why It Happens\n"
            "The workflow allows similar mistakes to repeat without a deterministic check.\n\n"
            "## Prevention\n"
            "Add a pre-merge validation step for this pattern family and fail fast on regressions.\n\n"
            "## Detection\n"
            "Alert when the same error signature appears 2+ times in recent learnings.\n\n"
            "### Examples\n"
            f"{examples}\n"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _write_draft(self, content: str, index: int) -> Path:
        if self.project_path:
            rules_dir = Path(self.project_path) / ".claude" / "rules"
        else:
            rules_dir = Path.home() / ".claude" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d")
        path = rules_dir / f"draft-introspect-{ts}-{index + 1}.md"
        path.write_text(content)
        return path

    def _log(self, msg: str) -> None:
        try:
            INTROSPECT_LOG.parent.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(INTROSPECT_LOG, "a") as f:
                f.write(f"[{ts}] {msg}\n")
        except Exception:
            pass
        logger.info("[introspect] %s", msg)
