# Agent-First Operations

Core philosophy: Humans steer, agents execute.

---

## The Shift

| Traditional | Agent-First |
|-------------|-------------|
| Engineers write code | Engineers design environments |
| Code review blocks | Corrections are cheap |
| Documentation in wikis | Documentation in repo |
| Architecture "later" | Architecture prerequisite |
| Manual cleanup | Encoded cleanup rules |

---

## Human Role

| Task | Description |
|------|-------------|
| **Specify intent** | What should happen, not how |
| **Design environments** | Tools, abstractions, feedback loops |
| **Encode taste** | Capture once, enforce continuously |
| **Validate outcomes** | Did it work? |
| **Escalate judgment** | Only when needed |

## Agent Role

| Task | Description |
|------|-------------|
| **Execute intent** | Write code, tests, docs |
| **Self-verify** | Run tests, check outcomes |
| **Iterate** | Fix failures, improve |
| **Escalate blockers** | When stuck |

---

## Environment Design

When agent fails, ask:

| Question | Action |
|----------|--------|
| What capability is missing? | Add tool/abstraction |
| Is it legible to agent? | Document in repo |
| Is it enforceable? | Add linter/test |
| Is the environment specified? | Add structure |

**Not**: "Try harder"

---

## The Constraint

> "0 lines of manually-written code"

This forces building what's necessary for velocity by orders of magnitude.

---

## Signs of Underspecified Environment

| Symptom | Fix |
|---------|-----|
| Agent stuck repeatedly | Add capability |
| Wrong patterns repeated | Encode taste rule |
| Context not found | Move to repo |
| Tests always fail | Fix environment, not agent |

---

## Progressive Disclosure

```
CLAUDE.md (100 lines)
    │
    ├── docs/principles/     # Philosophy
    ├── docs/workflow/       # Research
    ├── docs/architecture/   # Rules
    └── docs/jarvis/         # Project-specific
```

Agent starts small, dives deeper as needed.

---

## Key Insight

> "Building software still demands discipline, but the discipline shows up more in the scaffolding rather than the code."
