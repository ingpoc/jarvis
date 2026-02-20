---
name: jarvis-coder
description: Delegate coding, refactor, debugging, and implementation tasks to Jarvis through the jarvis_delegate_task tool. Use this when the user asks for real code changes, repository edits, or multi-step coding execution.
user-invocable: true
command-dispatch: tool
command-tool: jarvis_delegate_task
command-arg-mode: raw
metadata: {"openclaw":{"emoji":"🤖","homepage":"https://github.com/openclaw/openclaw","requires":{"config":["plugins.entries.jarvis-bridge.enabled"]}}}
---

# Jarvis Coder Bridge

Use `jarvis_delegate_task` for coding-focused tasks that should execute in Jarvis.

## Routing rules

1. If the user asks for coding/build/refactor/debug/implementation work, call `jarvis_delegate_task` instead of local ad-hoc execution.
2. Keep the delegated task explicit and implementation-focused; prepend `OPENCODE ONLY.` for coding delegations.
3. For multi-step work, split into atomic tasks with explicit completion markers (`DONE_STEP1`, `DONE_STEP2`, ...).
4. Prefer non-blocking delegation first; use bounded `wait=true` only for short verification steps.
5. After tool completion, summarize Jarvis output clearly and include status.

## Direct invocation

- `/jarvis-coder <task>` dispatches directly to `jarvis_delegate_task` without model mediation.
- `/jarvis <task>` is also available via plugin command.
