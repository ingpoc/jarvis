"""Tests for jarvis.memory — MemoryStore persistence layer."""

import json
import time

import pytest

from jarvis.memory import MemoryStore, Task


class TestTaskManagement:
    """Test task CRUD operations."""

    def test_create_task(self, memory):
        task = memory.create_task("t-001", "Build feature X", "/tmp/proj")
        assert task.id == "t-001"
        assert task.description == "Build feature X"
        assert task.status == "pending"
        assert task.project_path == "/tmp/proj"

    def test_get_task(self, memory):
        memory.create_task("t-002", "Fix bug", "/tmp/proj")
        task = memory.get_task("t-002")
        assert task is not None
        assert task.description == "Fix bug"

    def test_get_nonexistent_task(self, memory):
        assert memory.get_task("nonexistent") is None

    def test_update_task(self, memory):
        memory.create_task("t-003", "Deploy", "/tmp/proj")
        memory.update_task("t-003", status="completed", cost_usd=1.5)
        task = memory.get_task("t-003")
        assert task.status == "completed"
        assert task.cost_usd == 1.5

    def test_update_task_rejects_invalid_columns(self, memory):
        memory.create_task("t-004", "Test", "/tmp/proj")
        with pytest.raises(ValueError, match="Invalid task columns"):
            memory.update_task("t-004", evil_column="DROP TABLE")

    def test_list_tasks_by_project(self, memory):
        memory.create_task("t-010", "A", "/proj/a")
        memory.create_task("t-011", "B", "/proj/b")
        memory.create_task("t-012", "C", "/proj/a")
        tasks = memory.list_tasks(project_path="/proj/a")
        assert len(tasks) == 2
        assert all(t.project_path == "/proj/a" for t in tasks)

    def test_list_tasks_by_status(self, memory):
        memory.create_task("t-020", "X", "/proj")
        memory.create_task("t-021", "Y", "/proj")
        memory.update_task("t-020", status="completed")
        tasks = memory.list_tasks(status="completed")
        assert len(tasks) == 1
        assert tasks[0].id == "t-020"


class TestSessionSummaries:
    """Test session summary persistence."""

    def test_save_and_get_summary(self, memory):
        memory.save_session_summary(
            session_id="sess-1",
            project_path="/tmp/proj",
            summary="Completed 3 tasks",
            tasks_completed=["t-1", "t-2", "t-3"],
            tasks_remaining=["t-4"],
        )
        summary = memory.get_last_summary("/tmp/proj")
        assert summary is not None
        assert summary["summary"] == "Completed 3 tasks"
        assert summary["tasks_completed"] == ["t-1", "t-2", "t-3"]
        assert summary["tasks_remaining"] == ["t-4"]

    def test_get_last_summary_returns_most_recent(self, memory):
        memory.save_session_summary("s1", "/proj", "First", ["a"], [])
        memory.save_session_summary("s2", "/proj", "Second", ["b"], [])
        summary = memory.get_last_summary("/proj")
        assert summary["summary"] == "Second"

    def test_get_summary_nonexistent_project(self, memory):
        assert memory.get_last_summary("/nonexistent") is None


class TestLearnedPatterns:
    """Test learned pattern storage."""

    def test_learn_pattern(self, memory):
        memory.learn_pattern("/proj", "error_fix", "TypeError: always use str()")
        patterns = memory.get_patterns("/proj")
        assert len(patterns) == 1
        assert patterns[0]["pattern"] == "TypeError: always use str()"
        assert patterns[0]["confidence"] == 0.5

    def test_reinforce_pattern(self, memory):
        memory.learn_pattern("/proj", "convention", "Use snake_case")
        memory.learn_pattern("/proj", "convention", "Use snake_case")
        patterns = memory.get_patterns("/proj", pattern_type="convention")
        assert len(patterns) == 1
        assert patterns[0]["confidence"] == pytest.approx(0.6, abs=0.01)

    def test_filter_by_type(self, memory):
        memory.learn_pattern("/proj", "error_fix", "Fix A")
        memory.learn_pattern("/proj", "convention", "Conv B")
        patterns = memory.get_patterns("/proj", pattern_type="error_fix")
        assert len(patterns) == 1
        assert patterns[0]["type"] == "error_fix"


class TestExecutionRecords:
    """Test execution record storage and retrieval."""

    def test_record_execution(self, memory):
        record_id = memory.record_execution(
            task_id="t-100",
            session_id="s-1",
            tool_name="Bash",
            tool_input={"command": "npm test"},
            tool_output="All tests passed",
            exit_code=0,
            project_path="/proj",
        )
        assert record_id > 0

    def test_get_execution_records(self, memory):
        memory.record_execution("t-200", "s-1", "Edit", {"file": "a.py"}, "ok", 0, project_path="/proj")
        memory.record_execution("t-200", "s-1", "Bash", {"cmd": "test"}, "pass", 0, project_path="/proj")
        records = memory.get_execution_records(task_id="t-200")
        assert len(records) == 2
        assert records[0]["tool_name"] == "Edit"  # ASC order
        assert records[1]["tool_name"] == "Bash"

    def test_get_records_desc_order(self, memory):
        memory.record_execution("t-300", "s-1", "A", {}, "", 0, project_path="/proj")
        memory.record_execution("t-300", "s-1", "B", {}, "", 0, project_path="/proj")
        records = memory.get_execution_records(task_id="t-300", order="DESC")
        assert records[0]["tool_name"] == "B"

    def test_record_with_error(self, memory):
        memory.record_execution(
            task_id="t-400", session_id="s-1", tool_name="Bash",
            tool_input={"command": "npm build"}, tool_output="BUILD FAILED",
            exit_code=1, error_message="Module not found",
            project_path="/proj",
        )
        records = memory.get_execution_records(task_id="t-400")
        assert records[0]["error_message"] == "Module not found"
        assert records[0]["exit_code"] == 1

    def test_record_with_files_touched(self, memory):
        memory.record_execution(
            task_id="t-500", session_id="s-1", tool_name="Edit",
            tool_input={}, tool_output="ok", exit_code=0,
            files_touched=["src/main.py", "src/utils.py"],
            project_path="/proj",
        )
        records = memory.get_execution_records(task_id="t-500")
        assert records[0]["files_touched"] == ["src/main.py", "src/utils.py"]


class TestLearnings:
    """Test learnings table operations."""

    def test_save_learning(self, memory):
        learning_id = memory.save_learning(
            project_path="/proj",
            language="python",
            error_pattern_hash="abc123",
            error_message="ImportError: no module named foo",
            fix_description="pip install foo",
            fix_diff="+foo>=1.0",
            confidence=0.7,
        )
        assert learning_id > 0

    def test_get_learnings(self, memory):
        memory.save_learning("/proj", "python", "h1", "Error A", "Fix A", "diff A")
        memory.save_learning("/proj", "python", "h2", "Error B", "Fix B", "diff B")
        learnings = memory.get_learnings(project_path="/proj")
        assert len(learnings) == 2

    def test_update_existing_learning(self, memory):
        memory.save_learning("/proj", "python", "h1", "Error", "Fix", "diff")
        memory.save_learning("/proj", "python", "h1", "Error", "Fix v2", "diff v2")
        learnings = memory.get_learnings(project_path="/proj")
        assert len(learnings) == 1
        assert learnings[0]["occurrence_count"] == 2

    def test_filter_by_confidence(self, memory):
        memory.save_learning("/proj", "python", "h1", "Err", "Fix", "d", confidence=0.9)
        memory.save_learning("/proj", "python", "h2", "Err2", "Fix2", "d2", confidence=0.3)
        high_conf = memory.get_learnings(project_path="/proj", min_confidence=0.7)
        assert len(high_conf) == 1
        assert high_conf[0]["error_pattern_hash"] == "h1"

    def test_mark_for_revalidation(self, memory):
        lid = memory.save_learning("/proj", "python", "h1", "E", "F", "d")
        memory.mark_learning_for_revalidation(lid)
        learnings = memory.get_learnings(project_path="/proj", min_confidence=0.0)
        assert learnings[0]["needs_revalidation"] == 1


class TestSkillCandidates:
    """Test skill candidate tracking."""

    def test_record_skill_candidate(self, memory):
        cid = memory.record_skill_candidate("ph1", "Fix TypeError", "t-1", "/proj")
        assert cid > 0

    def test_increment_occurrence(self, memory):
        memory.record_skill_candidate("ph1", "Fix TypeError", "t-1", "/proj")
        memory.record_skill_candidate("ph1", "Fix TypeError", "t-2", "/proj")
        memory.record_skill_candidate("ph1", "Fix TypeError", "t-3", "/proj")
        candidates = memory.get_skill_candidates(min_occurrences=3)
        assert len(candidates) == 1
        assert candidates[0]["occurrence_count"] == 3
        assert set(candidates[0]["example_tasks"]) == {"t-1", "t-2", "t-3"}

    def test_promoted_filter(self, memory):
        memory.record_skill_candidate("ph1", "A", "t-1", "/proj")
        memory.record_skill_candidate("ph1", "A", "t-2", "/proj")
        memory.record_skill_candidate("ph1", "A", "t-3", "/proj")
        candidates = memory.get_skill_candidates(min_occurrences=3)
        memory.mark_skill_promoted(candidates[0]["id"])
        unpromoted = memory.get_skill_candidates(min_occurrences=1, promoted=False)
        promoted = memory.get_skill_candidates(min_occurrences=1, promoted=True)
        assert len(unpromoted) == 0
        assert len(promoted) == 1


class TestTokenUsage:
    """Test token usage tracking."""

    def test_record_token_usage(self, memory):
        uid = memory.record_token_usage(
            session_id="s-1", task_id="t-1", model="claude-sonnet-4.5",
            prompt_tokens=1000, completion_tokens=500,
            cost_usd=0.015, project_path="/proj",
        )
        assert uid > 0

    def test_get_token_usage(self, memory):
        memory.record_token_usage("s-1", "t-1", "claude", 100, 50, 0.01, "/proj")
        memory.record_token_usage("s-1", "t-2", "claude", 200, 100, 0.02, "/proj")
        usage = memory.get_token_usage(session_id="s-1")
        assert len(usage) == 2
        assert usage[0]["total_tokens"] == 300  # DESC order, most recent first


class TestTimelineEvents:
    """Test timeline event recording."""

    def test_record_and_query_event(self, memory):
        eid = memory.record_event(
            event_type="task_start",
            summary="Started feature X",
            task_id="t-1",
        )
        assert eid > 0
        events = memory.get_timeline()
        assert len(events) == 1
        assert events[0]["summary"] == "Started feature X"

    def test_filter_by_event_type(self, memory):
        memory.record_event("task_start", "Start")
        memory.record_event("task_complete", "Done")
        memory.record_event("task_start", "Start 2")
        events = memory.get_timeline(event_type="task_start")
        assert len(events) == 2
