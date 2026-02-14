"""Jarvis daemon: persistent background process with WS + Slack + Voice."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib import parse, request

from jarvis.config import JarvisConfig, ensure_jarvis_home
from jarvis.notifications import set_slack_bot, set_voice_client
from jarvis.orchestrator import JarvisOrchestrator
from jarvis.ws_server import JarvisWSServer

logger = logging.getLogger(__name__)


class JarvisDaemon:
    """Long-running daemon: WebSocket bridge + optional Slack/Voice."""

    def __init__(self, project_path: str | None = None):
        ensure_jarvis_home()
        self.config = JarvisConfig.load()
        self.orchestrator = JarvisOrchestrator(project_path)
        self.events = self.orchestrator.events
        self._ws_server: JarvisWSServer | None = None
        self._slack_bot = None
        self._slack_task: asyncio.Task | None = None
        self._voice_client = None
        self._running = False
        self._stop_event = asyncio.Event()
        self._idle_loop_task: asyncio.Task | None = None
        self._last_idle_run_ts: float = 0.0
        self._idle_runs_today: int = 0
        self._idle_runs_day: str = datetime.now().strftime("%Y-%m-%d")

    async def start(self) -> None:
        """Start all daemon services."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # WebSocket server (always)
        self._ws_server = JarvisWSServer(
            event_collector=self.events,
            orchestrator=self.orchestrator,
        )
        await self._ws_server.start()

        # Provider/model preflight (fail-fast when configured strict).
        live_check = os.environ.get("JARVIS_PREFLIGHT_LIVE", "0") == "1"
        strict = os.environ.get("JARVIS_PREFLIGHT_STRICT", "1") == "1"
        preflight = await self.orchestrator.run_model_preflight(
            live_check=live_check,
            timeout_seconds=int(os.environ.get("JARVIS_PREFLIGHT_TIMEOUT_SECS", "25")),
        )
        if preflight.get("ready"):
            self.events.emit(
                "preflight_ok",
                "Model/provider preflight passed",
                metadata={"live_check": live_check, "warnings": preflight.get("warnings", [])},
            )
        else:
            self.events.emit(
                "preflight_failed",
                "Model/provider preflight failed",
                metadata={
                    "errors": preflight.get("errors", []),
                    "warnings": preflight.get("warnings", []),
                    "live_check": live_check,
                },
            )
            logger.error("Startup preflight failed: %s", preflight.get("errors", []))
            if strict:
                raise RuntimeError(f"Startup preflight failed: {preflight.get('errors', [])}")

        # Slack bot (optional)
        if self.config.slack.enabled and self.config.slack.bot_token:
            try:
                from jarvis.slack_bot import JarvisSlackBot

                self._slack_bot = JarvisSlackBot(
                    bot_token=self.config.slack.bot_token,
                    app_token=self.config.slack.app_token,
                    default_channel=self.config.slack.default_channel,
                    research_channel=self.config.slack.research_channel,
                    event_collector=self.events,
                    orchestrator=self.orchestrator,
                )
                set_slack_bot(self._slack_bot)
                self._slack_task = asyncio.create_task(
                    self._slack_bot.start(),
                    name="jarvis-slack-bot",
                )
                self._slack_task.add_done_callback(self._on_slack_task_done)
                logger.info("Slack bot start requested")
            except ImportError:
                logger.warning("slack-bolt not installed, skipping Slack integration")
            except Exception as e:
                logger.exception("Slack bot failed to start: %s", e)

        # Voice client (optional)
        if self.config.voice.enabled and self.config.voice.api_key:
            try:
                from jarvis.voice import ElevenLabsVoiceClient

                self._voice_client = ElevenLabsVoiceClient(
                    api_key=self.config.voice.api_key,
                    agent_id=self.config.voice.agent_id,
                    event_collector=self.events,
                    auto_call_on_error=self.config.voice.auto_call_on_error,
                    auto_call_on_approval=self.config.voice.auto_call_on_approval,
                )
                set_voice_client(self._voice_client)
                await self._voice_client.connect()
                logger.info("Voice client connected")
            except ImportError:
                logger.warning("websockets not installed, skipping voice integration")
            except Exception as e:
                logger.exception("Voice client failed to connect: %s", e)

        self._running = True
        logger.info("Jarvis daemon started")
        self._start_idle_loop_if_enabled()

        # Block until stop is requested
        await self._stop_event.wait()

    async def stop(self) -> None:
        """Gracefully stop all services."""
        logger.info("Jarvis daemon stopping")

        if self._ws_server:
            await self._ws_server.stop()

        if self._slack_bot:
            try:
                await self._slack_bot.stop()
            except Exception as e:
                logger.exception("Slack bot stop error: %s", e)
        if self._slack_task:
            self._slack_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._slack_task
            self._slack_task = None

        if self._voice_client:
            try:
                await self._voice_client.disconnect()
            except Exception as e:
                logger.exception("Voice client disconnect error: %s", e)

        if self._idle_loop_task:
            self._idle_loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._idle_loop_task
            self._idle_loop_task = None

        try:
            await self.orchestrator.close()
        except Exception as e:
            logger.exception("Orchestrator shutdown error: %s", e)

        self._running = False
        self._stop_event.set()

    def _on_slack_task_done(self, task: asyncio.Task) -> None:
        """Surface Slack task failures and unexpected exits."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.exception("Slack bot task crashed: %s", exc)
        else:
            logger.warning("Slack bot task exited unexpectedly")

    def _start_idle_loop_if_enabled(self) -> None:
        # Always recover stale tasks on daemon start, even if idle research is disabled.
        self._normalize_stale_in_progress_tasks()
        # Idle research is opt-in. This prevents unintended Slack/channel spam.
        # To enable: set JARVIS_ENABLE_IDLE_AUTONOMY=1 *and* config.research.enabled=true.
        if os.environ.get("JARVIS_ENABLE_IDLE_AUTONOMY", "0") != "1":
            logger.info("Idle autonomy loop disabled (set JARVIS_ENABLE_IDLE_AUTONOMY=1 to enable)")
            return
        if not self.config.research.enabled:
            logger.info("Idle autonomy loop disabled by config")
            return
        if self._idle_loop_task and not self._idle_loop_task.done():
            return
        self._idle_loop_task = asyncio.create_task(self._idle_autonomy_loop())
        logger.info(
            "Idle autonomy loop started (interval=%s min, max/day=%s)",
            self.config.research.interval_minutes,
            self.config.research.max_runs_per_day,
        )

    async def _idle_autonomy_loop(self) -> None:
        """When Jarvis is idle, autonomously run self-improvement research tasks."""
        check_interval_seconds = 30
        while self._running:
            try:
                await asyncio.sleep(check_interval_seconds)
                if not self._running:
                    return
                if not self._should_run_idle_task():
                    continue
                selected_sources = self._select_idle_sources()
                if not selected_sources:
                    self.events.emit(
                        "idle_autonomy_skip",
                        "Idle research skipped: all configured sources recently researched",
                        metadata={"topic": self.config.research.topic},
                    )
                    self._mark_idle_run()
                    continue
                prompt = self._build_idle_research_prompt(selected_sources)
                self.events.emit(
                    "idle_autonomy_start",
                    "Jarvis started autonomous idle self-improvement task",
                    metadata={
                        "topic": self.config.research.topic,
                        "sources": selected_sources,
                        "slack_notify": False,
                        "origin": "idle_research",
                    },
                )
                result = await self.orchestrator.run_task(
                    prompt,
                    origin="idle_research",
                    emit_notifications=False,
                )
                self._mark_idle_run()
                summary = (result.get("output") or "").strip()[:2000]
                summary_lower = summary.lower()
                applied = result.get("status") == "completed" and (
                    "~/.codex/rules" in summary_lower or "agents.md" in summary_lower
                )
                for source in selected_sources:
                    self.orchestrator.memory.record_idle_research(
                        url=source,
                        topic=self.config.research.topic,
                        conclusion=(summary or result.get("status", "unknown"))[:1200],
                        evidence=summary[:2000],
                        applied=applied,
                        commit_sha=None,
                    )
                if self._slack_bot:
                    msg = (
                        "*Jarvis Idle Research Summary*\n"
                        f"- Topic: {self.config.research.topic}\n"
                        f"- Sources: {len(selected_sources)}\n"
                        f"- Status: {result.get('status')}\n"
                        f"- Conclusion: {(summary or 'No summary returned')[:2500]}"
                    )
                    await self._slack_bot.send_message(
                        msg,
                        channel=self.config.slack.research_channel,
                    )
                self.events.emit(
                    "idle_autonomy_complete",
                    "Jarvis completed autonomous idle self-improvement task",
                    metadata={
                        "topic": self.config.research.topic,
                        "sources": selected_sources,
                        "status": result.get("status"),
                        "slack_notify": False,
                        "origin": "idle_research",
                    },
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("Idle autonomy loop error: %s", e)
                self.events.emit(
                    "idle_autonomy_error",
                    str(e)[:200],
                    metadata={"error": str(e), "slack_notify": False, "origin": "idle_research"},
                )

    def _should_run_idle_task(self) -> bool:
        now = time.time()
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._idle_runs_day:
            self._idle_runs_day = today
            self._idle_runs_today = 0

        self._normalize_stale_in_progress_tasks()
        active_tasks = self.orchestrator.memory.list_tasks(
            self.orchestrator.project_path, status="in_progress"
        )
        if active_tasks:
            return False

        interval_seconds = max(300, int(self.config.research.interval_minutes) * 60)
        if (now - self._last_idle_run_ts) < interval_seconds:
            return False
        if self._idle_runs_today >= int(self.config.research.max_runs_per_day):
            return False
        return True

    def _normalize_stale_in_progress_tasks(self) -> None:
        """Unblock idle autonomy by failing abandoned in-progress tasks."""
        stale_after_seconds = int(os.environ.get("JARVIS_STALE_TASK_SECS", str(60 * 60)))
        if stale_after_seconds <= 0:
            return
        recovered = self.orchestrator.memory.recover_stale_in_progress_tasks(
            project_path=self.orchestrator.project_path,
            stale_after_seconds=stale_after_seconds,
            reason="Auto-marked stale by idle autonomy scheduler",
        )
        for task_id in recovered:
            self.events.emit(
                "task_stale_recovered",
                f"Auto-recovered stale in-progress task: {task_id}",
                task_id=task_id,
                metadata={"project": self.orchestrator.project_path},
            )

    def _mark_idle_run(self) -> None:
        self._last_idle_run_ts = time.time()
        self._idle_runs_today += 1

    def _load_bookmark_urls(self) -> list[str]:
        path = Path(self.config.research.bookmarks_file).expanduser()
        urls: list[str] = []
        if path.exists():
            for raw in path.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("http://") or line.startswith("https://"):
                    urls.append(line)

        # Optional: live X bookmark API ingestion is disabled by default.
        # Enable only with explicit opt-in.
        if self.config.research.enable_x_bookmarks_api:
            x_urls = self._load_x_bookmark_urls()
            for url in x_urls:
                if url not in urls:
                    urls.append(url)
        return urls

    def _load_x_bookmark_urls(self) -> list[str]:
        if not self.config.research.enable_x_bookmarks_api:
            return []
        token = os.environ.get("X_BOOKMARKS_ACCESS_TOKEN", "").strip()
        user_id = os.environ.get("X_BOOKMARKS_USER_ID", "").strip()
        if not token or not user_id:
            return []
        try:
            max_results = int(os.environ.get("JARVIS_X_BOOKMARKS_MAX_RESULTS", "50"))
        except ValueError:
            max_results = 50
        max_results = max(5, min(max_results, 100))

        params = {
            "max_results": str(max_results),
            "tweet.fields": "entities",
            "expansions": "attachments.media_keys",
        }
        url = (
            f"https://api.x.com/2/users/{user_id}/bookmarks?"
            f"{parse.urlencode(params)}"
        )
        req = request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "jarvis-idle-research/1.0",
            },
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=12) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            logger.warning("Failed to fetch X bookmarks: %s", exc)
            return []

        urls: list[str] = []
        for item in (payload.get("data") or []):
            entities = (item.get("entities") or {}) if isinstance(item, dict) else {}
            for u in (entities.get("urls") or []):
                expanded = str(u.get("expanded_url") or "").strip()
                if expanded.startswith(("http://", "https://")) and expanded not in urls:
                    urls.append(expanded)
        return urls

    def _select_idle_sources(self) -> list[str]:
        configured = list(self.config.research.source_urls or [])
        conversation_sources = self.orchestrator.memory.get_pending_research_sources(
            min_days_before_repeat=int(self.config.research.min_days_before_repeat),
            limit=200,
        )
        bookmarks = self._load_bookmark_urls()
        all_sources = []
        seen = set()
        for url in conversation_sources + configured + bookmarks:
            if url in seen:
                continue
            seen.add(url)
            all_sources.append(url)

        recent = self.orchestrator.memory.recent_research_urls(
            days=int(self.config.research.min_days_before_repeat)
        )
        fresh = [u for u in all_sources if u not in recent]
        if not fresh:
            return []
        return fresh[: max(1, int(self.config.research.max_sources_per_run))]

    def _build_idle_research_prompt(self, sources: list[str]) -> str:
        topic = self.config.research.topic
        sources_text = "\n".join(f"- {url}" for url in sources)
        return (
            "You are running an autonomous self-improvement cycle for Jarvis while user-idle.\n"
            "Objective: improve Jarvis architecture, reliability, and autonomous software engineering performance.\n"
            f"Priority research topic: {topic}\n"
            "Use only the listed sources for this cycle (do not re-research old items not listed).\n"
            "If strong evidence supports improvement, update global rules in ~/.codex/rules and the current repo AGENTS.md.\n"
            "Do not create or modify JARVIS.md in Jarvis core repo; reserve project JARVIS.md for external target projects.\n"
            "Keep markdown concise, actionable, and git-trackable. Do not spam channels.\n"
            "Prioritized sources for this cycle:\n"
            f"{sources_text}\n"
            "If a source is inaccessible, continue with remaining sources and report that explicitly.\n"
            "Always report explicit errors; never hide failures.\n"
            "At the end, summarize: discoveries, recommended workflow updates, what was changed, and URLs used."
        )


def main():
    """Entry point for python -m jarvis.daemon."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    project_path = sys.argv[1] if len(sys.argv) > 1 else None
    daemon = JarvisDaemon(project_path=project_path)
    asyncio.run(daemon.start())


if __name__ == "__main__":
    main()
