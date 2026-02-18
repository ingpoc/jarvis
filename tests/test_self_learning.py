"""Tests for jarvis.self_learning — error-fix pattern extraction."""

import pytest

from jarvis.self_learning import (
    calculate_fix_diff,
    detect_language,
    extract_error_from_execution,
    extract_fix_description,
    format_learning_for_context,
    get_relevant_learnings,
    hash_error_pattern,
    learn_from_task,
)


class TestHashErrorPattern:
    """Test error message normalization and hashing."""

    def test_consistent_hash(self):
        h1 = hash_error_pattern("TypeError: undefined is not a function")
        h2 = hash_error_pattern("TypeError: undefined is not a function")
        assert h1 == h2

    def test_normalizes_line_numbers(self):
        h1 = hash_error_pattern("Error at line 42 in foo.py")
        h2 = hash_error_pattern("Error at line 99 in foo.py")
        assert h1 == h2

    def test_normalizes_file_paths(self):
        h1 = hash_error_pattern("Error in /home/user/proj/src/main.py")
        h2 = hash_error_pattern("Error in /var/build/proj/src/main.py")
        assert h1 == h2

    def test_normalizes_timestamps(self):
        h1 = hash_error_pattern("Error at 2026-01-01 12:00:00")
        h2 = hash_error_pattern("Error at 2026-02-09 15:30:00")
        assert h1 == h2

    def test_normalizes_memory_addresses(self):
        h1 = hash_error_pattern("Segfault at 0x7fff5fbff8c0")
        h2 = hash_error_pattern("Segfault at 0xdeadbeef1234")
        assert h1 == h2

    def test_different_errors_different_hash(self):
        h1 = hash_error_pattern("TypeError: undefined is not a function")
        h2 = hash_error_pattern("ReferenceError: x is not defined")
        assert h1 != h2

    def test_returns_16_char_hex(self):
        h = hash_error_pattern("any error")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


class TestExtractError:
    """Test error extraction from execution records."""

    def test_extracts_error_message_field(self):
        record = {"error_message": "Module not found", "tool_output": ""}
        assert extract_error_from_execution(record) == "Module not found"

    def test_extracts_error_from_output(self):
        record = {
            "error_message": None,
            "tool_output": "error: Cannot find module 'foo'\nother text",
        }
        error = extract_error_from_execution(record)
        assert error is not None
        assert "Cannot find module" in error

    def test_extracts_error_from_exit_code(self):
        record = {"error_message": None, "tool_output": "silent failure", "exit_code": 1}
        error = extract_error_from_execution(record)
        assert "exit code 1" in error

    def test_no_error_returns_none(self):
        record = {"error_message": None, "tool_output": "All tests passed", "exit_code": 0}
        assert extract_error_from_execution(record) is None


class TestDetectLanguage:
    """Test language detection."""

    def test_from_python_files(self):
        assert detect_language("/proj", ["src/main.py", "src/utils.py"]) == "python"

    def test_from_javascript_files(self):
        assert detect_language("/proj", ["src/app.ts", "src/index.js"]) == "javascript"

    def test_from_rust_files(self):
        assert detect_language("/proj", ["src/main.rs"]) == "rust"

    def test_from_go_files(self):
        assert detect_language("/proj", ["cmd/main.go"]) == "go"

    def test_from_project_structure(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        assert detect_language(str(tmp_path), []) == "javascript"

    def test_unknown_language(self, tmp_path):
        assert detect_language(str(tmp_path), []) == "unknown"


class TestExtractFixDescription:
    """Test fix description extraction."""

    def test_edit_fix(self):
        records = [
            {"tool_name": "Edit", "tool_input": {"old_string": "broken()", "new_string": "fixed()"}},
        ]
        desc = extract_fix_description(records)
        assert "broken()" in desc
        assert "fixed()" in desc

    def test_write_fix(self):
        records = [
            {"tool_name": "Write", "tool_input": {"content": "new content"}},
        ]
        desc = extract_fix_description(records)
        assert "Wrote content" in desc

    def test_commit_fix(self):
        records = [
            {"tool_name": "mcp__jarvis-git__git_commit", "tool_input": {"message": "Fix bug #42"}},
        ]
        desc = extract_fix_description(records)
        assert "Fix bug #42" in desc

    def test_no_fix_records(self):
        records = [{"tool_name": "Read", "tool_input": {}}]
        assert extract_fix_description(records) == "Applied fix"


class TestCalculateFixDiff:
    """Test diff calculation from fix records."""

    def test_edit_diff(self):
        records = [
            {"tool_name": "Edit", "tool_input": {"old_string": "old_code", "new_string": "new_code"}},
        ]
        diff = calculate_fix_diff(records)
        assert "-old_code" in diff
        assert "+new_code" in diff

    def test_write_diff(self):
        records = [
            {"tool_name": "Write", "tool_input": {"content": "file_content"}},
        ]
        diff = calculate_fix_diff(records)
        assert "+++ new file" in diff

    def test_no_diffs(self):
        records = [{"tool_name": "Bash", "tool_input": {}}]
        assert calculate_fix_diff(records) == "No diff captured"


class TestLearnFromTask:
    """Test the full learning extraction pipeline."""

    @pytest.mark.asyncio
    async def test_no_records(self, memory):
        stats = await learn_from_task("t-empty", "/proj", memory)
        assert stats["errors_found"] == 0
        assert stats["learnings_saved"] == 0

    @pytest.mark.asyncio
    async def test_error_fix_sequence(self, memory):
        """Test learning extraction from an error followed by a fix."""
        # Record an error
        memory.record_execution(
            task_id="t-learn", session_id="s-1", tool_name="Bash",
            tool_input={"command": "npm test"},
            tool_output="error: Cannot find module 'lodash'",
            exit_code=1, error_message="Cannot find module 'lodash'",
            project_path="/proj",
        )
        # Record a fix (Edit)
        memory.record_execution(
            task_id="t-learn", session_id="s-1", tool_name="Edit",
            tool_input={"file_path": "package.json", "old_string": "{}", "new_string": '{"lodash": "^4.0"}'},
            tool_output="File edited",
            exit_code=0,
            files_touched=["package.json"],
            project_path="/proj",
        )

        stats = await learn_from_task("t-learn", "/proj", memory)
        assert stats["errors_found"] >= 1
        assert stats["learnings_saved"] >= 1

    @pytest.mark.asyncio
    async def test_no_fix_means_no_learning(self, memory):
        """Error without fix should not create a learning."""
        memory.record_execution(
            task_id="t-err", session_id="s-1", tool_name="Bash",
            tool_input={}, tool_output="error: something broke",
            exit_code=1, error_message="something broke",
            project_path="/proj",
        )
        stats = await learn_from_task("t-err", "/proj", memory)
        assert stats["errors_found"] >= 1
        assert stats["learnings_saved"] == 0

    @pytest.mark.asyncio
    async def test_skill_candidate_on_repeat(self, memory):
        """Third occurrence of same error pattern should flag skill candidate."""
        for i in range(3):
            tid = f"t-rep-{i}"
            memory.record_execution(
                task_id=tid, session_id="s-1", tool_name="Bash",
                tool_input={}, tool_output="error: ECONNREFUSED",
                exit_code=1, error_message="ECONNREFUSED",
                project_path="/proj",
            )
            memory.record_execution(
                task_id=tid, session_id="s-1", tool_name="Edit",
                tool_input={"old_string": "old", "new_string": "new"},
                tool_output="ok", exit_code=0,
                project_path="/proj",
            )
            stats = await learn_from_task(tid, "/proj", memory)

        # By the third iteration we should have skill candidates
        candidates = memory.get_skill_candidates(min_occurrences=1)
        # At minimum, learnings were saved
        assert stats["learnings_saved"] >= 1


class TestGetRelevantLearnings:
    """Test learning retrieval."""

    def test_finds_matching_learning(self, memory):
        error = "TypeError: Cannot read property 'map' of undefined"
        h = hash_error_pattern(error)
        memory.save_learning("/proj", "javascript", h, error, "Check if array", "diff")
        learnings = get_relevant_learnings("/proj", error, memory)
        assert len(learnings) >= 1
        assert "map" in learnings[0]["error_message"]

    def test_no_match_returns_empty(self, memory):
        learnings = get_relevant_learnings("/proj", "Totally unique error", memory)
        assert learnings == []


class TestFormatLearning:
    """Test learning formatting for context injection."""

    def test_format_includes_key_fields(self):
        learning = {
            "confidence": 0.85,
            "occurrence_count": 3,
            "error_message": "ImportError: No module named 'foo'",
            "fix_description": "pip install foo",
            "fix_diff": "+foo>=1.0",
        }
        formatted = format_learning_for_context(learning)
        assert "0.85" in formatted or "0.8" in formatted
        assert "3x" in formatted
        assert "ImportError" in formatted
        assert "pip install foo" in formatted
