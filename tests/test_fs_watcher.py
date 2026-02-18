"""Tests for jarvis.fs_watcher — file system monitoring."""

import time
from pathlib import Path

import pytest

from jarvis.fs_watcher import FileSnapshot, FileSystemWatcher, _file_hash, _should_watch


class TestShouldWatch:
    """Test file watch filtering."""

    def test_python_files(self):
        assert _should_watch(Path("src/main.py")) is True

    def test_javascript_files(self):
        assert _should_watch(Path("src/app.ts")) is True
        assert _should_watch(Path("src/index.js")) is True

    def test_rust_files(self):
        assert _should_watch(Path("src/main.rs")) is True

    def test_config_files(self):
        assert _should_watch(Path("config.yaml")) is True
        assert _should_watch(Path("package.json")) is True
        assert _should_watch(Path("pyproject.toml")) is True

    def test_ignores_non_code_files(self):
        assert _should_watch(Path("image.png")) is False
        assert _should_watch(Path("data.csv")) is False
        assert _should_watch(Path("README.md")) is False

    def test_ignores_hidden_dirs(self):
        assert _should_watch(Path(".git/config.json")) is False
        assert _should_watch(Path("node_modules/foo/index.js")) is False
        assert _should_watch(Path("__pycache__/mod.py")) is False


class TestFileHash:
    """Test file content hashing."""

    def test_hash_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("hello")
        h = _file_hash(f)
        assert h is not None
        assert len(h) == 32  # MD5 hex digest

    def test_same_content_same_hash(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("same")
        f2.write_text("same")
        assert _file_hash(f1) == _file_hash(f2)

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("foo")
        f2.write_text("bar")
        assert _file_hash(f1) != _file_hash(f2)

    def test_missing_file_returns_none(self, tmp_path):
        assert _file_hash(tmp_path / "nonexistent.py") is None


class TestFileSystemWatcher:
    """Test file system watcher change detection."""

    def _make_watcher(self, memory, project_path):
        return FileSystemWatcher(
            project_path=project_path,
            memory=memory,
            poll_interval=0.1,
            debounce=0.1,
        )

    def test_scan_files(self, memory, project_path):
        watcher = self._make_watcher(memory, project_path)
        snapshots = watcher._scan_files()
        # project_path has src/main.py, src/utils.py, tests/test_main.py, pyproject.toml
        assert len(snapshots) >= 3

    def test_detect_created_file(self, memory, project_path):
        watcher = self._make_watcher(memory, project_path)
        watcher._snapshots = watcher._scan_files()

        # Create new file
        (Path(project_path) / "src" / "new_file.py").write_text("new code")
        new_snapshots = watcher._scan_files()
        changes = watcher._detect_changes(new_snapshots)
        assert any(v == "created" for v in changes.values())

    def test_detect_modified_file(self, memory, project_path):
        watcher = self._make_watcher(memory, project_path)
        watcher._snapshots = watcher._scan_files()

        # Modify a file (advance mtime)
        main_py = Path(project_path) / "src" / "main.py"
        time.sleep(0.01)
        main_py.write_text("def main():\n    print('modified')\n")

        new_snapshots = watcher._scan_files()
        changes = watcher._detect_changes(new_snapshots)
        modified = [k for k, v in changes.items() if v == "modified"]
        assert any("main.py" in f for f in modified)

    def test_detect_deleted_file(self, memory, project_path):
        watcher = self._make_watcher(memory, project_path)
        watcher._snapshots = watcher._scan_files()

        # Delete a file
        (Path(project_path) / "src" / "utils.py").unlink()
        new_snapshots = watcher._scan_files()
        changes = watcher._detect_changes(new_snapshots)
        deleted = [k for k, v in changes.items() if v == "deleted"]
        assert any("utils.py" in f for f in deleted)

    def test_invalidate_learnings(self, memory, project_path):
        # Create a learning that references main.py
        memory.save_learning(
            project_path=project_path,
            language="python",
            error_pattern_hash="h1",
            error_message="Error in main.py",
            fix_description="Fix the issue",
            fix_diff="--- main.py\n+fixed",
        )

        watcher = self._make_watcher(memory, project_path)
        invalidated = watcher._invalidate_learnings(["src/main.py"])
        assert invalidated >= 1

        # Verify the learning is marked for revalidation
        learnings = memory.get_learnings(project_path=project_path, min_confidence=0.0)
        assert any(l["needs_revalidation"] == 1 for l in learnings)

    def test_get_stats(self, memory, project_path):
        watcher = self._make_watcher(memory, project_path)
        watcher._snapshots = watcher._scan_files()
        stats = watcher.get_stats()
        assert stats["project_path"] == project_path
        assert stats["files_tracked"] >= 3
        assert stats["running"] is False

    def test_change_callback(self, memory, project_path):
        watcher = self._make_watcher(memory, project_path)
        changes_received = []
        watcher.add_change_callback(lambda c: changes_received.append(c))
        # Verify callback registered
        assert len(watcher._change_callbacks) == 1

    @pytest.mark.asyncio
    async def test_start_stop(self, memory, project_path):
        watcher = self._make_watcher(memory, project_path)
        await watcher.start()
        assert watcher._running is True
        await watcher.stop()
        assert watcher._running is False
