#!/usr/bin/env python3
"""
Jarvis Validation Script - Comprehensive health check for Jarvis system.

Run: python3 scripts/validate_jarvis.py
Or:  python3 scripts/validate_jarvis.py --full

Checks:
1. API Lint - WebSocket message format validation
2. Config Integrity - Config file validation
3. Import Validation - All imports resolve correctly
4. Port Availability - WS (9847) and A2A (9848) ports
5. Database Integrity - SQLite schema validation
6. Governance Lint - Agent docs/research/memory contracts
7. Test Suite - Core tests pass
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
JARVIS_HOME = Path.home() / ".jarvis"


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    message: str
    details: str | None = None


def check_api_lint() -> CheckResult:
    """Run WebSocket API lint checks."""
    try:
        result = subprocess.run(
            [sys.executable, "scripts/jarvis_api_lint.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return CheckResult("API Lint", True, "All API checks passed")
        return CheckResult("API Lint", False, "API lint errors found", result.stderr)
    except Exception as e:
        return CheckResult("API Lint", False, f"Failed to run: {e}")


def check_agent_docs_lint() -> CheckResult:
    """Run governance/docs lint checks (research + memory gates)."""
    try:
        result = subprocess.run(
            [sys.executable, "scripts/agent_docs_lint.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return CheckResult("Governance Lint", True, "Governance docs + memory checks passed")
        return CheckResult("Governance Lint", False, "Governance lint errors found", result.stderr)
    except Exception as e:
        return CheckResult("Governance Lint", False, f"Failed to run: {e}")


def check_imports() -> CheckResult:
    """Validate all Jarvis imports resolve correctly."""
    src_dir = REPO_ROOT / "src" / "jarvis"
    errors = []

    for py_file in src_dir.rglob("*.py"):
        if py_file.name.startswith("_") and py_file.stem != "__init__":
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        try:
                            if alias.name.startswith("jarvis"):
                                spec = importlib.util.find_spec(alias.name)
                                if spec is None:
                                    errors.append(f"{py_file.name}: Cannot import {alias.name}")
                        except Exception:
                            pass
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("jarvis"):
                        try:
                            spec = importlib.util.find_spec(node.module)
                            if spec is None:
                                errors.append(f"{py_file.name}: Cannot import {node.module}")
                        except Exception:
                            pass
        except SyntaxError as e:
            errors.append(f"{py_file.name}: Syntax error: {e}")

    if errors:
        return CheckResult(
            "Import Validation", False, f"{len(errors)} import errors", "\n".join(errors[:5])
        )
    return CheckResult("Import Validation", True, "All imports resolve correctly")


def check_config_integrity() -> CheckResult:
    """Validate config file exists and has required fields."""
    config_path = JARVIS_HOME / "system" / "jarvis_config" / "config.json"

    if not config_path.exists():
        return CheckResult(
            "Config Integrity", False, "Config file missing", f"Expected: {config_path}"
        )

    try:
        config = json.loads(config_path.read_text())
        # Check for required config sections
        required_sections = ["budget"]
        missing = [s for s in required_sections if s not in config]

        if missing:
            return CheckResult("Config Integrity", False, f"Missing sections: {missing}")

        # Validate budget section
        if "budget" in config:
            budget_required = ["max_per_day_usd", "max_per_session_usd", "max_turns_per_task"]
            budget_missing = [b for b in budget_required if b not in config["budget"]]
            if budget_missing:
                return CheckResult(
                    "Config Integrity", False, f"Missing budget fields: {budget_missing}"
                )

        return CheckResult("Config Integrity", True, "Config valid")
    except json.JSONDecodeError as e:
        return CheckResult("Config Integrity", False, f"Invalid JSON: {e}")
    except Exception as e:
        return CheckResult("Config Integrity", False, f"Error: {e}")


def check_database_integrity() -> CheckResult:
    """Validate SQLite database schema."""
    db_path = JARVIS_HOME / "jarvis.db"

    if not db_path.exists():
        return CheckResult("Database Integrity", False, "Database missing", f"Expected: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check for required tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        required_tables = {"tasks", "session_summaries", "learnings", "timeline_events"}
        missing = required_tables - tables

        conn.close()

        if missing:
            return CheckResult("Database Integrity", False, f"Missing tables: {missing}")
        return CheckResult("Database Integrity", True, "Database schema valid")
    except Exception as e:
        return CheckResult("Database Integrity", False, f"Error: {e}")


def _can_connect(port: int) -> bool:
    """Return True when something is listening on localhost:port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        sock.connect(("127.0.0.1", port))
        sock.close()
        return True
    except PermissionError:
        sock.close()
        result = subprocess.run(
            ["lsof", "-n", "-P", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        sock.close()
        return False


def check_ports() -> CheckResult:
    """Validate expected ports are in expected state."""
    ws_port = 9847
    a2a_port = 9848

    ws_open = _can_connect(ws_port)
    a2a_open = _can_connect(a2a_port)

    # Both ports should be open together when daemon is healthy.
    if ws_open and a2a_open:
        return CheckResult("Port Validation", True, "Both ports in use (daemon running)")
    if not ws_open and not a2a_open:
        return CheckResult("Port Validation", True, "Both ports closed (daemon not running)")
    return CheckResult(
        "Port Validation",
        False,
        f"Inconsistent port state: WS_open={ws_open}, A2A_open={a2a_open}",
    )


def check_core_tests() -> CheckResult:
    """Run core test suite."""
    test_files = [
        "tests/test_orchestrator_handle_message.py",
        "tests/test_a2a_evidence.py",
        "tests/test_memory.py",
    ]

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest"] + test_files + ["-v", "--tb=short"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode == 0:
            # Extract pass count
            output = result.stdout
            if "passed" in output:
                return CheckResult("Core Tests", True, "All core tests passed")
        return CheckResult("Core Tests", False, "Test failures", result.stdout[-500:])
    except Exception as e:
        return CheckResult("Core Tests", False, f"Failed to run: {e}")


def check_daemon_health() -> CheckResult:
    """Check if daemon is running and healthy."""
    # Prefer live endpoint checks first; tolerate launch race by retrying briefly.
    deadline = time.time() + 12
    while time.time() < deadline:
        try:
            import httpx

            response = httpx.get("http://127.0.0.1:9848/health", timeout=2)
            if response.status_code == 200:
                return CheckResult("Daemon Health", True, "Daemon responding on A2A port")
        except Exception:
            pass

        if _can_connect(9847):
            return CheckResult("Daemon Health", True, "Daemon responding on WS port")

        if _can_connect(9848):
            return CheckResult(
                "Daemon Health",
                True,
                "Daemon process listening on A2A port (health probe unavailable)",
            )

        time.sleep(0.5)

    # Check process
    result = subprocess.run(
        ["pgrep", "-f", "jarvis.daemon"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return CheckResult("Daemon Health", True, "Daemon process running (ports may differ)")
    return CheckResult("Daemon Health", False, "Daemon not running")


def check_dependencies() -> CheckResult:
    """Check required dependencies are installed."""
    required = [
        "click",
        "rich",
        "httpx",
        "websockets",
        "fastapi",
        "uvicorn",
    ]

    missing = []
    for dep in required:
        spec = importlib.util.find_spec(dep)
        if spec is None:
            missing.append(dep)

    if missing:
        return CheckResult("Dependencies", False, f"Missing: {missing}")
    return CheckResult("Dependencies", True, "All dependencies installed")


def check_mcp_servers() -> CheckResult:
    """Check MCP server configuration."""
    mcp_config = REPO_ROOT / ".codex" / "config.toml"

    if not mcp_config.exists():
        mcp_config = Path.home() / ".claude" / "settings.json"

    if not mcp_config.exists():
        return CheckResult("MCP Servers", True, "No MCP config found (optional)")

    return CheckResult("MCP Servers", True, "MCP config exists")


def run_all_checks(full: bool = False) -> list[CheckResult]:
    """Run all validation checks."""
    checks = [
        check_dependencies,
        check_imports,
        check_config_integrity,
        check_database_integrity,
        check_ports,
        check_agent_docs_lint,
        check_api_lint,
    ]

    if full:
        checks.extend(
            [
                check_daemon_health,
                check_core_tests,
                check_mcp_servers,
            ]
        )

    return [check() for check in checks]


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate Jarvis system")
    parser.add_argument(
        "--full", action="store_true", help="Run full validation including daemon tests"
    )
    args = parser.parse_args()

    results = run_all_checks(full=args.full)

    print("=" * 60)
    print("JARVIS VALIDATION")
    print("=" * 60)

    passed = 0
    failed = 0

    for result in results:
        status = "✓" if result.passed else "✗"
        print(f"\n{status} {result.name}")
        print(f"  {result.message}")
        if result.details and not result.passed:
            for line in result.details.split("\n")[:3]:
                print(f"    {line}")

        if result.passed:
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
