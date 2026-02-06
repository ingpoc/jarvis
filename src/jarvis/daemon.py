"""Jarvis daemon: persistent background process with WS + Slack + Voice."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

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
        self._voice_client = None
        self._running = False
        self._stop_event = asyncio.Event()

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

        self._running = True
        logger.info("Jarvis daemon started")

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
