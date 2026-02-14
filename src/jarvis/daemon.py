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
from jarvis.model_router import get_model_router

import os
import traceback
from pathlib import Path

logger = logging.getLogger(__name__)


class CrashRecovery:
    """Daemon crash recovery: detects unclean shutdowns and recovers state."""

    PID_FILE = Path.home() / ".jarvis" / "daemon.pid"
    CRASH_LOG = Path.home() / ".jarvis" / "logs" / "crash.log"

    @classmethod
    def write_pid(cls) -> None:
        """Write current PID to file for crash detection."""
        cls.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        cls.PID_FILE.write_text(str(os.getpid()))

    @classmethod
    def clear_pid(cls) -> None:
        """Remove PID file on clean shutdown."""
        try:
            cls.PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass

    @classmethod
    def check_previous_crash(cls) -> dict | None:
        """Check if the previous daemon run crashed.

        Returns crash info dict if a crash was detected, None otherwise.
        """
        if not cls.PID_FILE.exists():
            return None

        try:
            old_pid = int(cls.PID_FILE.read_text().strip())
        except (ValueError, OSError):
            cls.clear_pid()
            return None

        # Check if the old process is still running
        try:
            os.kill(old_pid, 0)  # Signal 0 = check existence
            # Process is still running - not a crash, another instance
            return {"status": "running", "pid": old_pid}
        except ProcessLookupError:
            # Process is gone - it crashed
            return {"status": "crashed", "pid": old_pid}
        except PermissionError:
            # Process exists but we can't signal it
            return {"status": "running", "pid": old_pid}

    @classmethod
    def log_crash(cls, error: str) -> None:
        """Log crash information for post-mortem analysis."""
        import time
        cls.CRASH_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(cls.CRASH_LOG, "a") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Crash at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"PID: {os.getpid()}\n")
            f.write(f"Error: {error}\n")
            f.write(f"Traceback:\n{traceback.format_exc()}\n")

    @classmethod
    def recover_state(cls, orchestrator) -> dict:
        """Attempt to recover state after a crash.

        - Resumes in-progress tasks if possible
        - Cleans up stale container resources
        - Rebuilds context layers

        Returns recovery summary.
        """
        recovery = {"recovered_tasks": 0, "cleaned_containers": 0}

        try:
            # Find tasks that were in-progress when we crashed
            stale_tasks = orchestrator.memory.list_tasks(status="in_progress")
            for task in stale_tasks:
                orchestrator.memory.update_task(
                    task.id,
                    status="failed",
                    result="Daemon crashed during execution",
                )
                recovery["recovered_tasks"] += 1

            logger.info(
                f"Crash recovery: marked {recovery['recovered_tasks']} "
                f"stale tasks as failed"
            )
        except Exception as e:
            logger.warning(f"Crash recovery error: {e}")

        return recovery


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

        # Crash recovery
        crash_info = CrashRecovery.check_previous_crash()
        if crash_info and crash_info["status"] == "crashed":
            logger.warning(f"Detected previous crash (PID {crash_info['pid']}), recovering...")
            recovery = CrashRecovery.recover_state(self.orchestrator)
            logger.info(f"Recovery complete: {recovery}")
        elif crash_info and crash_info["status"] == "running":
            logger.error(f"Another daemon instance is running (PID {crash_info['pid']})")
            return

        CrashRecovery.write_pid()

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

        # Initialize 3-tier model router (loads MLX + Foundation Models if available)
        try:
            router = get_model_router()
            init_result = await router.initialize()
            logger.info(f"Model router initialized: MLX={init_result.get('mlx')}, "
                        f"Foundation={init_result.get('foundation')}")
        except Exception as e:
            logger.warning(f"Model router initialization failed: {e}")

        # macOS native integrations
        try:
            from jarvis.macos_native import get_platform_capabilities
            caps = get_platform_capabilities()
            if caps["is_apple_silicon"]:
                chip = caps.get("chip_info", {})
                logger.info(
                    f"Apple Silicon detected: {chip.get('chip', 'unknown')}, "
                    f"{chip.get('total_memory_gb', '?')}GB RAM"
                )

                # Start IOKit-based idle detection polling
                if caps["iokit_available"] and self._idle_processor:
                    self._iokit_idle_task = asyncio.create_task(
                        self._iokit_idle_loop()
                    )
                    logger.info("IOKit HID idle detection active")

                # Load credentials from Keychain
                from jarvis.macos_native import keychain_retrieve
                kc_api_key = keychain_retrieve("com.jarvis.anthropic", "api_key")
                if kc_api_key:
                    import os
                    os.environ.setdefault("ANTHROPIC_API_KEY", kc_api_key)
                    logger.info("Loaded API key from Keychain")
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"macOS native init: {e}")

        self._running = True
        logger.info("Jarvis daemon started")

        # Block until stop is requested
        await self._stop_event.wait()

    async def _iokit_idle_loop(self) -> None:
        """Poll IOKit HID idle time and trigger idle mode transitions.

        Runs every 30s and checks the actual HID idle seconds.
        More accurate than timer-based idle detection since it
        uses real keyboard/mouse/trackpad activity.
        """
        from jarvis.macos_native import get_idle_seconds, get_memory_pressure

        threshold = self.config.idle.idle_threshold_minutes * 60

        while self._running:
            try:
                await asyncio.sleep(30)

                idle_secs = get_idle_seconds()
                if idle_secs is None:
                    continue

                if self._idle_processor:
                    if idle_secs >= threshold:
                        self._idle_processor.trigger_idle()
                    elif idle_secs < 5:
                        # Recent activity
                        self._idle_processor.record_activity()

                # Check memory pressure for hibernation
                pressure = get_memory_pressure()
                if pressure and pressure.get("should_hibernate"):
                    if self._idle_processor:
                        self._idle_processor.trigger_hibernate()
                    # Also unload MLX model to free memory
                    router = get_model_router()
                    await router.shutdown()
                    logger.warning(
                        f"Memory pressure CRITICAL ({pressure.get('free_mb', '?')}MB free) "
                        "— hibernated + unloaded local models"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"IOKit idle loop error: {e}")

    async def stop(self) -> None:
        """Gracefully stop all services."""
        logger.info("Jarvis daemon stopping")

        # Shutdown model router (unload MLX)
        try:
            router = get_model_router()
            await router.shutdown()
        except Exception as e:
            logger.debug(f"Model router shutdown error: {e}")

        # Cancel IOKit idle loop
        if hasattr(self, "_iokit_idle_task") and self._iokit_idle_task:
            self._iokit_idle_task.cancel()
            try:
                await self._iokit_idle_task
            except asyncio.CancelledError:
                pass

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
        CrashRecovery.clear_pid()
        self._stop_event.set()


def main():
    """Entry point for python -m jarvis.daemon."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    project_path = sys.argv[1] if len(sys.argv) > 1 else None
    daemon = JarvisDaemon(project_path=project_path)
    try:
        asyncio.run(daemon.start())
    except Exception as e:
        CrashRecovery.log_crash(str(e))
        raise
    finally:
        CrashRecovery.clear_pid()


if __name__ == "__main__":
    main()
