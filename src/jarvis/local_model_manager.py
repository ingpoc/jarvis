"""Unified Local Model Manager.

Coordinates between Apple Foundation Models (direct) and LM Studio for optimal performance.

Provider Selection:
- foundation-models: Direct AFM Python integration (fastest, ~1s latency)
- lmstudio-* : LM Studio with on-demand startup (flexible model selection)
- mlx-* : Direct MLX (future expansion)

Memory Management:
- Only one provider active at a time
- Automatic cleanup when switching providers
- Idle timeout for LM Studio
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
from jarvis.lm_studio_manager import get_lm_studio_manager

logger = logging.getLogger(__name__)


class ModelProviderType(Enum):
    """Type of model provider."""

    ANTHROPIC = "anthropic"
    FOUNDATION = "foundation"
    LMSTUDIO = "lmstudio"
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

    LM_STUDIO_MODEL_PATTERNS = [
        "qwen2.5-coder",
        "qwen3",
        "deepseek",
        "gpt-oss",
        "llama",
        "mistral",
        "phi",
        "gemma",
        "mixtral",
    ]

    def get_provider_from_model(self, model_id: str) -> ModelProviderType:
        """Determine provider type from model ID."""
        if model_id == "foundation-models":
            return ModelProviderType.FOUNDATION
        elif model_id.startswith("lmstudio-"):
            return ModelProviderType.LMSTUDIO
        elif "/" in model_id:
            return ModelProviderType.LMSTUDIO
        elif any(p in model_id.lower() for p in self.LM_STUDIO_MODEL_PATTERNS):
            return ModelProviderType.LMSTUDIO
        elif model_id.startswith("mlx-"):
            return ModelProviderType.MLX
        else:
            return ModelProviderType.ANTHROPIC

    async def switch_model(self, model_id: str) -> dict[str, Any]:
        """Switch to a different model provider."""
        new_provider = self.get_provider_from_model(model_id)

        if new_provider == self._current_provider and model_id == self._current_model_id:
            return {"success": True, "provider": new_provider.value, "model": model_id}

        logger.info(f"Switching model: {self._current_model_id} -> {model_id}")

        await self._cleanup_current_provider()

        if new_provider == ModelProviderType.FOUNDATION:
            return await self._setup_foundation(model_id)
        elif new_provider == ModelProviderType.LMSTUDIO:
            return await self._setup_lmstudio(model_id)
        else:
            return {"error": f"Provider {new_provider.value} not implemented"}

    async def _cleanup_current_provider(self) -> None:
        """Clean up current provider resources."""
        if self._current_provider == ModelProviderType.FOUNDATION:
            afm_close()
        elif self._current_provider == ModelProviderType.LMSTUDIO:
            lm = get_lm_studio_manager()
            await lm.unload_model()

        self._current_provider = None

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
            "info": "Direct AFM integration (~1s latency)",
        }

    async def _setup_lmstudio(self, model_id: str) -> dict[str, Any]:
        """Setup LM Studio provider with on-demand startup."""
        lm = get_lm_studio_manager()

        running = await lm.ensure_running()
        if not running:
            return {"error": "Failed to start LM Studio"}

        await lm.load_model(model_id)

        self._current_provider = ModelProviderType.LMSTUDIO
        self._current_model_id = model_id

        return {
            "success": True,
            "provider": "lmstudio",
            "model": model_id,
            "info": "LM Studio started on-demand",
        }

    async def generate(self, prompt: str) -> dict[str, Any]:
        """Generate response from current provider."""
        if self._current_provider == ModelProviderType.FOUNDATION:
            return afm_generate(prompt)
        elif self._current_provider == ModelProviderType.LMSTUDIO:
            lm = get_lm_studio_manager()
            lm.record_usage()
            return await self._lmstudio_generate(prompt)
        else:
            raise RuntimeError("No local model provider active")

    async def _lmstudio_generate(self, prompt: str) -> dict[str, Any]:
        """Generate via LM Studio API."""
        import asyncio
        import json
        import urllib.request

        lm = get_lm_studio_manager()
        model_id = self._current_model_id

        payload = json.dumps(
            {
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1024,
            }
        ).encode()

        req = urllib.request.Request(
            "http://localhost:1234/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None, lambda: urllib.request.urlopen(req, timeout=60)
            )
            data = json.loads(response.read())
            content = data["choices"][0]["message"]["content"]
            return {"content": content, "model": model_id}
        except Exception as e:
            logger.error(f"LM Studio generation failed: {e}")
            raise

    def get_status(self) -> dict[str, Any]:
        """Get current provider status."""
        status = {
            "provider": self._current_provider.value if self._current_provider else None,
            "model": self._current_model_id,
            "afm_available": is_afm_available(),
            "lmstudio": get_lm_studio_manager().get_stats(),
        }

        if is_afm_available():
            status["afm_stats"] = afm_get_stats()

        return status

    async def shutdown(self) -> None:
        """Shutdown all providers."""
        await self._cleanup_current_provider()
        lm = get_lm_studio_manager()
        await lm.stop()


_local_model_manager: LocalModelManager | None = None


def get_local_model_manager() -> LocalModelManager:
    """Get the global local model manager."""
    global _local_model_manager
    if _local_model_manager is None:
        _local_model_manager = LocalModelManager()
    return _local_model_manager
