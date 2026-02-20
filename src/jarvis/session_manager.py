"""Session manager for per-channel ClaudeSDKClient isolation.

Prevents context bleeding between different channels (A2A, CLI, WS).
"""

import asyncio
import logging
from typing import Any

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

from jarvis.config import JarvisConfig

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages per-channel ClaudeSDKClient instances."""

    _instance: "SessionManager | None" = None
    _clients: dict[str, ClaudeSDKClient]
    _config: JarvisConfig
    _lock: asyncio.Lock

    def __init__(self, config: JarvisConfig):
        self._clients = {}
        self._config = config
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "SessionManager":
        if cls._instance is None:
            cls._instance = cls(JarvisConfig.load())
        return cls._instance

    async def get_client(
        self,
        channel_id: str,
        options: ClaudeAgentOptions | None = None,
    ) -> ClaudeSDKClient:
        """Get or create a ClaudeSDKClient for the given channel.

        Creates the client and calls connect() exactly once per channel.
        """
        async with self._lock:
            if channel_id not in self._clients:
                client = ClaudeSDKClient(options=options)
                await client.connect()
                self._clients[channel_id] = client
                logger.debug(f"Created and connected client for channel {channel_id}")
            return self._clients[channel_id]

    async def close_client(self, channel_id: str) -> None:
        """Close and remove a specific client.

        Calls disconnect() to properly shut down the SDK client.
        """
        async with self._lock:
            if channel_id in self._clients:
                client = self._clients.pop(channel_id)
                try:
                    await client.disconnect()
                    logger.debug(f"Disconnected client for channel {channel_id}")
                except Exception as e:
                    logger.warning(f"Error disconnecting client for {channel_id}: {e}")

    async def close_all(self) -> None:
        """Close all clients on shutdown.

        Calls disconnect() on each client for proper SDK lifecycle.
        """
        async with self._lock:
            for channel_id, client in self._clients.items():
                try:
                    await client.disconnect()
                    logger.debug(f"Disconnected client for channel {channel_id}")
                except Exception as e:
                    logger.warning(f"Error disconnecting client for {channel_id}: {e}")
            self._clients.clear()

    def get_active_channel_ids(self) -> list[str]:
        """Get list of active channel IDs."""
        return list(self._clients.keys())
