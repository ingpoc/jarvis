"""Jarvis daemon: persistent background process with WS + Slack + Voice."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

import os

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
        self._remote_server = None
        self._rest_app = None
        self._rest_runner = None
        self._slack_bot = None
        self._voice_client = None
        self._running = False
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start all daemon services."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Local WebSocket server (always)
        self._ws_server = JarvisWSServer(
            event_collector=self.events,
            orchestrator=self.orchestrator,
        )
        await self._ws_server.start()

        # Remote WSS server (if enabled)
        if self._remote_enabled():
            await self._start_remote_server()

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

        if self._remote_server:
            await self._remote_server.stop()

        if self._rest_runner:
            await self._rest_runner.cleanup()

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

    def _remote_enabled(self) -> bool:
        """Check if remote server is enabled."""
        return os.getenv("JARVIS_REMOTE_ENABLED", "false").lower() in ("true", "1", "yes")

    async def _start_remote_server(self) -> None:
        """Start remote WSS server and REST API."""
        try:
            from jarvis.remote_server import JarvisRemoteServer, RESTAPIHandler
            from jarvis.auth import Authenticator
            from aiohttp import web

            # Initialize authenticator
            jwt_secret = os.getenv("JARVIS_JWT_SECRET")
            if not jwt_secret:
                logger.warning("JARVIS_JWT_SECRET not set, using default (UNSAFE)")
                jwt_secret = "change-me-in-production"

            authenticator = Authenticator(
                secret=jwt_secret,
                expiry_seconds=int(os.getenv("JARVIS_JWT_EXPIRY", "86400")),
                max_devices=int(os.getenv("MAX_DEVICES", "10")),
            )

            # Start remote WSS server
            remote_port = int(os.getenv("JARVIS_REMOTE_PORT", "9848"))
            remote_bind = os.getenv("JARVIS_REMOTE_BIND", "0.0.0.0")

            self._remote_server = JarvisRemoteServer(
                event_collector=self.events,
                orchestrator=self.orchestrator,
                authenticator=authenticator,
                port=remote_port,
                bind=remote_bind,
            )
            await self._remote_server.start()
            logger.info(f"Remote WSS server started on {remote_bind}:{remote_port}")

            # Start REST API
            rest_handler = RESTAPIHandler(authenticator, self._remote_server)
            self._rest_app = await rest_handler.create_app()

            if self._rest_app:
                rest_port = int(os.getenv("JARVIS_REST_PORT", "9849"))
                self._rest_runner = web.AppRunner(self._rest_app)
                await self._rest_runner.setup()
                site = web.TCPSite(self._rest_runner, "0.0.0.0", rest_port)
                await site.start()
                logger.info(f"REST API started on port {rest_port}")

                # Start Tailscale funnel if enabled
                if os.getenv("TAILSCALE_ENABLED", "false").lower() == "true":
                    await self._start_tailscale_funnel(remote_port)

        except ImportError as e:
            logger.warning(f"Remote server dependencies missing: {e}")
        except Exception as e:
            logger.error(f"Remote server failed to start: {e}")

    async def _start_tailscale_funnel(self, port: int) -> None:
        """Start Tailscale funnel for remote access."""
        try:
            import asyncio.subprocess

            proc = await asyncio.create_subprocess_exec(
                "tailscale", "funnel", str(port),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait a bit to check if it started successfully
            await asyncio.sleep(2)

            if proc.returncode is not None:
                stderr = await proc.stderr.read()
                logger.warning(f"Tailscale funnel failed: {stderr.decode()}")
            else:
                logger.info(f"Tailscale funnel started for port {port}")

                # Get Tailscale IP
                ip_proc = await asyncio.create_subprocess_exec(
                    "tailscale", "ip", "-4",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await ip_proc.communicate()
                if ip_proc.returncode == 0:
                    ts_ip = stdout.decode().strip()
                    logger.info(f"Tailscale IP: {ts_ip}")

        except FileNotFoundError:
            logger.warning("Tailscale not installed")
        except Exception as e:
            logger.error(f"Tailscale funnel error: {e}")


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
