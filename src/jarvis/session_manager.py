"""Session manager placeholder for OpenCode-only runtime.

Legacy Claude SDK session pooling has been removed.
"""

import asyncio
import logging
from typing import Any

from jarvis.config import JarvisConfig

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages per-channel client objects.

    In OpenCode-only mode we do not provision Claude SDK clients. This
    class remains as a compatibility surface for callers that still import it.
    """

    _instance: "SessionManager | None" = None
    _clients: dict[str, Any]
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
        options: Any | None = None,
    ) -> Any:
        """OpenCode-only mode does not create SDK clients."""
        _ = (channel_id, options)
        raise RuntimeError(
            "SessionManager.get_client is unavailable: Claude Agent SDK runtime was removed."
        )

    async def close_client(self, channel_id: str) -> None:
        """Close and remove a specific client if present."""
        async with self._lock:
            if channel_id in self._clients:
                client = self._clients.pop(channel_id)
                try:
                    disconnect = getattr(client, "disconnect", None)
                    if callable(disconnect):
                        await disconnect()
                    logger.debug("Disconnected client for channel %s", channel_id)
                except Exception as e:
                    logger.warning("Error disconnecting client for %s: %s", channel_id, e)

    async def close_all(self) -> None:
        """Close all tracked clients on shutdown."""
        async with self._lock:
            for channel_id, client in self._clients.items():
                try:
                    disconnect = getattr(client, "disconnect", None)
                    if callable(disconnect):
                        await disconnect()
                    logger.debug("Disconnected client for channel %s", channel_id)
                except Exception as e:
                    logger.warning("Error disconnecting client for %s: %s", channel_id, e)
            self._clients.clear()

    def get_active_channel_ids(self) -> list[str]:
        """Get list of active channel IDs."""
        return list(self._clients.keys())
