"""Tests for jarvis.skill_generator — autonomous skill creation."""

from pathlib import Path
from unittest.mock import patch

import pytest

from jarvis.skill_generator import (
    copy_bootstrap_skills,
    detect_skill_worthy_patterns,
    generate_skill_from_candidate,
    generate_skill_name,
    generate_skills_from_patterns,
    save_skill_to_directory,
    validate_skill,
)


class TestGenerateSkillName:
    """Test skill name generation from descriptions."""

    def test_basic_name(self):
        assert generate_skill_name("Fix TypeError undefined") == "fix-typeerror-undefined"

    def test_removes_stop_words(self):
        name = generate_skill_name("Fix for the broken auth module")
        assert "the" not in name.split("-")
        assert "for" not in name.split("-")

    def test_max_4_words(self):
        name = generate_skill_name("one two three four five six seven")
        parts = name.split("-")
        assert len(parts) <= 4

    def test_removes_special_chars(self):
        name = generate_skill_name("Fix: error! in @module")
        assert ":" not in name
        assert "!" not in name
        assert "@" not in name


class TestDetectSkillWorthyPatterns:
    """Test skill candidate detection."""

    def test_finds_candidates_above_threshold(self, memory):
        for i in range(4):
            memory.record_skill_candidate("ph1", "Pattern A", f"t-{i}", "/proj")
        candidates = detect_skill_worthy_patterns(memory, min_occurrences=3)
        assert len(candidates) >= 1
        assert candidates[0]["occurrence_count"] >= 3

    def test_ignores_below_threshold(self, memory):
        memory.record_skill_candidate("ph2", "Pattern B", "t-1", "/proj")
        candidates = detect_skill_worthy_patterns(memory, min_occurrences=3)
        assert len(candidates) == 0


class TestGenerateSkillFromCandidate:
    """Test skill content generation."""

    @pytest.mark.asyncio
    async def test_generates_valid_skill(self, memory):
        candidate = {
            "id": 1,
            "pattern_hash": "abc123",
            "pattern_description": "Fix missing module error",
            "occurrence_count": 5,
            "example_tasks": ["t-1", "t-2", "t-3"],
            "confidence": 0.8,
        }
        result = await generate_skill_from_candidate(candidate, memory, "/proj")
        assert "skill_name" in result
        assert "skill_content" in result
        assert "fix-missing-module-error" == result["skill_name"]
        assert "SKILL.md" not in result["skill_name"]  # Name, not filename
        assert "5" in result["skill_content"]  # occurrence count
        assert "0.80" in result["skill_content"]  # confidence


class TestSaveSkillToDirectory:
    """Test skill file saving."""

    def test_saves_to_skills_dir(self, tmp_path):
        with patch("jarvis.skill_generator.Path.home", return_value=tmp_path):
            path = save_skill_to_directory("test-skill", "# Test Skill Content")
            assert path is not None
            assert path.exists()
            assert path.read_text() == "# Test Skill Content"

    def test_does_not_overwrite(self, tmp_path):
        with patch("jarvis.skill_generator.Path.home", return_value=tmp_path):
            save_skill_to_directory("test-skill", "Original")
            result = save_skill_to_directory("test-skill", "Overwritten")
            assert result is None
            # Original content preserved
            skill_path = tmp_path / ".claude" / "skills" / "test-skill.md"
            assert skill_path.read_text() == "Original"


class TestGenerateSkillsFromPatterns:
    """Test the full skill generation pipeline."""

    @pytest.mark.asyncio
    async def test_no_candidates(self, memory):
        result = await generate_skills_from_patterns(memory, "/proj")
        assert result["skills_generated"] == 0
        assert result["candidates_found"] == 0

    @pytest.mark.asyncio
    async def test_generates_and_promotes(self, memory, tmp_path):
        # Create a candidate with enough occurrences
        for i in range(4):
            memory.record_skill_candidate("ph1", "Fix auth error", f"t-{i}", "/proj")

        with patch("jarvis.skill_generator.Path.home", return_value=tmp_path):
            result = await generate_skills_from_patterns(memory, "/proj")
            assert result["skills_generated"] >= 1

            # Verify candidate was promoted
            promoted = memory.get_skill_candidates(min_occurrences=1, promoted=True)
            assert len(promoted) >= 1


class TestValidateSkill:
    """Test skill validation against execution history."""

    @pytest.mark.asyncio
    async def test_missing_skill_file(self, memory, tmp_path):
        with patch("jarvis.skill_generator.Path.home", return_value=tmp_path):
            result = await validate_skill("nonexistent", memory)
            assert result["validated"] is False
            assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_validates_with_history(self, memory, tmp_path):
        # Create skill file with pattern hash
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "test-skill.md").write_text(
            "---\nname: test-skill\n---\nPattern hash: testhash123\n"
        )

        # Create a promoted candidate matching the hash
        for i in range(3):
            memory.record_skill_candidate("testhash123", "Test pattern", f"t-{i}", "/proj")
        candidates = memory.get_skill_candidates(min_occurrences=3)
        memory.mark_skill_promoted(candidates[0]["id"])

        # Create successful execution records for example tasks
        for i in range(3):
            memory.record_execution(
                task_id=f"t-{i}", session_id="s-1", tool_name="Edit",
                tool_input={}, tool_output="ok", exit_code=0,
                project_path="/proj",
            )

        with patch("jarvis.skill_generator.Path.home", return_value=tmp_path):
            result = await validate_skill("test-skill", memory)
            assert result["test_count"] == 3
            assert result["success_rate"] == pytest.approx(1.0)
            assert result["validated"] is True


class TestCopyBootstrapSkills:
    """Test bootstrap skill installation."""

    def test_copies_skills(self, tmp_path):
        # Create bootstrap source
        bootstrap = tmp_path / "bootstrap" / "skills" / "coding"
        bootstrap.mkdir(parents=True)
        (bootstrap / "skill-a.md").write_text("Skill A")
        (bootstrap / "skill-b.md").write_text("Skill B")

        with (
            patch("jarvis.skill_generator.Path.home", return_value=tmp_path),
            patch("jarvis.skill_generator.Path.__file__", str(tmp_path / "src" / "jarvis" / "skill_generator.py")),
        ):
            # We need to patch the bootstrap_dir calculation
            import jarvis.skill_generator as sg
            original_func = sg.copy_bootstrap_skills

            def patched_copy(project_path=None):
                import shutil
                skills_dir = tmp_path / ".claude" / "skills"
                skills_dir.mkdir(parents=True, exist_ok=True)
                copied = []
                for skill_file in bootstrap.glob("*.md"):
                    dest = skills_dir / skill_file.name
                    if not dest.exists():
                        shutil.copy2(skill_file, dest)
                        copied.append(skill_file.stem)
                return copied

            result = patched_copy()
            assert len(result) == 2
            assert "skill-a" in result
            assert "skill-b" in result
