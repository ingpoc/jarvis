"""Tests for jarvis.mlx_inference — MLX local model inference.

Works on all platforms: MLX features degrade gracefully on non-macOS.
Full inference tests only run on Apple Silicon with MLX installed.
"""

import platform

import pytest

from jarvis.mlx_inference import (
    DEFAULT_MODEL,
    MLXInferenceEngine,
    get_mlx_engine,
    is_mlx_available,
)


class TestMLXAvailability:
    """Test MLX availability detection."""

    def test_is_mlx_available_returns_bool(self):
        result = is_mlx_available()
        assert isinstance(result, bool)

    @pytest.mark.skipif(
        platform.system() != "Darwin" or platform.machine() != "arm64",
        reason="MLX requires macOS Apple Silicon",
    )
    def test_mlx_available_on_apple_silicon(self):
        # May still be False if mlx package not installed,
        # but should not raise
        result = is_mlx_available()
        assert isinstance(result, bool)


class TestMLXInferenceEngine:
    """Test the inference engine interface."""

    def test_create_engine(self):
        engine = MLXInferenceEngine()
        assert engine.model_name == DEFAULT_MODEL
        assert engine.max_tokens == 512
        assert engine.loaded is False

    def test_available_property(self):
        engine = MLXInferenceEngine()
        assert isinstance(engine.available, bool)

    def test_stats_before_load(self):
        engine = MLXInferenceEngine()
        stats = engine.get_stats()
        assert stats["loaded"] is False
        assert stats["inference_count"] == 0
        assert stats["model"] == DEFAULT_MODEL

    @pytest.mark.asyncio
    async def test_generate_without_load_raises(self):
        engine = MLXInferenceEngine()
        # Force loaded=False
        engine._loaded = False
        with pytest.raises(RuntimeError, match="not loaded"):
            await engine.generate("test prompt")

    @pytest.mark.asyncio
    async def test_load_fails_gracefully_without_mlx(self):
        engine = MLXInferenceEngine()
        if not engine.available:
            result = await engine.load_model()
            assert result is False
            assert engine.loaded is False

    @pytest.mark.asyncio
    async def test_unload_when_not_loaded(self):
        engine = MLXInferenceEngine()
        # Should not raise
        await engine.unload_model()
        assert engine.loaded is False

    @pytest.mark.asyncio
    async def test_classify_task_fallback(self):
        engine = MLXInferenceEngine()
        engine._loaded = False
        # Can't test real classification without MLX, but we test the interface
        if not engine.available:
            with pytest.raises(RuntimeError):
                await engine.classify_task("fix a bug")


class TestMLXSingleton:
    """Test singleton pattern."""

    def test_get_mlx_engine_returns_same_instance(self):
        e1 = get_mlx_engine()
        e2 = get_mlx_engine()
        assert e1 is e2


class TestMLXOnAppleSilicon:
    """Integration tests that only run on Apple Silicon with MLX installed."""

    @pytest.mark.skipif(not is_mlx_available(), reason="MLX not available")
    @pytest.mark.asyncio
    async def test_load_and_generate(self):
        engine = MLXInferenceEngine()
        loaded = await engine.load_model()
        assert loaded is True
        assert engine.loaded is True

        response = await engine.generate("What is 2+2?", max_tokens=50)
        assert len(response) > 0

        stats = engine.get_stats()
        assert stats["inference_count"] == 1
        assert stats["load_time_ms"] > 0

        await engine.unload_model()
        assert engine.loaded is False

    @pytest.mark.skipif(not is_mlx_available(), reason="MLX not available")
    @pytest.mark.asyncio
    async def test_classify_task(self):
        engine = MLXInferenceEngine()
        await engine.load_model()

        result = await engine.classify_task("fix a typo in README.md")
        assert "complexity" in result
        assert result["complexity"] in ("simple", "moderate", "complex")

        await engine.unload_model()

    @pytest.mark.skipif(not is_mlx_available(), reason="MLX not available")
    @pytest.mark.asyncio
    async def test_filter_context_files(self):
        engine = MLXInferenceEngine()
        await engine.load_model()

        files = [
            "src/main.py",
            "src/utils.py",
            "src/config.py",
            "tests/test_main.py",
            "README.md",
            "Dockerfile",
            "package.json",
        ]
        filtered = await engine.filter_context_files(
            "fix the bug in main.py", files, max_files=3
        )
        assert len(filtered) <= 3
        # main.py should likely be included
        assert any("main" in f for f in filtered)

        await engine.unload_model()

    @pytest.mark.skipif(not is_mlx_available(), reason="MLX not available")
    @pytest.mark.asyncio
    async def test_summarize_error(self):
        engine = MLXInferenceEngine()
        await engine.load_model()

        error = """
        Traceback (most recent call last):
          File "main.py", line 42, in run
            result = process(data)
          File "main.py", line 18, in process
            return data['key']
        KeyError: 'key'
        """
        summary = await engine.summarize_error(error)
        assert len(summary) > 0
        assert len(summary) < len(error)

        await engine.unload_model()
