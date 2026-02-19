# Codex Capabilities (Built-In First)

Repository: `openai/codex` (DeepWiki)

## Core Built-Ins To Use Before Custom Logic

| Area | Built-in capability | Practical use for Jarvis |
|------|----------------------|--------------------------|
| Execution safety | `approval_policy` | Control when user approval is required |
| Sandboxing | `sandbox_mode` (`read-only`, `workspace-write`, etc.) | Restrict command blast radius |
| Command governance | Exec policy prefix rules | Enforce allow/prompt/forbid patterns |
| Session continuity | Rollout persistence + resume/fork | Keep long-running work stateful |
| Tool orchestration | Central tool orchestrator | Unified approval + sandbox flow |
| MCP integration | MCP server config in `config.toml` | Use external tools without custom glue |
| Lifecycle hooks | `AfterAgent`/`AfterToolUse` style hooks | Post-event telemetry/automation |

## Important Limits

1. No direct `PreToolUse` equivalent like Claude Code hooks.
2. Enforcement is strongest via config/policy (approval, sandbox, execpolicy), not prompt text alone.
3. For pre-execution behavior shaping, use policy + instructions (`AGENTS.md`) rather than expecting callback interception.

## Deterministic vs Advisory

| Type | Mechanism |
|------|-----------|
| Deterministic | Approval policy, sandbox policy, exec policy rules |
| Advisory | `AGENTS.md` instructions, prompt guidance |

## Recommended Optimization Order

1. Tighten `approval_policy` and `sandbox_mode`.
2. Add/maintain exec policy prefix rules for risky command classes.
3. Ensure MCP server inventory is complete for specialized tasks.
4. Keep `AGENTS.md` concise and high-signal for non-mechanical behavior.
5. Add custom extensions only after identifying a concrete unsupported gap.
