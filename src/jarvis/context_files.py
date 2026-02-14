"""Core markdown context and per-project JARVIS memory files."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_FILES = ["AGENTS.md", "workflow.md", "principles.md", "soul.md", "memory.md"]
TURN_LOG_MARKER = "## Turn Log"
PROJECT_CONTEXT_FILENAME = "PROJECT-CONTEXT.md"

PROJECT_JARVIS_TEMPLATE = """# JARVIS.md

## Project Context
- Keep this file concise and current.
- Store only actionable project-specific memory.

## Workflow Notes
- Follow core workflow and principles from Jarvis core files.

## Turn Log
"""

PROJECT_CONTEXT_TEMPLATE = """# PROJECT-CONTEXT.md

## Project Snapshot
- Name:
- Goal:
- Primary Stack:
- Runtime/Env:

## Working Agreements
- Keep plans short and testable.
- Record only high-signal decisions.
- Fail fast and keep errors explicit.

## Current Focus
- In progress:
- Blockers:
- Next validation step:

## Decision Log
- YYYY-MM-DD: <decision> | Why: <reason> | Result: <outcome>
"""


def ensure_core_context_files() -> None:
    """No-op: core context is maintained in repo files, not generated."""
    return None


def load_core_context(max_chars: int = 16000) -> str:
    """Return compact core markdown context for prompts."""
    sections: list[str] = []
    for filename in CORE_FILES:
        path = REPO_ROOT / filename
        if not path.exists():
            continue
        text = path.read_text().strip()
        if not text:
            continue
        sections.append(f"### {filename}\n{text}")
    joined = "\n\n".join(sections)
    return joined[:max_chars]


def resolve_project_jarvis_file(project_path: str | Path) -> Path:
    project = Path(project_path)
    canonical = project / "JARVIS.md"
    legacy = project / "Jarvis.md"
    if canonical.exists():
        return canonical
    if legacy.exists():
        return legacy
    return canonical


def is_jarvis_repo_path(project_path: str | Path) -> bool:
    """True when project_path points inside the Jarvis codebase itself."""
    project = Path(project_path).resolve()
    return project == REPO_ROOT or REPO_ROOT in project.parents


def should_use_project_jarvis(project_path: str | Path) -> bool:
    """Only use project JARVIS.md for non-Jarvis target projects."""
    return not is_jarvis_repo_path(project_path)


def ensure_project_jarvis_file(project_path: str | Path) -> Path | None:
    """Ensure project has JARVIS.md (legacy Jarvis.md still supported)."""
    if not should_use_project_jarvis(project_path):
        return None
    path = resolve_project_jarvis_file(project_path)
    if not path.exists():
        path.write_text(PROJECT_JARVIS_TEMPLATE)
    return path


def ensure_project_context_file(project_path: str | Path) -> Path | None:
    """Ensure project has a minimal PROJECT-CONTEXT.md template."""
    if not should_use_project_jarvis(project_path):
        return None
    project = Path(project_path)
    path = project / PROJECT_CONTEXT_FILENAME
    if not path.exists():
        path.write_text(PROJECT_CONTEXT_TEMPLATE)
    return path


def append_project_turn(
    project_path: str | Path,
    *,
    actor: str,
    message: str,
    outcome: str,
    max_entries: int = 24,
) -> None:
    """Append bounded turn history for project continuity."""
    path = ensure_project_jarvis_file(project_path)
    if path is None:
        return
    content = path.read_text() if path.exists() else PROJECT_JARVIS_TEMPLATE
    if TURN_LOG_MARKER not in content:
        content = content.rstrip() + f"\n\n{TURN_LOG_MARKER}\n"

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = " ".join((message or "").strip().split())[:280]
    out = " ".join((outcome or "").strip().split())[:420]
    entry = f"\n### {ts}\n- Actor: {actor}\n- Input: {msg}\n- Outcome: {out}\n"
    updated = content.rstrip() + entry + "\n"

    head, _, tail = updated.partition(TURN_LOG_MARKER)
    turns = [t.strip() for t in tail.strip().split("### ") if t.strip()]
    if len(turns) > max_entries:
        turns = turns[-max_entries:]
    rendered_turns = "\n\n".join(f"### {t}" for t in turns)
    if rendered_turns:
        rendered_turns = "\n\n" + rendered_turns
    final_text = f"{head}{TURN_LOG_MARKER}{rendered_turns}\n"
    path.write_text(final_text)
