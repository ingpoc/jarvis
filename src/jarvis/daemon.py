"""Jarvis daemon: persistent background process with WS + Slack + Voice."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import sys
import time
from datetime import datetime

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

        # Slack bot (optional)
        if self.config.slack.enabled and self.config.slack.bot_token:
            try:
                from jarvis.slack_bot import JarvisSlackBot

                self._slack_bot = JarvisSlackBot(
                    bot_token=self.config.slack.bot_token,
                    app_token=self.config.slack.app_token,
                    default_channel=self.config.slack.default_channel,
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
        if not self.config.research.enabled:
            logger.info("Idle autonomy loop disabled by config")
            return
        # Recover stale tasks immediately on daemon start so idle autonomy isn't blocked.
        self._normalize_stale_in_progress_tasks()
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
                prompt = self._build_idle_research_prompt()
                self.events.emit(
                    "idle_autonomy_start",
                    "Jarvis started autonomous idle self-improvement task",
                    metadata={"topic": self.config.research.topic},
                )
                await self.orchestrator.run_task(prompt)
                self._mark_idle_run()
                self.events.emit(
                    "idle_autonomy_complete",
                    "Jarvis completed autonomous idle self-improvement task",
                    metadata={"topic": self.config.research.topic},
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("Idle autonomy loop error: %s", e)
                self.events.emit("idle_autonomy_error", str(e)[:200], metadata={"error": str(e)})

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
        stale_after_seconds = 60 * 60  # 1 hour
        now = time.time()
        in_progress = self.orchestrator.memory.list_tasks(
            self.orchestrator.project_path, status="in_progress"
        )
        for task in in_progress:
            if (now - task.updated_at) < stale_after_seconds:
                continue
            self.orchestrator.memory.update_task(
                task.id,
                status="failed",
                result=(task.result or "")[:4500] + "\n\n[Auto-marked stale by idle autonomy scheduler]",
            )
            self.events.emit(
                "task_stale_recovered",
                f"Auto-recovered stale in-progress task: {task.id}",
                task_id=task.id,
                metadata={"description": task.description[:200]},
            )

    def _mark_idle_run(self) -> None:
        self._last_idle_run_ts = time.time()
        self._idle_runs_today += 1

    def _build_idle_research_prompt(self) -> str:
        topic = self.config.research.topic
        sources = self.config.research.source_urls or []
        sources_text = "\n".join(f"- {url}" for url in sources)
        return (
            "You are running an autonomous self-improvement cycle for Jarvis while user-idle.\n"
            "Objective: improve Jarvis architecture, reliability, and autonomous software engineering performance.\n"
            f"Priority research topic: {topic}\n"
            "Research current posts/articles/repos (including @bcherny and Claude Code resources), extract concrete techniques,\n"
            "propose implementation-ready improvements for Jarvis, and apply safe, local improvements if clearly beneficial.\n"
            "Prioritized sources to study in this cycle:\n"
            f"{sources_text}\n"
            "If a source is inaccessible, continue with remaining sources and report that explicitly.\n"
            "Always report explicit errors; never hide failures.\n"
            "At the end, summarize: discoveries, recommended changes, what was changed, and cite URLs used."
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
