"""Shared test fixtures for Jarvis test suite."""

import os
import tempfile
from pathlib import Path

import pytest

from jarvis.memory import MemoryStore


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def memory(tmp_path):
    """Provide a MemoryStore backed by a temporary database."""
    db_path = tmp_path / "test_jarvis.db"
    return MemoryStore(db_path=db_path)


@pytest.fixture
def project_path(tmp_path):
    """Provide a temporary project directory with basic structure."""
    project = tmp_path / "test_project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "src" / "main.py").write_text("def main():\n    print('hello')\n")
    (project / "src" / "utils.py").write_text("def helper():\n    return 42\n")
    (project / "tests").mkdir()
    (project / "tests" / "test_main.py").write_text("def test_main():\n    pass\n")
    (project / "pyproject.toml").write_text('[project]\nname = "test"\n')
    (project / "requirements.txt").write_text("flask>=3.0\n")
    return str(project)
