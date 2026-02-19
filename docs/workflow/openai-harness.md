# OpenAI Harness Engineering (Distilled)

**Source**: [OpenAI Blog - Harness Engineering](https://openai.com/index/harness-engineering/) (Feb 11, 2026 — Ryan Lopopolo, OpenAI)

**TL;DR**: 5 months, 0 lines of manual code, ~1M lines generated, 1,500 PRs, 3 → 7 engineers. Throughput *increased* as team grew (not just maintained).

---

## Core Philosophy

| Principle | Meaning |
|-----------|---------|
| **Humans steer. Agents execute.** | No manual code. Everything by Codex. |
| **Environment > Capability** | Early slowness was underspecified environment, not agent limitation |
| **Repository as system of record** | If not in repo, doesn't exist to agent |
| **Enforce invariants, not implementations** | Boundaries enforced, implementation free |

---

## Key Quote

> "What capability is missing, and how do we make it both legible and enforceable for the agent?"

This is the primary engineering question. Never "try harder." Always add capability.

---

## What Worked

### 1. Progressive Disclosure

| Anti-Pattern | Pattern |
|--------------|---------|
| 1000-page instruction manual | Short AGENTS.md (~100 lines) as table of contents |
| Everything "important" | Pointers to deeper sources |
| Monolithic manual | Structured `docs/` directory |

**Why**: Giant instruction files crowd out task, code, docs. Agent misses constraints or optimizes wrong ones.

### 2. Architecture Layers

```
Types → Config → Repo → Service → Runtime → UI
                    ↑
              Providers (cross-cutting)
```

- Fixed layers per domain
- Strict dependency direction
- Providers enter through single interface
- Enforced mechanically via custom linters

**Key insight**: "Architecture you postpone until 100s of engineers is prerequisite with agents."

### 3. Taste Invariants (Mechanical Rules)

| Rule | Enforcement |
|------|-------------|
| Structured logging | Custom linter |
| Naming conventions | Custom linter |
| File size limits | Custom linter |
| Boundary validation | Custom linter |

**Critical**: Error messages include remediation instructions → agent self-fixes.

### 4. Observability for Agents

| Capability | Tool |
|------------|------|
| UI inspection | Chrome DevTools Protocol |
| Log queries | LogQL |
| Metric queries | PromQL |
| Per-worktree isolation | Ephemeral observability |

**Enables prompts like**: "Ensure startup < 800ms" or "No span exceeds 2s in critical journeys"

### 5. Ralph Wiggum Loop (Agent Self-Review)

Codex reviews its own PRs in a loop until all agent reviewers are satisfied. Humans may review but aren't required to. All review effort pushed to agent-to-agent.

```
Codex opens PR → requests agent reviews (local + cloud) → responds to feedback → loops until satisfied → merges
```

**Key**: Humans interact "almost entirely through prompts." No copy-pasting context into CLI — agent uses standard tools directly (`gh`, local scripts, repository-embedded skills).

### 6. Repository-Embedded Skills

Codex gathers context via skills embedded in the repo — not by humans providing context manually. This is the mechanism that makes "repository as system of record" work in practice.

**Directly validates**: Our `.claude/skills/` directory approach and trigger-based progressive disclosure.

### 7. Garbage Collection (Not Bursts)

| Before | After |
|--------|-------|
| 20% of week cleaning "AI slop" | Recurring cleanup tasks |
| Manual refactoring | Golden principles encoded |
| Debt compounds | Debt paid continuously |

**Pattern**: Human taste captured once, enforced continuously.

---

## What Didn't Work

| Anti-Pattern | Lesson |
|--------------|--------|
| Human-written code | Breaks the model, creates inconsistency |
| External context (Slack, Notion) | Invisible to agent |
| Prescriptive prompting | Restricts problem-solving |
| Blocking merge gates | Corrections cheap, waiting expensive |
| Manual cleanup | Doesn't scale |

---

## Autonomy Threshold

**Current capability** (single prompt):

1. Validate codebase state
2. Reproduce bug
3. Record failure video
4. Implement fix
5. Validate fix
6. Record resolution video
7. Open PR
8. Respond to feedback
9. Detect/remediate build failures
10. Escalate only when judgment required
11. Merge

**Note**: Depends on specific structure + tooling, doesn't generalize without investment.

---

## Key Metrics

| Metric | Value |
|--------|-------|
| Time to ~1M lines | 5 months |
| Engineers | 3 → 7 |
| PRs merged | ~1,500 |
| Throughput | 3.5 PRs/engineer/day |
| PR lifespan | Short (hours not days) |
| Single task duration | Up to 6 hours (runs overnight) |

---

## Apply to Jarvis

| From OpenAI | Jarvis Implementation | Status |
|-------------|----------------------|--------|
| Short AGENTS.md | CLAUDE.md 72 lines, 3-question gate enforced | ✅ Done |
| Architecture layers | Not formalized | ❌ Missing |
| Custom linters | `jarvis_api_lint.py` | ✅ Started |
| Observability | Logs exist, not queryable | ⚠️ Partial |
| Garbage collection | No recurring cleanup | ❌ Missing |
| Repo as record | Some context external | ⚠️ Partial |
| Repository-embedded skills | `.claude/skills/` — research-evaluator, claude-md-creator etc. | ✅ Done |
| Ralph Wiggum Loop | Pre-commit hook wired, no agent self-review loop on PRs yet | ⚠️ Partial |
| Agent-to-agent review | research-evaluator Advocate/Skeptic team | ✅ Started |

---

## Quotes

> "The primary job of our engineering team became enabling the agents to do useful work."

> "When something failed, the fix was almost never 'try harder.'"

> "What capability is missing, and how do we make it both legible and enforceable for the agent?"

> "Our most difficult challenges now center on designing environments, feedback loops, and control systems."

---

## Integration Notes

**Tier**: 2 (Tested)
**Created**: 2026-02-17
**Sessions Used**: 3
**Additional source**: [Anthropic — Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (Feb 2026)
**Outcomes**:

- Session 1: Created docs structure based on progressive disclosure
- Session 2: Shortened CLAUDE.md/AGENTS.md to ~125 lines
- Session 3: CLAUDE.md/AGENTS.md trimmed to 59→75 lines. 3-question gate rule added to Principles. `claude-md-creator` skill enforcement updated. `research-evaluator` skill built (replaces `agent-context-repo`).

### Reasoning

1. **What problem does this solve?** Context management, architecture drift, agent effectiveness
2. **Do we have this problem?** Yes - CLAUDE.md was 192 lines, no architecture layers
3. **Is this the best solution we've seen?** Yes - only real-world data at this scale
4. **Can we verify it works?** Yes - token usage, agent effectiveness measurable
5. **Does it align with existing principles?** Yes - matches agent-first, progressive disclosure

### Promotion Status

- [x] Tier 1 → Tier 2 criteria met (2+ sessions, improved outcomes)
- [ ] Tier 2 → Tier 3 (needs 5+ sessions, consensus)

**Pending**: Architecture layers not yet implemented, garbage collection not set up
