# Claude Code Capabilities (Built-In First)

Repository: `anthropics/claude-code` (DeepWiki)

## Core Built-Ins To Use Before Custom Logic

| Area | Built-in capability | Practical use for Jarvis |
|------|----------------------|--------------------------|
| Pre/post interception | Hooks (`PreToolUse`, `PostToolUse`, etc.) | Validate, block, rewrite inputs, add context |
| Permission control | Tool permissions + deny lists | Deterministic gating of risky tools |
| Sandbox | Bash sandbox mode | Isolate command execution |
| Reusable workflows | Skills | Progressive-load structured workflows |
| Extensibility | Plugins | Bundle commands/agents/skills/hooks |
| Tool ecosystem | MCP integration + search/discovery | Use external capabilities without bespoke integration |
| Context management | Auto compaction + `/compact` | Prevent context overflow drift |
| Session continuity | Session manager (resume/fork/tag) | Reliable long-running and branched work |
| Multi-agent | Agent teams/events | Structured review/debate workflows |

## Deterministic vs Advisory

| Type | Mechanism |
|------|-----------|
| Deterministic | Permissions, deny/disallowed tools, hook decisions, sandbox settings |
| Advisory | `CLAUDE.md`, prompt/system guidance, skill narrative instructions |

## Important Limits

1. Prompt-only policy is not enforcement.
2. Hooks run with timeout constraints; keep them fast and deterministic.
3. Agent teams are powerful but can become token-heavy if overused.
4. Use tool discovery/search to avoid hidden-capability underutilization.

## Recommended Optimization Order

1. Add deterministic gates first (permissions, disallowed tools, hook rules).
2. Add tool-discovery and fallback hooks for known failure paths.
3. Encode repeated multi-step workflows as skills.
4. Use plugins only for reusable cross-project packages.
5. Keep `CLAUDE.md` as a concise table-of-contents, not a giant manual.
