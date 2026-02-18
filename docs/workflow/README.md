# Workflow Index

Distilled research articles and patterns.

| Article | Source | Key Insight |
|---------|--------|-------------|
| [openai-harness.md](openai-harness.md) | OpenAI Blog | 0 manual code, environment > capability |
| [verification-loops.md](verification-loops.md) | Anthropic | Feature lists, self-verification |
| [garbage-collection.md](garbage-collection.md) | OpenAI | Continuous debt paydown |
| [vercel-agents-md.md](vercel-agents-md.md) | Vercel | Passive context beats skills, 100% vs 79% |
| [apple-container.md](apple-container.md) | Apple GitHub | Linux containers as VMs, XPC architecture |
| [context-learning-loop.md](context-learning-loop.md) | Internal proposal | Traces → hooks → rules; verdict: Adapt (use existing skills, add hook enforcement) |
| [draw-io-diagram-generation.md](draw-io-diagram-generation.md) | Process guide | Diagram generation workflow with draw.io (Mermaid/XML/CSV) |
| [apple-mlx-frameworks.md](apple-mlx-frameworks.md) | DeepWiki Research | MLX for local LLM inference, LM Studio for Claude SDK integration |
| [local-models-integration.md](local-models-integration.md) | Internal — debug sessions 2026-02-18 | `run_until_complete()` inside async silently breaks `switch_model`; `is_running` ≠ service available — use `is_api_available()` for externally-started services; `load_model()` requires valid request body |

## Reading Order

1. **openai-harness.md** - Core philosophy and patterns
2. **verification-loops.md** - How to verify progress
3. **garbage-collection.md** - Managing technical debt

## Contribution

When adding new research:

1. Create `article-name.md` in this directory
2. Follow template: TL;DR → Principles → Patterns → Application
3. Update this index
4. Keep under 200 lines (distilled, not copied)
