"""Tests for jarvis.universal_heuristics — cold-start learning injection."""

from pathlib import Path

import pytest

from jarvis.universal_heuristics import (
    UNIVERSAL_HEURISTICS,
    auto_seed_project,
    detect_project_languages,
    seed_universal_heuristics,
)


class TestUniversalHeuristics:
    """Test the heuristics collection itself."""

    def test_has_entries(self):
        assert len(UNIVERSAL_HEURISTICS) >= 10

    def test_all_have_required_fields(self):
        for h in UNIVERSAL_HEURISTICS:
            assert "language" in h
            assert "error_pattern" in h
            assert "fix_description" in h
            assert "fix_diff" in h
            assert "confidence" in h

    def test_all_languages_covered(self):
        languages = {h["language"] for h in UNIVERSAL_HEURISTICS}
        assert "python" in languages
        assert "javascript" in languages
        assert "rust" in languages
        assert "docker" in languages
        assert "git" in languages


class TestSeedUniversalHeuristics:
    """Test heuristic seeding into project."""

    def test_seed_all(self, memory):
        result = seed_universal_heuristics(memory, "/proj")
        assert result["seeded"] == len(UNIVERSAL_HEURISTICS)
        assert result["skipped"] == 0

    def test_seed_by_language(self, memory):
        result = seed_universal_heuristics(memory, "/proj", languages=["python"])
        python_count = sum(1 for h in UNIVERSAL_HEURISTICS if h["language"] == "python")
        assert result["seeded"] == python_count
        assert result["skipped"] == len(UNIVERSAL_HEURISTICS) - python_count

    def test_idempotent(self, memory):
        result1 = seed_universal_heuristics(memory, "/proj")
        result2 = seed_universal_heuristics(memory, "/proj")
        assert result1["seeded"] > 0
        assert result2["seeded"] == 0  # All skipped on second run
        assert result2["skipped"] == len(UNIVERSAL_HEURISTICS)

    def test_seeded_learnings_queryable(self, memory):
        seed_universal_heuristics(memory, "/proj", languages=["python"])
        learnings = memory.get_learnings(project_path="/proj", min_confidence=0.0)
        assert len(learnings) > 0
        assert all(l["project_path"] == "/proj" for l in learnings)


class TestDetectProjectLanguages:
    """Test language auto-detection."""

    def test_detect_python(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]")
        languages = detect_project_languages(str(tmp_path))
        assert "python" in languages

    def test_detect_javascript(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        languages = detect_project_languages(str(tmp_path))
        assert "javascript" in languages

    def test_detect_rust(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text("[package]")
        languages = detect_project_languages(str(tmp_path))
        assert "rust" in languages

    def test_detect_go(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com")
        languages = detect_project_languages(str(tmp_path))
        assert "go" in languages

    def test_detect_docker(self, tmp_path):
        (tmp_path / "Dockerfile").write_text("FROM python:3.11")
        languages = detect_project_languages(str(tmp_path))
        assert "docker" in languages

    def test_detect_git(self, tmp_path):
        (tmp_path / ".git").mkdir()
        languages = detect_project_languages(str(tmp_path))
        assert "git" in languages

    def test_detect_from_files(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")
        languages = detect_project_languages(str(tmp_path))
        assert "python" in languages

    def test_multiple_languages(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]")
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / ".git").mkdir()
        languages = detect_project_languages(str(tmp_path))
        assert "python" in languages
        assert "javascript" in languages
        assert "git" in languages

    def test_empty_project(self, tmp_path):
        languages = detect_project_languages(str(tmp_path))
        assert languages == []


class TestAutoSeedProject:
    """Test end-to-end auto-seeding."""

    @pytest.mark.asyncio
    async def test_auto_seed_python_project(self, memory, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]")
        (tmp_path / ".git").mkdir()
        result = await auto_seed_project(memory, str(tmp_path))
        assert result["seeded"] > 0
        assert "python" in result["languages"]
        assert "git" in result["languages"]

    @pytest.mark.asyncio
    async def test_auto_seed_empty_project(self, memory, tmp_path):
        result = await auto_seed_project(memory, str(tmp_path))
        assert result["seeded"] == 0
        assert result["languages"] == []
