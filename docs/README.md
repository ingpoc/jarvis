# Jarvis Documentation

Progressive disclosure: Start here, dive deeper as needed.

## Quick Navigation

| Need | Document | Lines |
|------|----------|-------|
| How to work in this repo | [../CLAUDE.md](../CLAUDE.md) | ~100 |
| Core principles | [principles/README.md](principles/README.md) | Index |
| Research distillations | [workflow/README.md](workflow/README.md) | Index |
| Architecture rules | [architecture/README.md](architecture/README.md) | Index |
| Jarvis-specific | [jarvis/README.md](jarvis/README.md) | Index |

## Structure

```
docs/
├── README.md              # This file - master index
├── principles/            # Core philosophy (timeless)
│   ├── agent-first.md     # Humans steer, agents execute
│   ├── progressive-disclosure.md  # Map not manual
│   ├── determinism.md     # Code > LLM judgment
│   └── token-efficiency.md # Resource management
├── workflow/              # Research distillations (updated)
│   ├── openai-harness.md  # OpenAI's 0-code experiment
│   ├── verification-loops.md # Self-testing patterns
│   └── garbage-collection.md # Tech debt management
├── architecture/          # Enforced rules (mechanical)
│   ├── layers.md          # Layered architecture
│   ├── taste-invariants.md # Style rules
│   └── idle-introspection-framework.md # Local MLX model, idle-time learning loop
└── jarvis/                # Project-specific (evolving)
    ├── conventions.md     # Container, git, tools
    ├── debugging.md       # Common issues
    └── api-reference.md   # WebSocket API
```

## Reading Order

1. **New to project**: CLAUDE.md → principles/agent-first.md → jarvis/conventions.md
2. **Debugging issue**: jarvis/debugging.md → architecture/taste-invariants.md
3. **Research background**: workflow/openai-harness.md → principles/progressive-disclosure.md

## Maintenance

| Task | Frequency | Owner |
|------|-----------|-------|
| Validate links | Weekly | `scripts/validate-docs.py` |
| Garbage collect | Daily | `scripts/doc-gardener.py` |
| Update research | As needed | Manual |

## Sources

| Source | Key Insight | Distilled In |
|--------|-------------|--------------|
| [OpenAI Harness Engineering](https://openai.com/index/harness-engineering/) | 0 manual code, environment > capability | workflow/openai-harness.md |
| [Anthropic Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Feature lists, verification loops | workflow/verification-loops.md |
| [Boris Cherny Claude Workflow](https://talent500.com/blog/claude-code-workflow-redefining-software-development/) | 5 specialized agents, CLAUDE.md as error repo | workflow/multi-agent.md |
