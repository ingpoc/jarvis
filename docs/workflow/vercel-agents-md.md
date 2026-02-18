# Vercel: AGENTS.md vs Skills (Distilled)

**Source**: [Vercel Blog - AGENTS.md outperforms skills](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals) (Jan 2026)

**TL;DR**: Compressed 8KB docs index in AGENTS.md achieved 100% pass rate. Skills maxed at 79%. Passive context beats active retrieval for framework knowledge.

---

## Core Finding

| Approach | Pass Rate | vs Baseline |
|----------|-----------|-------------|
| Baseline (no docs) | 53% | — |
| Skill (default) | 53% | +0pp |
| Skill + explicit instructions | 79% | +26pp |
| **AGENTS.md docs index** | **100%** | **+47pp** |

---

## Why Skills Failed

| Issue | Data |
|-------|------|
| Not triggered | 56% of cases, skill never invoked |
| Wording fragile | "MUST invoke" vs "explore first" = different outcomes |
| Ordering problems | Docs-first missed project context; explore-first better |

**Key insight**: Agent having access ≠ agent using it. Decision points create failure modes.

---

## Why Passive Context Won

| Factor | AGENTS.md Advantage |
|--------|---------------------|
| No decision point | Agent doesn't choose whether to look up |
| Consistent availability | In system prompt every turn |
| No ordering issues | No "read docs first vs explore project" conflict |

---

## The Compression Pattern

| Metric | Value |
|--------|-------|
| Initial injection | ~40KB |
| Compressed | 8KB (80% reduction) |
| Pass rate | Same (100%) |

### Minified Index Format

```
[Next.js Docs Index]|root: ./.next-docs
|IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning
|01-app/01-getting-started:{01-installation.mdx,02-project-structure.mdx,...}
|01-app/02-building-your-application/01-routing:{01-defining-routes.mdx,...}
```

**Pattern**: Index points to retrievable files, not full content.

---

## Key Instruction

> "Prefer retrieval-led reasoning over pre-training-led reasoning for any [framework] tasks."

This explicitly tells agents to consult docs rather than rely on potentially outdated training data.

---

## Anti-Patterns

| Anti-Pattern | Problem |
|--------------|---------|
| "You MUST invoke the skill" | Anchors on docs, misses project context |
| Skill without instructions | Agent ignores it (0% improvement) |
| Full docs in AGENTS.md | Context bloat (40KB unnecessary) |

---

## Practical Recommendations

| Recommendation | Rationale |
|----------------|-----------|
| Don't wait for skills to improve | Results matter now |
| Compress aggressively | Index works as well as full docs |
| Test with evals | Target APIs not in training data |
| Design for retrieval | Structure docs for random access |

---

## Skills vs AGENTS.md: When to Use Each

| Use Case | Approach |
|----------|----------|
| General framework knowledge | **AGENTS.md** (passive context) |
| Version-specific docs | **AGENTS.md** (compressed index) |
| Vertical workflows (upgrade, migrate) | **Skills** (explicit trigger) |
| User-triggered actions | **Skills** (on-demand) |

**Pattern**: Passive for horizontal (always-needed), skills for vertical (user-initiated).

---

## Apply to Jarvis

| From Vercel | Jarvis Status |
|-------------|---------------|
| Short AGENTS.md | ✅ CLAUDE.md ~100 lines |
| Compressed index | ⚠️ Not yet - could add for Python/Jarvis APIs |
| Retrieval-led reasoning instruction | ❌ Missing |
| Evals for out-of-training APIs | ❌ Missing |

### Potential Application

For Jarvis-specific APIs not in model training:

```markdown
[Jarvis API Index]|root: ./docs/jarvis/api
|IMPORTANT: Prefer retrieval-led reasoning for Jarvis daemon APIs
|ws-server:{connect,actions,message-format}
|orchestrator:{routing,tools,agents}
```

---

## Quotes

> "The 'dumb' approach (a static markdown file) outperformed the more sophisticated skill-based retrieval."

> "If small wording tweaks produce large behavioral swings, the approach feels brittle for production use."

> "The goal is to shift agents from pre-training-led reasoning to retrieval-led reasoning."

---

## Integration Notes

**Tier**: 1 (Reference)
**Created**: 2026-02-17
**Sessions Used**: 0
**Outcomes**: (pending validation)

### Reasoning

1. **What problem does this solve?** Agent not using available documentation, framework knowledge gaps
2. **Do we have this problem?** Partially - we use AGENTS.md but no compressed index pattern
3. **Is this the best solution we've seen?** Yes - only empirical data comparing approaches
4. **Can we verify it works?** Yes - could test with Jarvis-specific APIs
5. **Does it align with existing principles?** Yes - matches progressive disclosure, token efficiency

### Promotion Status

- [ ] Tier 1 → Tier 2 (needs 2+ sessions, validated improvement)
- [ ] Tier 2 → Tier 3 (needs 5+ sessions, proven essential)

**Pending**: Test compressed index pattern for Jarvis APIs, validate retrieval-led instruction effectiveness
