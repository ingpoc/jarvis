"""Tests for jarvis.idle_mode — background task processing."""

import asyncio
import time

import pytest

from jarvis.idle_mode import BackgroundTask, IdleModeProcessor, IdleState, TaskPriority


class TestIdleState:
    """Test idle state machine transitions."""

    def test_initial_state_is_active(self, memory):
        processor = IdleModeProcessor(memory, "/proj")
        assert processor.state == IdleState.ACTIVE

    def test_trigger_idle(self, memory):
        processor = IdleModeProcessor(memory, "/proj")
        processor.trigger_idle()
        assert processor.state == IdleState.IDLE

    def test_trigger_hibernate(self, memory):
        processor = IdleModeProcessor(memory, "/proj")
        processor.trigger_hibernate()
        assert processor.state == IdleState.HIBERNATED

    def test_activity_resumes_active(self, memory):
        processor = IdleModeProcessor(memory, "/proj")
        processor.trigger_idle()
        assert processor.state == IdleState.IDLE
        processor.record_activity()
        assert processor.state == IdleState.ACTIVE

    def test_activity_from_hibernated(self, memory):
        processor = IdleModeProcessor(memory, "/proj")
        processor.trigger_hibernate()
        processor.record_activity()
        assert processor.state == IdleState.ACTIVE

    def test_state_callback_notified(self, memory):
        processor = IdleModeProcessor(memory, "/proj")
        transitions = []
        processor.add_state_callback(lambda old, new: transitions.append((old, new)))
        processor.trigger_idle()
        assert len(transitions) == 1
        assert transitions[0] == ("active", "idle")


class TestBackgroundTask:
    """Test background task scheduling."""

    def test_should_run_initially(self):
        task = BackgroundTask(name="test", func=lambda: None, interval_seconds=60)
        assert task.should_run is True  # last_run is 0

    def test_should_not_run_after_execution(self):
        task = BackgroundTask(name="test", func=lambda: None, interval_seconds=60)
        task.last_run = time.time()
        assert task.should_run is False

    def test_should_run_after_interval(self):
        task = BackgroundTask(name="test", func=lambda: None, interval_seconds=1)
        task.last_run = time.time() - 2
        assert task.should_run is True

    def test_priority_ordering(self):
        high = BackgroundTask("h", lambda: None, priority=TaskPriority.HIGH)
        med = BackgroundTask("m", lambda: None, priority=TaskPriority.MEDIUM)
        low = BackgroundTask("l", lambda: None, priority=TaskPriority.LOW)
        sorted_tasks = sorted([low, high, med], key=lambda t: t.priority.value)
        assert sorted_tasks[0].name == "h"
        assert sorted_tasks[1].name == "m"
        assert sorted_tasks[2].name == "l"


class TestIdleModeProcessor:
    """Test idle mode processing lifecycle."""

    def test_default_tasks_registered(self, memory):
        processor = IdleModeProcessor(memory, "/proj")
        task_names = [t.name for t in processor._tasks]
        assert "learning_revalidation" in task_names
        assert "context_rebuild" in task_names
        assert "skill_generation" in task_names
        assert "token_optimization_report" in task_names

    def test_get_stats(self, memory):
        processor = IdleModeProcessor(memory, "/proj")
        stats = processor.get_stats()
        assert stats["state"] == "active"
        assert stats["running"] is False
        assert len(stats["tasks"]) >= 4

    @pytest.mark.asyncio
    async def test_start_stop(self, memory):
        processor = IdleModeProcessor(memory, "/proj")
        await processor.start()
        assert processor._running is True
        await processor.stop()
        assert processor._running is False

    @pytest.mark.asyncio
    async def test_revalidate_learnings(self, memory):
        # Add a learning that needs revalidation
        lid = memory.save_learning("/proj", "python", "h1", "Error", "Fix", "diff", confidence=0.8)
        memory.mark_learning_for_revalidation(lid)

        processor = IdleModeProcessor(memory, "/proj")
        result = await processor._revalidate_learnings()
        assert result["total_checked"] >= 1

    @pytest.mark.asyncio
    async def test_generate_token_report_no_data(self, memory):
        processor = IdleModeProcessor(memory, "/proj")
        result = await processor._generate_token_report()
        assert result["status"] == "no_data"

    @pytest.mark.asyncio
    async def test_generate_token_report_with_data(self, memory):
        memory.record_token_usage("s-1", "t-1", "claude", 100, 50, 0.01, "/proj")
        memory.record_token_usage("s-1", "t-2", "claude", 200, 100, 0.02, "/proj")

        processor = IdleModeProcessor(memory, "/proj")
        result = await processor._generate_token_report()
        assert result["total_records"] == 2
        assert result["total_cost_usd"] == pytest.approx(0.03)
