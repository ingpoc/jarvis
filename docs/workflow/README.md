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
