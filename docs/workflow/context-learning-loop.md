# Context Graph Learning Loop (Distilled)

**Source**: Internal proposal (context-learning-loop framework)
**TL;DR**: Formalize context graph from passive trace storage into an active learning system with mandatory precedent lookup, pattern extraction, and auto-generated rules.

---

## Opinion

**Verdict**: Adopt (with adaptations)
**Confidence**: High
**Reasoning**: The core feedback loop is sound and validated by 76 real traces. After auditing the existing skills: `learning-loop` was deleted (broken scripts, no MCP connection, never triggered); `introspect` was rewritten to be honest — the agent calls MCP directly, scripts are templates only, session-deduped thresholds from proposal are now incorporated. The Vercel article supports this: skills failed 56% of the time when not explicitly triggered; `learning-loop` was never triggered. The proposal's hook-enforcement for mandatory precedent lookup is the right model.

### Claims Analysis

| Claim | Agree? | Evidence | Confidence |
|-------|--------|----------|------------|
| 76 traces exist, no pattern extraction | Yes | `context_list_categories` shows 76 traces across 12 categories, no automation found | H |
| Mandatory precedent lookup not enforced | Yes | CLAUDE.md has trust thresholds as rules, no hook/script enforces them | H |
| Unicode regex has 3+ occurrences → lint warranted | Partially | 3 error traces confirmed, but all from stock-extraction JS project, not Jarvis | M |
| WS format errors → need auto-generated lint | No | trace_bc612147b123: `jarvis_api_lint.py` already created manually | H |
| Auto-generate CLAUDE.md at 5+ occurrences | Disagree | CLAUDE.md edits require human review; automation risks polluting rules with false patterns | H |
| Pattern clustering by semantic similarity is feasible | Partially | 76 traces spread across 12 categories — thin for clustering, cross-project contamination is real | M |
| Introspection agent is novel | No | `introspect` and `learning-loop` skills already exist in skill registry | H |

---

## What's Actually Novel (vs. Already Exists)

| Idea | Status |
|------|--------|
| Mandatory precedent lookup before decisions | Rule exists in CLAUDE.md, NOT mechanically enforced |
| 3+ occurrences → generate lint | NEW — good threshold, but needs project scoping |
| 5+ occurrences → CLAUDE.md update | NEW — but risky without human review gate |
| Introspection agent | `introspect` skill EXISTS but scripts are broken scaffolding |
| Pattern extraction from traces | `learning-loop` skill EXISTS but `extract-patterns.py` requires offline JSON export (no MCP) |
| WS format lint | ALREADY EXISTS (`jarvis_api_lint.py`) |

**On the existing skills**: Both `introspect` and `learning-loop` are manual workflow guides, not autonomous automation. `analyze-traces.sh` calls `claude mcp call` as a subprocess (won't work inside Claude Code session). `extract-patterns.py` needs pre-exported traces JSON — without it, finds nothing. `generate-rule.sh` produces a stub with `// WRONG // Bad pattern example` placeholders. The agent still does all the actual work manually.

**Genuine new value**: Occurrence thresholds (3+/5+) as a promotion ladder, precedent lookup as a hook not a rule, AND the introspection agent is more genuinely novel than initially assessed — existing skills don't deliver it autonomously.

---

## Key Adaptations Required

### 1. Project-Scoped Trace Queries for Rule Generation

All 3 Unicode regex error traces are from a stock-extraction JS project, not Jarvis. Auto-generating Jarvis rules from cross-project traces would be wrong. Introspection must filter by project context.

```python
# Required: project_dir scoping
errors = context_list_traces(
    category="error",
    project_dir="/path/to/jarvis-mac"  # explicit, not default
)
```

### 2. Human Review Gate Before CLAUDE.md

Auto-editing CLAUDE.md is too risky. Correct flow:

```
3+ occurrences → generate .claude/rules/draft-{name}.md (not active)
                                    ↓
                    Human reviews + renames to {name}.md
                                    ↓
5+ validated occurrences → human promotes to CLAUDE.md
```

### 3. Use Rewritten Introspect Skill

`learning-loop` deleted — broken, never triggered. `introspect` rewritten with:

- Agent calls MCP directly (no broken `claude mcp call` subprocess)
- Session-deduped thresholds (3+ sessions → draft rule, 5+ → human promotes to CLAUDE.md)
- Project-dir filtering step explicit in workflow
- Scripts demoted to templates-only, agent fills content

### 4. Occurrence Threshold Needs Dedup

A single bad session can generate 5+ traces on the same bug (visible in error traces: Jan 27-28 stock extraction session spawned ~8 error traces). Threshold should be session-deduped:

```
N+ occurrences across M+ sessions (not just raw count)
```

---

## What to Adopt (Phase 1 — High Value, Low Risk)

**Mandatory precedent lookup as a hook**, not just a rule:

```json
// ~/.claude/hooks/pre-decision.json
{
  "event": "PreToolUse",
  "matcher": "task|architecture|implementation",
  "script": "query-context-graph.sh"
}
```

This converts the existing CLAUDE.md rule into enforced behavior. The 0.75/0.60 similarity thresholds already defined in CLAUDE.md are correct — just need mechanical enforcement.

---

## Key Principles

| Principle | Meaning |
|-----------|---------|
| Traces without extraction are archives, not learning | Storing is not enough; periodic introspection closes the loop |
| Rules without enforcement are suggestions | Pre-decision hooks, not just CLAUDE.md text |
| Occurrence threshold needs session dedup | 5 traces in 1 session ≠ 5 independent incidents |
| Cross-project traces contaminate project-specific rules | Always filter by project_dir when generating rules |

## Patterns

| Before | After |
|--------|-------|
| Context graph queried manually when remembered | Pre-decision hook forces query before architecture/implementation decisions |
| Introspect skill run on-demand | Scheduled weekly or triggered at session end by orchestrator |
| CLAUDE.md edited manually when pattern noticed | Draft rule generated at 3+ occurrences, human reviews, promotes at 5+ validated |

## Anti-Patterns

| Anti-Pattern | Problem |
|--------------|---------|
| Auto-editing CLAUDE.md from traces | False patterns pollute rules permanently |
| Cross-project traces without filtering | Unicode regex lint for Jarvis from JS stock-extraction errors |
| New introspection scripts instead of existing skills | Duplicate tooling, skill registry ignored |
| Raw occurrence count without session dedup | One bad session triggers premature rule generation |

---

## Integration Notes

**Tier**: 1 (Reference)
**Created**: 2026-02-18
**Sessions Used**: 0
**Promotion Status**: Pending validation

### Reasoning

1. **Problem**: Context graph underutilized — traces stored but no extraction loop.
2. **Do we have this problem?** Yes, 76 traces with no automated learning.
3. **Best solution?** Partially — existing skills (introspect, learning-loop) already address this; novel value is in hook enforcement + occurrence thresholds.
4. **Can we verify?** Yes — implement hook, run weekly introspect, measure if rules are generated.
5. **Aligns with existing principles?** Yes — determinism (code > judgment), enforcement (hooks > rules).
