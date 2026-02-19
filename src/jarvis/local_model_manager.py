"""Unified local model manager.

Coordinates local model execution paths used by Jarvis.

Provider Selection:
- foundation-models: Direct AFM Python integration
- mlx-*: Reserved for future direct MLX integration

Memory Management:
- Only one local provider active at a time
- Automatic cleanup when switching providers
"""

import logging
from enum import Enum
from typing import Any

from jarvis.afm_integration import (
    close_session as afm_close,
    generate as afm_generate,
    get_stats as afm_get_stats,
    is_afm_available,
)

logger = logging.getLogger(__name__)


class ModelProviderType(Enum):
    """Type of model provider."""

    ANTHROPIC = "anthropic"
    FOUNDATION = "foundation"
    MLX = "mlx"


class LocalModelManager:
    """Unified manager for local model providers."""

    def __init__(self):
        self._current_provider: ModelProviderType | None = None
        self._current_model_id: str | None = None

    @property
    def provider(self) -> ModelProviderType | None:
        return self._current_provider

    @property
    def current_model(self) -> str | None:
        return self._current_model_id

    def get_provider_from_model(self, model_id: str) -> ModelProviderType:
        """Determine provider type from model ID."""
        if model_id == "foundation-models":
            return ModelProviderType.FOUNDATION
        if model_id.startswith("mlx-"):
            return ModelProviderType.MLX
        return ModelProviderType.ANTHROPIC

    async def switch_model(self, model_id: str) -> dict[str, Any]:
        """Switch to a different model provider."""
        new_provider = self.get_provider_from_model(model_id)

        if new_provider == self._current_provider and model_id == self._current_model_id:
            return {"success": True, "provider": new_provider.value, "model": model_id}

        logger.info("Switching model: %s -> %s", self._current_model_id, model_id)

        await self._cleanup_current_provider()

        if new_provider == ModelProviderType.FOUNDATION:
            return await self._setup_foundation(model_id)

        return {"error": f"Provider {new_provider.value} is not a local runtime"}

    async def _cleanup_current_provider(self) -> None:
        """Clean up current provider resources."""
        if self._current_provider == ModelProviderType.FOUNDATION:
            afm_close()

        self._current_provider = None
        self._current_model_id = None

    async def _setup_foundation(self, model_id: str) -> dict[str, Any]:
        """Setup Foundation Models provider."""
        if not is_afm_available():
            return {"error": "Foundation Models not available"}

        self._current_provider = ModelProviderType.FOUNDATION
        self._current_model_id = model_id

        return {
            "success": True,
            "provider": "foundation",
            "model": model_id,
            "info": "Direct AFM integration",
        }

    async def generate(self, prompt: str) -> dict[str, Any]:
        """Generate response from current provider."""
        if self._current_provider == ModelProviderType.FOUNDATION:
            return afm_generate(prompt)
        raise RuntimeError("No local model provider active")

    def get_status(self) -> dict[str, Any]:
        """Get current provider status."""
        status = {
            "provider": self._current_provider.value if self._current_provider else None,
            "model": self._current_model_id,
            "afm_available": is_afm_available(),
        }

        if is_afm_available():
            status["afm_stats"] = afm_get_stats()

        return status

    async def shutdown(self) -> None:
        """Shutdown all providers."""
        await self._cleanup_current_provider()


_local_model_manager: LocalModelManager | None = None


def get_local_model_manager() -> LocalModelManager:
    """Get the global local model manager."""
    global _local_model_manager
    if _local_model_manager is None:
        _local_model_manager = LocalModelManager()
    return _local_model_manager
