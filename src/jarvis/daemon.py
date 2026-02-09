"""Jarvis daemon: persistent background process with WS + Slack + Voice + Idle."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from jarvis.config import JarvisConfig, ensure_jarvis_home
from jarvis.notifications import set_slack_bot, set_voice_client
from jarvis.orchestrator import JarvisOrchestrator
from jarvis.ws_server import JarvisWSServer
from jarvis.mcp_health import health_check_all_servers, filter_healthy_servers, notify_health_failures

logger = logging.getLogger(__name__)


class JarvisDaemon:
    """Long-running daemon: WebSocket bridge + optional Slack/Voice + Idle processing."""

    def __init__(self, project_path: str | None = None):
        ensure_jarvis_home()
        self.config = JarvisConfig.load()
        self.orchestrator = JarvisOrchestrator(project_path)
        self.events = self.orchestrator.events
        self._ws_server: JarvisWSServer | None = None
        self._slack_bot = None
        self._voice_client = None
        self._idle_processor = None
        self._file_watcher = None
        self._running = False
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start all daemon services."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Health check MCP servers before starting
        logger.info("Running MCP server health checks...")
        mcp_servers = {
            "jarvis-container": self.orchestrator.container_server,
            "jarvis-git": self.orchestrator.git_server,
            "jarvis-review": self.orchestrator.review_server,
            "jarvis-browser": self.orchestrator.browser_server,
        }

        health_results = await health_check_all_servers(mcp_servers, timeout=2.0)
        logger.info(
            f"MCP health check complete: {health_results['healthy_count']}/{health_results['total_count']} healthy"
        )

        # Notify about failures and quarantine unhealthy servers
        if health_results["unhealthy_count"] > 0:
            await notify_health_failures(health_results)

            # Remove unhealthy servers from orchestrator's MCP config
            healthy_servers = filter_healthy_servers(mcp_servers, health_results)
            quarantined = set(mcp_servers.keys()) - set(healthy_servers.keys())
            if quarantined:
                logger.warning(f"Quarantined MCP servers: {', '.join(quarantined)}")

        # Build context layers asynchronously for use in system prompt
        try:
            from jarvis.context_layers import build_context_layers
            self.orchestrator._cached_context_layers = await build_context_layers(
                self.orchestrator.project_path, ["L1", "L2"]
            )
            logger.info("Context layers L1-L2 built successfully")
        except Exception as e:
            logger.warning(f"Context layers build failed: {e}")

        # WebSocket server (always)
        self._ws_server = JarvisWSServer(
            event_collector=self.events,
            orchestrator=self.orchestrator,
        )
        await self._ws_server.start()

        # File system watcher (for knowledge invalidation)
        try:
            from jarvis.fs_watcher import FileSystemWatcher
            self._file_watcher = FileSystemWatcher(
                project_path=self.orchestrator.project_path,
                memory=self.orchestrator.memory,
                poll_interval=self.config.idle.file_watcher_poll_interval,
                debounce=self.config.idle.file_watcher_debounce,
            )
            await self._file_watcher.start()
            logger.info("File watcher started")
        except Exception as e:
            logger.warning(f"File watcher failed to start: {e}")

        # Idle mode processor (background tasks during inactivity)
        if self.config.idle.enable_background_processing:
            try:
                from jarvis.idle_mode import IdleModeProcessor
                self._idle_processor = IdleModeProcessor(
                    memory=self.orchestrator.memory,
                    project_path=self.orchestrator.project_path,
                    idle_threshold_minutes=self.config.idle.idle_threshold_minutes,
                )
                # Connect file watcher changes to idle processor activity tracking
                if self._file_watcher:
                    self._file_watcher.add_change_callback(
                        lambda _: self._idle_processor.record_activity()
                    )
                await self._idle_processor.start()
                logger.info("Idle mode processor started")
            except Exception as e:
                logger.warning(f"Idle mode processor failed to start: {e}")

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
                await self._slack_bot.start()
                logger.info("Slack bot started")
            except ImportError:
                logger.warning("slack-bolt not installed, skipping Slack integration")
            except Exception as e:
                logger.error(f"Slack bot failed to start: {e}")

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
                logger.error(f"Voice client failed to connect: {e}")

        # Copy bootstrap skills on first daemon start
        try:
            from jarvis.skill_generator import copy_bootstrap_skills
            copied = copy_bootstrap_skills()
            if copied:
                logger.info(f"Installed {len(copied)} bootstrap skills: {', '.join(copied)}")
        except Exception as e:
            logger.warning(f"Bootstrap skills install failed: {e}")

        self._running = True
        logger.info("Jarvis daemon started")

        # Block until stop is requested
        await self._stop_event.wait()

    async def stop(self) -> None:
        """Gracefully stop all services."""
        logger.info("Jarvis daemon stopping")

        if self._file_watcher:
            try:
                await self._file_watcher.stop()
            except Exception as e:
                logger.warning(f"File watcher stop error: {e}")

        if self._idle_processor:
            try:
                await self._idle_processor.stop()
            except Exception as e:
                logger.warning(f"Idle processor stop error: {e}")

        if self._ws_server:
            await self._ws_server.stop()

        if self._slack_bot:
            try:
                await self._slack_bot.stop()
            except Exception as e:
                logger.warning(f"Slack bot stop error: {e}")

        if self._voice_client:
            try:
                await self._voice_client.disconnect()
            except Exception as e:
                logger.warning(f"Voice client disconnect error: {e}")

        self._running = False
        self._stop_event.set()


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
