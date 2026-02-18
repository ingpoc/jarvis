# AGENTS.md

## Scope

This file contains only Jarvis-core, repository-specific rules.
Global operating policy lives in `~/.codex/AGENTS.md` and `~/.codex/rules/*`.

## Context Contract

- Apply global baseline first from `~/.codex/AGENTS.md`.
- Use this file only for rules specific to this repository.
- Do not duplicate global policy text here; add short references when needed.

## Mission (Jarvis Core)

Improve Jarvis reliability and capability while keeping failures explicit and diagnosable.

## Jarvis-Core Mandatory Rules

- Startup checks are fail-fast only:
  - If daemon launch env cannot be loaded, abort startup with explicit `FATAL` log.
  - Do not add fallback paths that mask broken launch/permissions state.
- Launchd compatibility:
  - Daemon launch context must not depend on reading project files under `Documents` at runtime.
  - Required launch env must be sourced from `~/.jarvis` artifacts generated at startup.
- Port cleanup safety:
  - Kill only listeners on service ports (`-sTCP:LISTEN`), never all processes touching the port.
- Launchctl validation:
  - Do not trust a single captured PID during bootstrap (PID can churn).
  - Validate via launchctl service state + port readiness, then refresh/write current PID.

## Verification Standard (Jarvis Core)

After startup or daemon lifecycle changes:

- `stop-jarvis.sh` then `start-jarvis.sh` must pass with clean logs.
- Confirm daemon WebSocket port is listening.
- Confirm menu bar process is running and connected.

## WebSocket API Rules (CRITICAL)

- **Message format**: All WebSocket messages MUST use `data` wrapper:
  - Correct: `{"action": "chat", "data": {"message": "..."}, "id": "..."}`
  - Wrong: `{"action": "chat", "message": "..."}` (returns "Missing 'message'" error)
- **Actions requiring data wrapper**: chat, run_task, message, read_file, git_status, build_project, run_tests
- **Actions exempt**: get_status, get_timeline, get_capabilities, get_containers
- **Run lint before testing**: `python3 scripts/jarvis_api_lint.py`
- **Debug locations**: See `.claude/rules/jarvis-debugging.md` for daemon log paths and restart sequences.

## Scope Routing (Jarvis)

- Jarvis-core implementation policy stays in this repo (`AGENTS.md`, `.agent/*`).
- `JARVIS.md` is only for non-core target repos where Jarvis executes user tasks.

## Harness Governance (.agent)

- `.agent/ARCHITECTURE.md` contains stable, agreed/approved decisions only (no in-flight chatter).
- `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md` contains open items only.
- Promotion rule:
  - when an item is `APPROVED`, remove it from inflight and add the stable outcome to `.agent/ARCHITECTURE.md`.
- Progressive disclosure is mandatory:
  - keep stable docs short; keep churn in inflight.
- Any change touching `.agent/*` must keep governance lint green:
  - `python3 scripts/agent_docs_lint.py`

## Trace Requirement

Use global Context Graph workflow from:

- `~/.codex/rules/WORKFLOW.md`
- `~/.codex/rules/TOOLS-POLICY.md`

For this repo, non-trivial fixes are not done unless trace query/store/update workflow is followed.
