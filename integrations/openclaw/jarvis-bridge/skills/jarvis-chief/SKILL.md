---
name: jarvis-chief
description: Delegate execution tasks to Jarvis through jarvis_delegate_task when the work is implementation-heavy or long-running. Use this for coding, deep analysis, repo operations, and structured execution plans.
user-invocable: true
command-dispatch: tool
command-tool: jarvis_delegate_task
command-arg-mode: raw
metadata: {"openclaw":{"emoji":"🧠","homepage":"https://github.com/openclaw/openclaw","requires":{"config":["plugins.entries.jarvis-bridge.enabled"]}}}
---

# Jarvis Chief

Use `jarvis_delegate_task` to offload execution-heavy tasks to Jarvis.

## Routing rules

1. Use OpenClaw-native research tools first for discovery (Perplexity, Browser, Context7).
2. Delegate to Jarvis when work needs implementation depth, multi-step execution, or repository changes.
3. Include a concrete objective and expected output in the delegated task.
4. After completion, update memory and research/work ledgers to avoid repeated loops.

## Direct invocation

- `/jarvis-chief <task>` dispatches directly to `jarvis_delegate_task`.
- `/jarvis <task>` is available as a short command.
