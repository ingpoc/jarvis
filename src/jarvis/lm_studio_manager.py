"""LM Studio manager with on-demand startup and memory management.

Optimized for workstation use:
- LM Studio only starts when needed (first request)
- Model loads only when processing
- Auto-unload after idle_timeout (default 5 minutes)
- Full process cleanup to free RAM
- Memory pressure monitoring
"""

import asyncio
import json
import logging
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LM_STUDIO_PORT = 1234
LM_STUDIO_BASE_URL = f"http://localhost:{LM_STUDIO_PORT}"
IDLE_TIMEOUT_SECONDS = 300  # 5 minutes
CHECK_INTERVAL_SECONDS = 30


class LMStudioManager:
    """Manages LM Studio lifecycle with memory optimization."""

    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._model_loaded: str | None = None
        self._last_used: float = 0
        self._monitor_task: asyncio.Task | None = None
        self._loading_lock = asyncio.Lock()
        self._check_interval = CHECK_INTERVAL_SECONDS
        self._idle_timeout = IDLE_TIMEOUT_SECONDS
        self._is_stopping = False

    @property
    def is_running(self) -> bool:
        """Check if LM Studio is running."""
        return self._process is not None and self._process.poll() is None

    @property
    def is_model_loaded(self) -> bool:
        """Check if a model is currently loaded."""
        return self._model_loaded is not None

    @property
    def current_model(self) -> str | None:
        """Get the currently loaded model ID."""
        return self._model_loaded

    def is_api_available(self) -> bool:
        """Check if LM Studio API is reachable (handles externally-started instances)."""
        try:
            req = urllib.request.Request(f"{LM_STUDIO_BASE_URL}/v1/models")
            urllib.request.urlopen(req, timeout=2)
            return True
        except Exception:
            return False

    @property
    def available_models(self) -> list[str]:
        """Get list of available models (from LM Studio)."""
        try:
            req = urllib.request.Request(f"{LM_STUDIO_BASE_URL}/v1/models")
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read())
                return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            logger.debug(f"Failed to get models: {e}")
            return []

    async def ensure_running(self) -> bool:
        """Ensure LM Studio is running, start if not."""
        if self.is_running or self.is_api_available():
            return True

        async with self._loading_lock:
            if self.is_running or self.is_api_available():
                return True

            logger.info("Starting LM Studio...")
            await self._start_lm_studio()

            if self._monitor_task is None or self._monitor_task.done():
                self._monitor_task = asyncio.create_task(self._idle_monitor())

            return self.is_running or self.is_api_available()

    async def _start_lm_studio(self) -> None:
        """Start LM Studio process."""
        lm_studio_path = self._find_lm_studio()
        if not lm_studio_path:
            raise RuntimeError("LM Studio not found")

        env = os.environ.copy()
        env["LMSTUDIO_PORT"] = str(LM_STUDIO_PORT)

        self._process = subprocess.Popen(
            [str(lm_studio_path)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        await self._wait_for_ready()
        logger.info("LM Studio started")

    def _find_lm_studio(self) -> Path | None:
        """Find LM Studio executable."""
        possible_paths = [
            Path("/Applications/LM Studio.app/Contents/MacOS/LM Studio"),
            Path.home() / "Applications" / "LM Studio.app" / "Contents" / "MacOS" / "LM Studio",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return None

    async def _wait_for_ready(self, timeout: float = 30.0) -> None:
        """Wait for LM Studio API to be ready."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                req = urllib.request.Request(f"{LM_STUDIO_BASE_URL}/v1/models")
                urllib.request.urlopen(req, timeout=2)
                return
            except Exception:
                await asyncio.sleep(0.5)
        raise TimeoutError("LM Studio failed to start")

    async def load_model(self, model_id: str) -> bool:
        """Load a model into LM Studio memory by sending a minimal inference request."""
        if not self.is_running and not self.is_api_available():
            await self.ensure_running()

        if self._model_loaded == model_id:
            return True

        logger.info(f"Loading model into memory: {model_id}")

        # Send a valid minimal request — LM Studio loads the model on first use
        payload = json.dumps({
            "model": model_id,
            "messages": [{"role": "user", "content": "."}],
            "max_tokens": 1,
        }).encode()

        req = urllib.request.Request(
            f"{LM_STUDIO_BASE_URL}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            loop = asyncio.get_event_loop()
            # Large models can take 60–120s to load — don't block event loop
            await loop.run_in_executor(
                None, lambda: urllib.request.urlopen(req, timeout=120)
            )
            self._model_loaded = model_id
            self._last_used = time.time()
            logger.info(f"Model loaded: {model_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model {model_id}: {e}")
            return False

    async def unload_model(self) -> None:
        """Unload current model to free memory."""
        if not self._model_loaded:
            return

        try:
            req = urllib.request.Request(
                f"{LM_STUDIO_BASE_URL}/v1/model/unload",
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.debug(f"Model unload request: {e}")

        self._model_loaded = None
        logger.info("Model unloaded")

    async def _idle_monitor(self) -> None:
        """Monitor for idle and cleanup resources."""
        while not self._is_stopping:
            await asyncio.sleep(self._check_interval)

            if not self.is_running and not self.is_api_available():
                continue

            idle_time = time.time() - self._last_used
            if idle_time > self._idle_timeout and self._model_loaded:
                logger.info(f"Idle for {idle_time:.0f}s, unloading model")
                await self.unload_model()

    async def stop(self) -> None:
        """Stop LM Studio completely."""
        self._is_stopping = True

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        if self._model_loaded:
            await self.unload_model()

        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()

            self._process = None
            logger.info("LM Studio stopped")

    def record_usage(self) -> None:
        """Record that model was used (resets idle timer)."""
        self._last_used = time.time()

    def get_stats(self) -> dict[str, Any]:
        """Get manager stats."""
        return {
            "running": self.is_running,
            "model_loaded": self._model_loaded,
            "idle_seconds": time.time() - self._last_used if self.is_running else 0,
            "available_models": self.available_models if self.is_running else [],
        }


_lm_studio_manager: LMStudioManager | None = None


def get_lm_studio_manager() -> LMStudioManager:
    """Get the global LM Studio manager instance."""
    global _lm_studio_manager
    if _lm_studio_manager is None:
        _lm_studio_manager = LMStudioManager()
    return _lm_studio_manager
