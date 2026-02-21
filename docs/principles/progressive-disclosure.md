# Progressive Disclosure

Give agents a map, not a 1000-page manual.

---

## The Problem

| Issue | Cause |
|-------|-------|
| Agent misses constraints | Giant file crowds out task |
| Wrong optimization | Everything "important" |
| Stale rules | Manual rot |
| Drift | No mechanical checks |

---

## The Solution

```
Entry Point (CLAUDE.md ~100 lines)
         │
         ▼
    Table of Contents
         │
    ┌────┼────┬────────┐
    ▼    ▼    ▼        ▼
  docs/principles/
  docs/workflow/
  docs/architecture/
  docs/jarvis/
```

---

## Content Guidelines

| Level | Content | Size |
|-------|---------|------|
| **Entry** | Quick start, pointers | ~100 lines |
| **Index** | What's available, when to use | ~50 lines |
| **Detail** | Full content | Unlimited |

---

## Anti-Patterns

| Anti-Pattern | Problem |
|--------------|---------|
| One massive file | Agent loses task context |
| Everything marked important | Nothing important |
| External wikis | Invisible to agent |
| Unstructured docs | Can't validate |
| No ownership | No maintenance |

---

## Patterns

| Pattern | Benefit |
|---------|---------|
| Short entry file | Agent focuses on task |
| Pointers not copies | Single source of truth |
| Structured directory | Mechanical validation |
| Cross-links | Discoverability |
| Index files | Navigation |

---

## Validation

| Check | Tool |
|-------|------|
| Links and path references | `python3 scripts/agent_docs_lint.py` |
| Structure correctness | `python3 scripts/agent_docs_lint.py` |
| Freshness | Manual review in implementation sessions |

---

## Key Insight

> "Context is a scarce resource. A giant instruction file crowds out the task, the code, and the relevant docs."
