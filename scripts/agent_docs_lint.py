#!/usr/bin/env python3
"""
Lint rules for .agent governance.

Design goals:
- Deterministic, fail-fast, and low-noise.
- Enforce repo-local governance so docs don't drift as agents iterate quickly.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    message: str

    def format(self) -> str:
        rel = self.path.relative_to(REPO_ROOT) if self.path.is_absolute() else self.path
        return f"{rel}:{self.line}: {self.message}"


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise
    except UnicodeDecodeError:
        # Treat non-UTF8 as a finding; governance docs must be UTF-8.
        return []


def _iter_agent_files(agent_root: Path) -> Iterable[Path]:
    for p in agent_root.rglob("*"):
        if p.is_file():
            yield p


def _find_substring(lines: list[str], needle: str) -> list[int]:
    return [i + 1 for i, line in enumerate(lines) if needle in line]


def _find_regex(lines: list[str], pattern: re.Pattern[str]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if pattern.search(line):
            out.append((i + 1, line))
    return out


def lint_no_stale_paths(agent_root: Path) -> list[Finding]:
    """Fail on stale references to old filenames/paths."""
    findings: list[Finding] = []
    banned = [
        ".agent/ANALYSIS.md",
        "`ANALYSIS.md`",
        "ANALYSIS.md",
        ".agent/ANALYSIS_IMPROVEMENT.md",
    ]
    # Exceptions: allow the literal filename in headings of inflight file.
    exception_file = agent_root / "inflight-communication" / "ANALYSIS_IMPROVEMENT.md"

    for p in _iter_agent_files(agent_root):
        lines = _read_lines(p)
        for needle in banned:
            for ln in _find_substring(lines, needle):
                if p == exception_file and needle in ("ANALYSIS.md", "`ANALYSIS.md`"):
                    # Disallow even here; the filename should not appear anymore.
                    pass
                findings.append(Finding(p, ln, f"Stale reference found: {needle!r}"))
    return findings


def lint_architecture_file(agent_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    arch = agent_root / "ARCHITECTURE.md"
    if not arch.exists():
        return [Finding(arch, 1, "Missing required file")]
    lines = _read_lines(arch)
    if not lines or lines[0].strip() != "# ARCHITECTURE.md":
        findings.append(Finding(arch, 1, "First line must be '# ARCHITECTURE.md'"))

    # ARCHITECTURE.md must not contain in-flight review artifacts.
    # Keep this narrow to avoid false positives: ARCHITECTURE.md may legitimately
    # contain words like "approved" in prose. We only forbid the review/status
    # scaffolding that belongs in the inflight log.
    forbidden_patterns = [
        r"^\s*\*\*Status:",
        r"\bREVIEW:\b",
        r"Codex Review",
        r"Claude Response",
        r"Implementation Status",
        r"Canonical Review Snapshot",
    ]
    combined = re.compile("|".join(forbidden_patterns))
    for ln, _line in _find_regex(lines, combined):
        findings.append(Finding(arch, ln, "In-flight content is not allowed in ARCHITECTURE.md"))
    return findings


def _parse_snapshot_table(lines: list[str]) -> dict[str, str]:
    """
    Parse the canonical snapshot table in ANALYSIS_IMPROVEMENT.md.
    Returns {item_id: status}.
    """
    header = "| Item | Status | Latest Codex Verdict | Open Blocker IDs |"
    try:
        start = lines.index(header)
    except ValueError:
        return {}

    out: dict[str, str] = {}
    for row in lines[start + 2 :]:
        if not row.startswith("|"):
            break
        cols = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cols) < 2:
            continue
        item, status = cols[0], cols[1]
        if item and item != "-":
            out[item] = status
    return out


def _has_snapshot_table(lines: list[str]) -> bool:
    header = "| Item | Status | Latest Codex Verdict | Open Blocker IDs |"
    return header in lines


def _extract_item_status(lines: list[str], item_id: str) -> tuple[int, str] | None:
    """
    Find the per-item '**Status: X**' line under the '#### <ID>.' heading.
    Returns (line_number, status_value).
    """
    # Note: don't use a word-boundary after the '.'; '.' and space are both
    # non-word chars so \b won't match. The heading format we require is:
    # "#### A2. Title..."
    heading_re = re.compile(rf"^####\s+{re.escape(item_id)}\.")
    # Allow an optional suffix after the bold status, e.g. "(Round 5: ...)".
    status_re = re.compile(r"^\s*\*\*Status:\s*([A-Z_]+)\*\*(?:\s+.*)?\s*$")

    for i, line in enumerate(lines):
        if heading_re.match(line):
            # Scan forward a bounded window to find status line.
            for j in range(i + 1, min(i + 40, len(lines))):
                m = status_re.match(lines[j])
                if m:
                    return (j + 1, m.group(1))
            return None
    return None


def lint_inflight_status_consistency(agent_root: Path) -> list[Finding]:
    """Ensure snapshot table matches per-item Status lines."""
    findings: list[Finding] = []
    inflight = agent_root / "inflight-communication" / "ANALYSIS_IMPROVEMENT.md"
    if not inflight.exists():
        return [Finding(inflight, 1, "Missing required inflight file")]

    lines = _read_lines(inflight)
    if not _has_snapshot_table(lines):
        findings.append(Finding(inflight, 1, "Missing or unparsable snapshot table"))
        return findings
    snapshot = _parse_snapshot_table(lines)
    # It's valid for the snapshot to be empty when there are no open items.
    if not snapshot:
        return findings

    for item_id, snapshot_status in snapshot.items():
        extracted = _extract_item_status(lines, item_id)
        if extracted is None:
            findings.append(Finding(inflight, 1, f"Missing per-item section/status for {item_id}"))
            continue
        ln, item_status = extracted
        if item_status != snapshot_status:
            findings.append(
                Finding(
                    inflight,
                    ln,
                    f"Status mismatch for {item_id}: snapshot={snapshot_status!r} item={item_status!r}",
                )
            )
    return findings


def lint_agent_path_references_exist(agent_root: Path) -> list[Finding]:
    """Ensure `.agent/...` backtick path references exist on disk."""
    findings: list[Finding] = []
    path_re = re.compile(r"`(\.agent/[A-Za-z0-9_\-./]+)`")
    # Local-only configs are allowed to be missing (secrets/tokens not in git).
    allowed_missing = {
        ".agent/comms_config.json",
    }
    for p in _iter_agent_files(agent_root):
        lines = _read_lines(p)
        for i, line in enumerate(lines):
            for m in path_re.finditer(line):
                rel = m.group(1)
                if rel in allowed_missing:
                    continue
                target = REPO_ROOT / rel
                if not target.exists():
                    findings.append(Finding(p, i + 1, f"Referenced path does not exist: {rel}"))
    return findings


def main() -> int:
    agent_root = REPO_ROOT / ".agent"
    if not agent_root.exists():
        print("ERROR: .agent folder not found", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    findings.extend(lint_architecture_file(agent_root))
    findings.extend(lint_inflight_status_consistency(agent_root))
    findings.extend(lint_agent_path_references_exist(agent_root))
    findings.extend(lint_no_stale_paths(agent_root))

    if findings:
        print("AGENT DOCS LINT FAILED\n", file=sys.stderr)
        for f in findings:
            print(f.format(), file=sys.stderr)
        print(f"\nTotal findings: {len(findings)}", file=sys.stderr)
        return 1

    print("AGENT DOCS LINT OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
