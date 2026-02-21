# Jarvis Documentation

Progressive disclosure: Start here, dive deeper as needed.

## Quick Navigation

| Need | Document | Lines |
|------|----------|-------|
| How to work in this repo | [../AGENTS.md](../AGENTS.md) | compressed trigger/index |
| Core principles | [principles/README.md](principles/README.md) | Index |
| Platform capabilities | [capabilities/README.md](capabilities/README.md) | Index |
| Research distillations | [workflow/README.md](workflow/README.md) | Index |
| Long-term continuity memory | [../memory/README.md](../memory/README.md) | Contract |
| Architecture rules | [architecture/README.md](architecture/README.md) | Index |
| Jarvis-specific | [jarvis/README.md](jarvis/README.md) | Index |

## Structure

```
docs/
├── README.md              # This file - master index
├── capabilities/          # Platform capability maps (use-before-build)
│   ├── checklist.md       # Proposal gate before adding new harness logic
│   ├── codex.md           # Codex built-ins and limits
│   └── claude-code.md     # Claude Code built-ins and enforcement model
├── principles/            # Core philosophy (timeless)
│   ├── agent-first.md     # Humans steer, agents execute
│   ├── progressive-disclosure.md  # Map not manual
│   ├── determinism.md     # Code > LLM judgment
│   └── token-efficiency.md # Resource management
├── workflow/              # Research distillations (updated)
│   ├── openai-harness.md
│   ├── openclaw-integration.md
│   ├── openclaw-jarvis-integration.md
│   ├── opencode-parallel-worktrees.md
│   └── local-models-integration.md
├── architecture/          # Enforced rules (mechanical)
│   ├── layers.md          # Layered architecture
│   ├── taste-invariants.md # Style rules
│   └── idle-introspection-framework.md # Idle-time learning loop
└── jarvis/                # Project-specific (evolving)
    ├── conventions.md     # Container, git, tools
    ├── debugging.md       # Common issues
    └── api-reference.md   # WebSocket API
```

## Reading Order

1. **New to project**: AGENTS.md → principles/agent-first.md → jarvis/conventions.md
2. **Capability planning**: capabilities/README.md → capabilities/{platform}.md
3. **Debugging issue**: jarvis/debugging.md → jarvis/scripts.md
4. **OpenClaw operations**: workflow/openclaw-integration.md
5. **OpenClaw/Jarvis delegation**: workflow/openclaw-jarvis-integration.md → workflow/opencode-parallel-worktrees.md

## Maintenance

| Task | Frequency | Owner |
|------|-----------|-------|
| Sync docs with non-trivial code/behavior changes | Every implementation session | Required gate before completion |
| Validate docs references | Weekly | `python3 scripts/agent_docs_lint.py` |
| Garbage collect stale docs | Daily | Manual review |
| Update research | As needed | Manual |

## Sources

| Source | Key Insight | Distilled In |
|--------|-------------|--------------|
| [OpenAI Harness Engineering](https://openai.com/index/harness-engineering/) | Environment and process matter as much as model | workflow/openai-harness.md |
| [OpenClaw docs](https://docs.openclaw.ai/tools/plugin) | Gateway/channels/model/sandbox operations + plugin delegation | workflow/openclaw-integration.md, workflow/openclaw-jarvis-integration.md |
| [Claude Code worktrees guide](https://code.claude.com/docs/en/common-workflows#run-parallel-claude-code-sessions-with-git-worktrees) | Parallel execution via isolated worktrees | workflow/opencode-parallel-worktrees.md |
