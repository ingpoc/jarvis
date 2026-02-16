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

## Scope Routing (Jarvis)
- Jarvis-core implementation policy stays in this repo (`AGENTS.md`, `ROADMAP.md`).
- `JARVIS.md` is only for non-core target repos where Jarvis executes user tasks.

## Trace Requirement
Use global Context Graph workflow from:
- `~/.codex/rules/WORKFLOW.md`
- `~/.codex/rules/TOOLS-POLICY.md`

For this repo, non-trivial fixes are not done unless trace query/store/update workflow is followed.
