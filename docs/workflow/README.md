# Workflow Index

Distilled research articles and patterns.

| Article | Source | Key Insight |
|---------|--------|-------------|
| [openai-harness.md](openai-harness.md) | OpenAI Blog | 0 manual code, environment > capability |
| [openai-unlocking-codex-harness.md](openai-unlocking-codex-harness.md) | OpenAI Blog | Thread/turn/item protocol model; adapt loop interfaces, not runtime-specific wiring |
| [openai-unrolling-codex-agent-loop.md](openai-unrolling-codex-agent-loop.md) | OpenAI Blog | Explicit agent loop design (role/instructions/tools/input + self-correction stages) |
| [langchain-improving-deep-agents-harness-engineering.md](langchain-improving-deep-agents-harness-engineering.md) | X post + LangChain Blog | Trace-driven harness iteration + self-verification loop improved benchmark score with fixed model |
| [vercel-agents-md.md](vercel-agents-md.md) | Vercel | Passive context beats skills, 100% vs 79% |
| [context-learning-loop.md](context-learning-loop.md) | Internal proposal | Traces → hooks → rules; verdict: Adapt (use existing skills, add hook enforcement) |
| [draw-io-diagram-generation.md](draw-io-diagram-generation.md) | Process guide | Diagram generation workflow with draw.io (Mermaid/XML/CSV) |
| [local-models-integration.md](local-models-integration.md) | Internal — updated 2026-02-21 | OpenCode-only runtime policy, free-model pinning, and WS/A2A routing rules |
| [openclaw-integration.md](openclaw-integration.md) | OpenClaw docs + DeepWiki + live validation (2026-02-20) | Standalone OpenClaw operations: sandbox/pairing/auth/slack/gateway reliability |
| [openclaw-jarvis-integration.md](openclaw-jarvis-integration.md) | OpenClaw docs + DeepWiki + live validation (2026-02-20) | Jarvis delegation contract: bridge ownership map, non-blocking task flow, and workspace rule sync |
| [opencode-parallel-worktrees.md](opencode-parallel-worktrees.md) | Claude Code docs + OpenCode docs + DeepWiki (2026-02-20) | Manager + parallel OpenCode subagents with per-role containerized git worktrees, deterministic gates, and PR/issue handoff |
| [jarvis-autonomous-evolution.md](jarvis-autonomous-evolution.md) | Internal runtime contract | Jarvis updates docs/workflow continuously while keeping AGENTS compressed and trigger-based |
| [harness-governance.md](harness-governance.md) | Internal policy | What is always-on vs progressive vs enforced, and cross-runtime (Claude + Codex) rules |
| [harness-purpose-map.md](harness-purpose-map.md) | Internal policy | Why each enforced harness item exists and when to remove it |
| [social-post-intake.md](social-post-intake.md) | Internal process | Fast extraction cascade for X/LinkedIn/Threads research links |
| [github-account-isolation.md](github-account-isolation.md) | Internal ops (2026-02-21) | Two-account gh isolation: ingpoc (personal) vs openclaw-gurusharan (Jarvis), via separate GH_CONFIG_DIR + direnv |

## Skipped Evaluations

| Article | Source | Why skipped |
|---------|--------|-------------|
| [skipped/openai-in-house-data-agent.md](skipped/openai-in-house-data-agent.md) | OpenAI Blog | Strong case study but low transferability/ROI at Jarvis's current scale |

## Reading Order

1. **openai-harness.md** - Core philosophy and patterns
2. **openai-unrolling-codex-agent-loop.md** - Explicit loop design
3. **openai-unlocking-codex-harness.md** - Protocol and runtime shape
4. **langchain-improving-deep-agents-harness-engineering.md** - Trace-driven optimization loop
5. **jarvis-autonomous-evolution.md** - How Jarvis self-updates docs/workflow with progressive loading

## Contribution

When adding new research:

1. Create `article-name.md` in this directory
2. Use `research-evaluator` output format (score, verdict, claims, what to take/modify)
3. Add `**Evaluation**: research-evaluator` for adopt/adapt distillations (non-skipped)
4. Include `## Memory Promotion` with explicit `**Memory Action**:` in adopt/adapt distillations
5. Update this index
6. Keep under 200 lines (distilled, not copied)
