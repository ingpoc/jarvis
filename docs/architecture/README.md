# Architecture Index

Enforced rules and structural patterns.

| Document | Purpose | Enforcement |
|----------|---------|-------------|
| [layers.md](layers.md) | Dependency direction | Linter |
| [taste-invariants.md](taste-invariants.md) | Style rules | Linter |

## Architecture Layers

```
Types → Config → Repo → Service → Runtime → UI
                    ↑
              Providers (cross-cutting)
```

Code can only depend "forward" through layers.

## Taste Invariants

| Rule | Tool |
|------|------|
| WebSocket message format | `jarvis_api_lint.py` |
| Structured logging | (TODO) |
| Naming conventions | (TODO) |

## Adding Rules

1. Identify pattern (good or bad)
2. Write invariant in `taste-invariants.md`
3. Create/enhance linter with remediation message
4. Add to CI

## Key Insight

> "Constraints are what allows speed without decay."
