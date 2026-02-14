"""MLX-based local inference for Qwen3 4B on Apple Silicon.

Provides local model inference for:
- Context pre-filtering (select relevant files from project)
- Simple task execution (rename, fix typo, etc.)
- Task classification (route to appropriate tier)
- Offline fallback when cloud API is unavailable

Optimized for M4 Mac Mini with 24GB RAM:
- Qwen3 4B Q4 quantized: ~3GB VRAM
- Loads into unified memory (Metal GPU)
- First inference: ~2s, subsequent: 200-500ms
- Max context: 4096 tokens

Requirements:
    pip install mlx mlx-lm
"""

import asyncio
import logging
import platform
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# MLX imports are conditional — only available on macOS Apple Silicon
_mlx_available = False
_mlx = None
_mlx_lm = None

if platform.system() == "Darwin" and platform.machine() == "arm64":
    try:
        import mlx.core  # noqa: F401
        import mlx_lm

        _mlx_available = True
        _mlx = mlx.core
        _mlx_lm = mlx_lm
        logger.info("MLX framework loaded successfully")
    except ImportError:
        logger.info("MLX not installed — pip install mlx mlx-lm")

# Default model for context filtering and simple tasks
DEFAULT_MODEL = "mlx-community/Qwen2.5-3B-Instruct-4bit"
# Larger model for more complex local tasks (still fits in 24GB)
LARGE_MODEL = "mlx-community/Qwen2.5-7B-Instruct-4bit"

# Memory budget for M4 Mac Mini 24GB
MAX_MODEL_MEMORY_MB = 4000  # Reserve ~4GB for model, rest for system + containers


class MLXInferenceEngine:
    """Local inference engine using MLX on Apple Silicon.

    Manages model loading, inference, and memory. Designed to coexist
    with containers and the rest of the Jarvis stack within 24GB.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        max_tokens: int = 512,
        memory_limit_mb: int = MAX_MODEL_MEMORY_MB,
    ):
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.memory_limit_mb = memory_limit_mb
        self._model = None
        self._tokenizer = None
        self._loaded = False
        self._load_time_ms: float = 0
        self._inference_count: int = 0
        self._total_inference_ms: float = 0

    @property
    def available(self) -> bool:
        """Check if MLX inference is available on this system."""
        return _mlx_available

    @property
    def loaded(self) -> bool:
        return self._loaded

    async def load_model(self) -> bool:
        """Load the model into memory (Apple Silicon unified memory).

        Returns True if successful, False if MLX unavailable or load fails.
        """
        if not _mlx_available:
            logger.warning("MLX not available — requires macOS Apple Silicon")
            return False

        if self._loaded:
            return True

        try:
            start = time.monotonic()
            logger.info(f"Loading MLX model: {self.model_name}")

            # Run model loading in a thread to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            self._model, self._tokenizer = await loop.run_in_executor(
                None, _mlx_lm.load, self.model_name
            )

            self._load_time_ms = (time.monotonic() - start) * 1000
            self._loaded = True
            logger.info(
                f"Model loaded in {self._load_time_ms:.0f}ms: {self.model_name}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            self._loaded = False
            return False

    async def unload_model(self) -> None:
        """Unload the model to free memory (e.g., for hibernation)."""
        if self._model is not None:
            del self._model
            del self._tokenizer
            self._model = None
            self._tokenizer = None
            self._loaded = False
            # Force garbage collection to free Metal memory
            import gc
            gc.collect()
            logger.info("Model unloaded from memory")

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int | None = None,
        temperature: float = 0.1,
    ) -> str:
        """Generate text using the local model.

        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
            max_tokens: Override default max tokens
            temperature: Sampling temperature (0.0 = deterministic)

        Returns:
            Generated text response

        Raises:
            RuntimeError: If model not loaded or MLX unavailable
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded — call load_model() first")

        # Build chat messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Apply chat template
        formatted = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        start = time.monotonic()

        # Run inference in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: _mlx_lm.generate(
                self._model,
                self._tokenizer,
                prompt=formatted,
                max_tokens=max_tokens or self.max_tokens,
                temp=temperature,
            ),
        )

        elapsed_ms = (time.monotonic() - start) * 1000
        self._inference_count += 1
        self._total_inference_ms += elapsed_ms
        logger.debug(f"Inference completed in {elapsed_ms:.0f}ms ({len(response)} chars)")

        return response

    async def classify_task(self, task_description: str) -> dict[str, Any]:
        """Classify a task into complexity categories.

        Returns:
            dict with 'complexity' (simple/moderate/complex),
            'category' (classification/editing/generation/analysis),
            'confidence' (0.0-1.0)
        """
        system = (
            "You are a task classifier. Respond with ONLY a JSON object. "
            "Classify the task into: "
            "complexity: simple|moderate|complex, "
            "category: classification|editing|generation|analysis|testing, "
            "confidence: 0.0-1.0"
        )
        prompt = f"Classify this development task:\n{task_description[:500]}"

        try:
            response = await self.generate(prompt, system_prompt=system, max_tokens=100)
            # Parse JSON from response
            import json
            # Find JSON in response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except Exception as e:
            logger.warning(f"Task classification failed: {e}")

        # Fallback
        return {"complexity": "moderate", "category": "analysis", "confidence": 0.3}

    async def filter_context_files(
        self,
        task_description: str,
        file_list: list[str],
        max_files: int = 5,
    ) -> list[str]:
        """Use the model to select relevant files for a task.

        Args:
            task_description: What needs to be done
            file_list: Available files in the project
            max_files: Maximum files to return

        Returns:
            Filtered list of relevant file paths
        """
        if len(file_list) <= max_files:
            return file_list

        # Truncate file list for 4K context budget
        files_text = "\n".join(f"- {f}" for f in file_list[:100])

        system = (
            "You are a code assistant. Given a task and a list of files, "
            "select the most relevant files. Respond with ONLY the file paths, "
            "one per line, no bullets or explanation."
        )
        prompt = (
            f"Task: {task_description[:300]}\n\n"
            f"Files:\n{files_text}\n\n"
            f"Select the {max_files} most relevant files:"
        )

        try:
            response = await self.generate(prompt, system_prompt=system, max_tokens=200)
            # Parse file paths from response
            selected = []
            for line in response.strip().splitlines():
                line = line.strip().lstrip("- ")
                if line in file_list:
                    selected.append(line)
                    if len(selected) >= max_files:
                        break

            if selected:
                return selected
        except Exception as e:
            logger.warning(f"Context filtering failed: {e}")

        # Fallback: return first N files
        return file_list[:max_files]

    async def summarize_error(self, error_output: str) -> str:
        """Summarize a long error output into a concise description.

        Useful for normalizing errors before hashing for the learning system.
        """
        system = (
            "Summarize this error in one sentence. "
            "Focus on the root cause, not the stack trace."
        )
        prompt = f"Error output:\n{error_output[:2000]}"

        try:
            return await self.generate(prompt, system_prompt=system, max_tokens=100)
        except Exception:
            # Fallback: return first line
            return error_output.split("\n")[0][:200]

    def get_stats(self) -> dict[str, Any]:
        """Get inference engine statistics."""
        avg_ms = (
            self._total_inference_ms / self._inference_count
            if self._inference_count > 0
            else 0
        )
        return {
            "available": self.available,
            "loaded": self._loaded,
            "model": self.model_name,
            "load_time_ms": self._load_time_ms,
            "inference_count": self._inference_count,
            "avg_inference_ms": avg_ms,
            "total_inference_ms": self._total_inference_ms,
            "memory_limit_mb": self.memory_limit_mb,
        }


# Singleton instance
_engine_instance: MLXInferenceEngine | None = None


def get_mlx_engine(model_name: str = DEFAULT_MODEL) -> MLXInferenceEngine:
    """Get the global MLX inference engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = MLXInferenceEngine(model_name=model_name)
    return _engine_instance


def is_mlx_available() -> bool:
    """Quick check if MLX is available on this system."""
    return _mlx_available
