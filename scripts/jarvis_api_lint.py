#!/usr/bin/env python3
"""
Lint rules for Jarvis WebSocket API usage.

Prevents common mistakes identified from debugging sessions:
1. Wrong message format (message at top level instead of in data wrapper)
2. Missing data wrapper in WebSocket messages

Run: python3 scripts/jarvis_api_lint.py
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent

# WebSocket actions that require data wrapper
ACTIONS_REQUIRING_DATA = {
    "chat",
    "run_task",
    "message",
    "approve",
    "deny",
    "read_file",
    "git_status",
    "build_project",
    "run_tests",
    "analyze_code",
    "process_file",
}

# Actions that don't require data (or have different structure)
ACTIONS_EXEMPT = {
    "get_status",
    "get_timeline",
    "get_available_tools",
    "get_capabilities",
    "get_containers",
}


@dataclass(frozen=True)
class Finding:
    file: Path
    line: int
    message: str
    severity: str = "error"

    def format(self) -> str:
        rel = self.file.relative_to(REPO_ROOT) if self.file.is_absolute() else self.file
        return f"{rel}:{self.line}: [{self.severity.upper()}] {self.message}"


def _iter_python_files(paths: Iterable[Path]) -> Iterable[Path]:
    for p in paths:
        if p.is_file() and p.suffix == ".py":
            yield p
        elif p.is_dir():
            for child in p.rglob("*.py"):
                yield child


def _extract_json_dumps_args(node: ast.Call) -> dict | None:
    """Extract the dict passed to json.dumps() if it's a literal."""
    if not isinstance(node.func, ast.Attribute):
        return None
    if node.func.attr != "dumps":
        return None
    if not isinstance(node.func.value, ast.Name) or node.func.value.id != "json":
        return None
    if not node.args:
        return None

    # Try to parse the dict literal
    arg = node.args[0]
    if isinstance(arg, ast.Dict):
        result = {}
        for key, value in zip(arg.keys, arg.values):
            if isinstance(key, ast.Constant):
                key_str = key.value
                if isinstance(value, ast.Constant):
                    result[key_str] = value.value
                elif isinstance(value, ast.Dict):
                    result[key_str] = "<dict>"
                else:
                    result[key_str] = "<expr>"
        return result
    return None


def lint_ws_message_format(content: str, filepath: Path) -> list[Finding]:
    """Check for wrong WebSocket message format patterns."""
    findings = []

    # Pattern 1: Direct message field at top level with action
    # Matches: {"action": "chat", "message": "..."} but NOT comments explaining wrong format
    pattern1 = re.compile(
        r'\{\s*"action"\s*:\s*"(chat|run_task|message)"\s*,\s*"message"\s*:'
    )
    for i, line in enumerate(content.splitlines(), 1):
        # Skip lines that are comments explaining the wrong format
        if "#" in line and ("WRONG" in line or "wrong" in line or "example" in line.lower()):
            continue
        if pattern1.search(line):
            findings.append(
                Finding(
                    filepath,
                    i,
                    f"WebSocket message uses top-level 'message' instead of 'data.message' wrapper. "
                    f"Use: {{'action': '{pattern1.search(line).group(1)}', 'data': {{'message': '...'}}}}",
                    "error",
                )
            )

    # Pattern 2: json.dumps with action but no data wrapper
    pattern2 = re.compile(
        r'json\.dumps\(\s*\{\s*"action"\s*:\s*"([^"]+)"\s*,\s*"message"\s*:'
    )
    for i, line in enumerate(content.splitlines(), 1):
        match = pattern2.search(line)
        if match:
            action = match.group(1)
            if action in ACTIONS_REQUIRING_DATA:
                findings.append(
                    Finding(
                        filepath,
                        i,
                        f"json.dumps() with action='{action}' missing 'data' wrapper. "
                        f"Use: {{'action': '{action}', 'data': {{'message': '...'}}}}",
                        "error",
                    )
                )

    # Pattern 3: Check AST for ws.send with wrong format
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for ws.send(json.dumps(...))
                if isinstance(node.func, ast.Attribute) and node.func.attr == "send":
                    if node.args:
                        arg = node.args[0]
                        if isinstance(arg, ast.Call):
                            data = _extract_json_dumps_args(arg)
                            if data:
                                action = data.get("action")
                                if action in ACTIONS_REQUIRING_DATA:
                                    if "message" in data and "data" not in data:
                                        findings.append(
                                            Finding(
                                                filepath,
                                                node.lineno,
                                                f"ws.send() with action='{action}' has 'message' at top level. "
                                                f"Move to 'data' wrapper.",
                                                "error",
                                            )
                                        )
    except SyntaxError:
        pass  # Skip files with syntax errors

    return findings


def lint_daemon_log_path(content: str, filepath: Path) -> list[Finding]:
    """Check for wrong daemon log path references."""
    findings = []

    # Common mistake: checking /tmp/jarvis-daemon.log for runtime logs
    # Runtime logs are at ~/.jarvis/logs/daemon.log
    wrong_patterns = [
        (r'tail\s+"?/tmp/jarvis-daemon\.log"?', "Use ~/.jarvis/logs/daemon.log for runtime logs"),
        (r'cat\s+"?/tmp/jarvis-daemon\.log"?', "Use ~/.jarvis/logs/daemon.log for runtime logs"),
        (r'read_file.*"/tmp/jarvis-daemon\.log"', "Use ~/.jarvis/logs/daemon.log for runtime logs"),
    ]

    for i, line in enumerate(content.splitlines(), 1):
        for pattern, suggestion in wrong_patterns:
            if re.search(pattern, line):
                findings.append(
                    Finding(filepath, i, f"Wrong daemon log path. {suggestion}", "warning")
                )

    return findings


def lint_missing_bytecode_clear(content: str, filepath: Path) -> list[Finding]:
    """Check for test files that modify Python but don't clear cache."""
    findings = []

    # If file imports from src/jarvis and has test functions,
    # recommend clearing bytecode cache
    if "test_" in filepath.name or "tests/" in str(filepath):
        if "import jarvis" in content or "from jarvis" in content:
            # Check if there's any cache clearing
            if "pycache" not in content and ".pyc" not in content:
                # This is just a warning for awareness
                pass  # Don't spam warnings

    return findings


def main() -> int:
    # Check all Python files in tests/ and any test files
    paths_to_check = [
        REPO_ROOT / "tests",
        REPO_ROOT / "scripts",
    ]

    # Also check any files passed as arguments
    if len(sys.argv) > 1:
        paths_to_check.extend(Path(arg) for arg in sys.argv[1:])

    findings: list[Finding] = []
    files_checked = 0

    for filepath in _iter_python_files(paths_to_check):
        try:
            content = filepath.read_text(encoding="utf-8")
        except (FileNotFoundError, UnicodeDecodeError):
            continue

        files_checked += 1
        findings.extend(lint_ws_message_format(content, filepath))
        findings.extend(lint_daemon_log_path(content, filepath))

    if findings:
        print("JARVIS API LINT FAILED\n", file=sys.stderr)
        for f in sorted(findings, key=lambda x: (str(x.file), x.line)):
            print(f.format(), file=sys.stderr)
        print(f"\nTotal findings: {len(findings)}", file=sys.stderr)
        print(f"Files checked: {files_checked}", file=sys.stderr)
        return 1

    print(f"JARVIS API LINT OK ({files_checked} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
