"""Tests for jarvis.model_router — 3-tier intelligence routing."""

import pytest

from jarvis.model_router import ModelRouter, ModelTier, RoutingDecision, get_model_router


class TestModelRouter:
    """Test model routing decisions."""

    @pytest.fixture
    def router(self):
        return ModelRouter()

    @pytest.mark.asyncio
    async def test_default_routes_to_glm(self, router):
        decision = await router.route_task("Implement a REST API for user management")
        assert decision.tier == ModelTier.GLM_CLOUD
        assert decision.model == "claude-sonnet-4.5"

    @pytest.mark.asyncio
    async def test_classification_with_foundation(self, router):
        router.foundation_available = True
        decision = await router.route_task("classify this error as build or runtime")
        assert decision.tier == ModelTier.FOUNDATION
        assert decision.estimated_cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_classification_without_foundation(self, router):
        """Without Foundation Models, classification falls through to GLM."""
        decision = await router.route_task("classify this error type")
        assert decision.tier == ModelTier.GLM_CLOUD

    @pytest.mark.asyncio
    async def test_simple_task_with_qwen3(self, router):
        router.qwen3_available = True
        decision = await router.route_task(
            "fix typo in readme",
            context_files=["README.md"],
        )
        assert decision.tier == ModelTier.QWEN3_LOCAL
        assert decision.estimated_cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_simple_task_without_qwen3(self, router):
        decision = await router.route_task(
            "fix typo in readme",
            context_files=["README.md"],
        )
        assert decision.tier == ModelTier.GLM_CLOUD

    @pytest.mark.asyncio
    async def test_complex_task_bypasses_local(self, router):
        router.qwen3_available = True
        decision = await router.route_task(
            "refactor the entire authentication system",
            context_files=["a.py", "b.py", "c.py", "d.py", "e.py"],
        )
        assert decision.tier == ModelTier.GLM_CLOUD

    @pytest.mark.asyncio
    async def test_offline_with_qwen3(self, router):
        router.qwen3_available = True
        decision = await router.route_task(
            "fix a bug in main.py",
            offline_mode=True,
        )
        assert decision.tier == ModelTier.QWEN3_LOCAL

    @pytest.mark.asyncio
    async def test_offline_without_models(self, router):
        decision = await router.route_task(
            "fix a bug",
            offline_mode=True,
        )
        assert decision.model == "unavailable"

    def test_routing_stats(self, router):
        stats = router.get_stats()
        assert stats["total_routes"] == 0
        assert stats["qwen3_available"] is False
        assert stats["foundation_available"] is False

    @pytest.mark.asyncio
    async def test_stats_accumulate(self, router):
        await router.route_task("build feature")
        await router.route_task("create service")
        stats = router.get_stats()
        assert stats["total_routes"] == 2
        assert stats["glm_pct"] == 100.0

    def test_enable_local_models(self, router):
        router.enable_local_models(qwen3=True, foundation=True)
        assert router.qwen3_available is True
        assert router.foundation_available is True


class TestHeuristicFilter:
    """Test heuristic context filtering."""

    def test_filter_by_filename_mention(self):
        router = ModelRouter()
        files = ["src/main.py", "src/utils.py", "src/config.py"]
        filtered = router._heuristic_filter_context("fix the bug in main.py", files)
        assert "src/main.py" in filtered

    def test_filter_returns_max_3(self):
        router = ModelRouter()
        files = [f"file{i}.py" for i in range(10)]
        filtered = router._heuristic_filter_context("generic task", files)
        assert len(filtered) <= 3

    def test_filter_no_mention_returns_first_3(self):
        router = ModelRouter()
        files = ["a.py", "b.py", "c.py", "d.py"]
        filtered = router._heuristic_filter_context("do something", files)
        assert len(filtered) == 3


class TestClassificationDetection:
    """Test task classification detection."""

    def test_classification_keywords(self):
        router = ModelRouter()
        assert router._is_classification_task("classify this error") is True
        assert router._is_classification_task("is this a bug or feature?") is True
        assert router._is_classification_task("check if this is valid") is True
        assert router._is_classification_task("implement a REST API") is False

    def test_simple_task_detection(self):
        router = ModelRouter()
        assert router._is_simple_task("fix typo in file", ["a.py"]) is True
        assert router._is_simple_task("refactor the auth system", ["a.py", "b.py", "c.py", "d.py"]) is False
        assert router._is_simple_task("rename variable", []) is True


class TestSingleton:
    """Test singleton pattern."""

    def test_get_model_router_returns_same_instance(self):
        r1 = get_model_router()
        r2 = get_model_router()
        assert r1 is r2
