# Jarvis Autonomous Evolution

## Purpose

Define how Jarvis updates its own workflow/docs without bloating always-on context.

## Contract

1. Jarvis executes delegated work autonomously (workflow, subagents, tools, worktrees, containers).
2. After non-trivial implementation or failure->fix, Jarvis updates `docs/` with the learned procedure.
3. `AGENTS.md` stays compressed:
   - keep only stable high-frequency rules and trigger/index pointers
   - move detailed steps and rationale to `docs/workflow/*.md`
4. Runtime visibility (`Workspace` / `MCP` / `Skills` / `Tools`) must be runtime-derived from OpenCode discovery, not hardcoded lists.

## Progressive Loading Rule

Load the minimum detail required for the current task:

- Start with `AGENTS.md` trigger/index lines.
- Load only the directly relevant workflow doc(s).
- Load deeper references only when blocked or when higher confidence is required.

## Update Loop

1. Detect repeated pattern (same class of task or failure appears again).
2. Add/refresh one workflow doc under `docs/workflow/`.
3. Add one concise trigger pointer in `AGENTS.md` (if truly recurrent).
4. Keep examples deterministic and implementation-oriented.
5. Validate docs (`python3 scripts/agent_docs_lint.py`).

## Ownership

- Human-managed immutable runtime config: `~/.jarvis/system/*`
- Jarvis-managed evolving workflow: `~/.jarvis/runtime_workflow/*`
- Execution outputs: `~/.jarvis/workspaces/*`

## Success Criteria

- New sessions can discover the right doc from `AGENTS.md` quickly.
- No long procedural blocks inside `AGENTS.md`.
- Runtime tabs reflect what OpenCode actually discovers at runtime.
