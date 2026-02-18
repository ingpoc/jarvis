# Principles Index

Core philosophy for agent-first operations.

| Principle | Summary | When to Read |
|-----------|---------|--------------|
| [agent-first.md](agent-first.md) | Humans steer, agents execute | New to project |
| [progressive-disclosure.md](progressive-disclosure.md) | Map not manual | Writing CLAUDE.md |
| [determinism.md](determinism.md) | Code > LLM judgment | Verification |
| [token-efficiency.md](token-efficiency.md) | Context is scarce | Performance |

## Quick Reference

```
Agent-First:     Design environments, don't write code
Progressive:     Short entry (100 lines) → deep docs
Determinism:     Exit codes, not "I think"
Token-Efficient: Sandbox data, summarize results
```

## Application Order

1. **Before task**: Check progressive-disclosure for context strategy
2. **During task**: Use token-efficiency for data
3. **After task**: Apply determinism for verification
4. **Always**: Agent-first mindset
