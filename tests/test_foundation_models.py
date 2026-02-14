"""Tests for jarvis.foundation_models — Foundation Models Python client.

Works on all platforms. Real integration tests only run when the
Foundation Models bridge is actually running.
"""

import pytest

from jarvis.foundation_models import FoundationModelsClient, get_foundation_client


class TestFoundationModelsClient:
    """Test client interface."""

    def test_create_client(self):
        client = FoundationModelsClient()
        assert client.base_url == "http://127.0.0.1:9848"

    def test_custom_url(self):
        client = FoundationModelsClient(base_url="http://localhost:1234")
        assert client.base_url == "http://localhost:1234"

    def test_stats_initial(self):
        client = FoundationModelsClient()
        stats = client.get_stats()
        assert stats["request_count"] == 0
        assert stats["available"] is None  # Not yet checked

    @pytest.mark.asyncio
    async def test_classify_fallback_when_unavailable(self):
        """When bridge is not running, classify returns fallback."""
        client = FoundationModelsClient(base_url="http://127.0.0.1:19999")
        result = await client.classify("test text", categories=["a", "b"])
        assert result["source"] == "fallback"
        assert result["label"] == "a"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_classify_task_complexity_fallback(self):
        client = FoundationModelsClient(base_url="http://127.0.0.1:19999")
        result = await client.classify_task_complexity("build a REST API")
        assert result["label"] in ("simple", "moderate", "complex")

    @pytest.mark.asyncio
    async def test_classify_intent_fallback(self):
        client = FoundationModelsClient(base_url="http://127.0.0.1:19999")
        result = await client.classify_intent("run my tests")
        assert result["label"] in ("run_task", "ask_question", "view_status",
                                    "approve", "cancel", "configure")

    @pytest.mark.asyncio
    async def test_summarize_fallback(self):
        client = FoundationModelsClient(base_url="http://127.0.0.1:19999")
        result = await client.summarize("This is a long text " * 20, max_length=50)
        assert len(result) <= 50

    @pytest.mark.asyncio
    async def test_is_available_caches(self):
        client = FoundationModelsClient(base_url="http://127.0.0.1:19999")
        result1 = await client.is_available()
        assert result1 is False

        # Second call should use cache
        result2 = await client.is_available()
        assert result2 is False


class TestSingleton:
    """Test singleton pattern."""

    def test_get_foundation_client_same_instance(self):
        c1 = get_foundation_client()
        c2 = get_foundation_client()
        assert c1 is c2
