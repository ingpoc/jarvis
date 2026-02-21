"""Core markdown context and per-project JARVIS memory files."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from jarvis.config import (
    JARVIS_CONFIG,
    JARVIS_HOME,
    JARVIS_MCP_RUNTIME_CONFIG,
    JARVIS_OPENCODE_CONFIG,
    JARVIS_RUNTIME_WORKFLOW_DIR,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
IMMUTABLE_CONTEXT_DIR = JARVIS_CONFIG.parent
RUNTIME_CONTEXT_DIR = JARVIS_RUNTIME_WORKFLOW_DIR
IMMUTABLE_CONTEXT_FILES = ["IDENTITY.md", "SOUL.md", "PRINCIPLES.md"]
RUNTIME_CONTEXT_FILES = ["AGENTS.md", "workflow.md", "memory.md"]
TURN_LOG_MARKER = "## Turn Log"
PROJECT_CONTEXT_FILENAME = "PROJECT-CONTEXT.md"
JARVIS_WORKSPACE_DYNAMIC_MCP = JARVIS_HOME / "workspaces" / ".opencode" / ".mcp.json"

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
    """Ensure strict Jarvis runtime/system context files exist under ~/.jarvis."""
    JARVIS_HOME.mkdir(parents=True, exist_ok=True)
    IMMUTABLE_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    # Immutable, human-managed baseline files
    _seed_file(
        IMMUTABLE_CONTEXT_DIR / "IDENTITY.md",
        [
            REPO_ROOT / "IDENTITY.md",
        ],
        "# IDENTITY\n\n- Human-managed immutable identity contract.\n",
    )
    _seed_file(
        IMMUTABLE_CONTEXT_DIR / "SOUL.md",
        [
            REPO_ROOT / "soul.md",
            REPO_ROOT / "SOUL.md",
        ],
        "# SOUL\n\n- Human-managed immutable values and behavior guardrails.\n",
    )
    _seed_file(
        IMMUTABLE_CONTEXT_DIR / "PRINCIPLES.md",
        [
            REPO_ROOT / "principles.md",
            REPO_ROOT / "PRINCIPLES.md",
        ],
        "# PRINCIPLES\n\n- Human-managed immutable engineering principles.\n",
    )

    # Mutable runtime workflow files
    _seed_file(
        RUNTIME_CONTEXT_DIR / "AGENTS.md",
        [
            REPO_ROOT / "AGENTS.md",
        ],
        "# AGENTS\n\n- Runtime workflow instructions.\n",
    )
    _seed_file(
        RUNTIME_CONTEXT_DIR / "workflow.md",
        [
            REPO_ROOT / "workflow.md",
            REPO_ROOT / "WORKFLOW.md",
        ],
        "# workflow\n\n- Runtime workflow playbook.\n",
    )
    _seed_file(
        RUNTIME_CONTEXT_DIR / "memory.md",
        [
            REPO_ROOT / "memory.md",
            REPO_ROOT / "MEMORY.md",
        ],
        "# memory\n\n- Runtime learning and memory rules.\n",
    )

    if not _sync_runtime_mcp_from_opencode(
        JARVIS_OPENCODE_CONFIG,
        JARVIS_MCP_RUNTIME_CONFIG,
        dynamic_overlay_path=JARVIS_WORKSPACE_DYNAMIC_MCP,
    ):
        if not JARVIS_MCP_RUNTIME_CONFIG.exists():
            repo_mcp = REPO_ROOT / ".mcp.json"
            if repo_mcp.exists():
                JARVIS_MCP_RUNTIME_CONFIG.write_text(repo_mcp.read_text())
            else:
                JARVIS_MCP_RUNTIME_CONFIG.write_text('{"mcpServers": {}}\n')


def load_core_context(max_chars: int = 16000) -> str:
    """Return compact core markdown context from strict ~/.jarvis locations."""
    ensure_core_context_files()
    sections: list[str] = []
    ordered_paths = [
        *(IMMUTABLE_CONTEXT_DIR / f for f in IMMUTABLE_CONTEXT_FILES),
        *(RUNTIME_CONTEXT_DIR / f for f in RUNTIME_CONTEXT_FILES),
    ]
    for path in ordered_paths:
        if not path.exists():
            continue
        text = path.read_text().strip()
        if not text:
            continue
        sections.append(f"### {path.name}\n{text}")
    joined = "\n\n".join(sections)
    return joined[:max_chars]


def _seed_file(path: Path, candidates: list[Path], default_text: str) -> None:
    """Create a file from first existing candidate or fallback text."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    for source in candidates:
        if source.exists():
            path.write_text(source.read_text())
            return
    path.write_text(default_text)


def _sync_runtime_mcp_from_opencode(
    opencode_config_path: Path,
    runtime_mcp_path: Path,
    *,
    dynamic_overlay_path: Path | None = None,
) -> bool:
    """Sync runtime .mcp.json from opencode.json MCP section.

    Returns True when sync succeeded (including empty MCP map), else False.
    """
    if not opencode_config_path.exists():
        return False

    try:
        raw = json.loads(opencode_config_path.read_text())
    except Exception:
        return False

    source_map = raw.get("mcp")
    if not isinstance(source_map, dict):
        # Explicitly keep runtime map empty if no MCP section is defined.
        runtime_mcp_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_mcp_path.write_text('{"mcpServers": {}}\n')
        return True

    mcp_servers: dict[str, dict] = {}
    for name, cfg in source_map.items():
        if not isinstance(name, str) or not isinstance(cfg, dict):
            continue
        if cfg.get("enabled", True) is False:
            continue

        server: dict[str, object] = {}
        server_type = str(cfg.get("type") or "").strip().lower()
        if server_type == "remote" or "url" in cfg:
            url = cfg.get("url")
            if isinstance(url, str) and url.strip():
                server["url"] = url.strip()
        else:
            command = cfg.get("command")
            if isinstance(command, list) and command:
                command_parts = [str(part) for part in command if str(part).strip()]
                if command_parts:
                    server["command"] = command_parts[0]
                    if len(command_parts) > 1:
                        server["args"] = command_parts[1:]
            elif isinstance(command, str) and command.strip():
                server["command"] = command.strip()
                args = cfg.get("args")
                if isinstance(args, list) and args:
                    server["args"] = [str(part) for part in args if str(part).strip()]

        env = cfg.get("environment")
        if isinstance(env, dict) and env:
            server["env"] = {str(k): str(v) for k, v in env.items()}

        headers = cfg.get("headers")
        if isinstance(headers, dict) and headers:
            server["headers"] = {str(k): str(v) for k, v in headers.items()}

        if server:
            mcp_servers[name] = server

    if dynamic_overlay_path and dynamic_overlay_path.exists():
        try:
            overlay_raw = json.loads(dynamic_overlay_path.read_text())
            overlay_servers = overlay_raw.get("mcpServers", {})
            if isinstance(overlay_servers, dict):
                for name, cfg in overlay_servers.items():
                    if not isinstance(name, str) or not isinstance(cfg, dict):
                        continue
                    if cfg.get("enabled", True) is False or cfg.get("disabled", False) is True:
                        mcp_servers.pop(name, None)
                        continue
                    merged_cfg = {k: v for k, v in cfg.items() if k not in {"enabled", "disabled"}}
                    if merged_cfg:
                        mcp_servers[name] = merged_cfg
        except Exception:
            # Overlay is optional; invalid overlay must not block startup.
            pass

    payload = {"mcpServers": dict(sorted(mcp_servers.items()))}
    runtime_mcp_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_mcp_path.write_text(json.dumps(payload, indent=2) + "\n")
    return True


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
