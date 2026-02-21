# Capability Maps

Use this folder before adding new harness logic. Goal: use built-in capabilities first, then add custom logic only for gaps.

## When To Load

| Need | Document |
|------|----------|
| Optimize Codex behavior/policy | `codex.md` |
| Optimize Claude Code harness | `claude-code.md` |
| Evaluate a new optimization idea | `checklist.md` |

## Decision Rule

1. Check platform capability map.
2. If built-in capability exists, configure/use it.
3. If no built-in covers requirement, implement custom extension.
4. Run `checklist.md` before implementation.
5. Record the gap and decision in context graph.

## Source

Derived from DeepWiki repository docs:

- `openai/codex`
- `anthropics/claude-code`
