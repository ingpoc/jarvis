# Capability Checklist Template

Use this checklist before implementing any new harness optimization.

## Proposal

| Field | Value |
|------|-------|
| Proposal name | |
| Target layer | `Codex` / `Claude Code` / `Jarvis app` |
| Problem statement | |
| Expected outcome metric | |

## Built-In First Gate (Required)

1. Which platform built-ins already address this?
2. Which built-ins were configured/tested first?
3. Why are built-ins insufficient (if still proposing custom work)?

Evidence:

- Relevant capability doc used:
- Config/settings attempted:
- Test result:

## Enforcement Classification

| Question | Answer |
|----------|--------|
| Is this deterministic enforcement or advisory guidance? | |
| If deterministic: where enforced? (`permissions` / `hooks` / `execpolicy` / `SDK callback`) | |
| If advisory: where documented? (`AGENTS` / `CLAUDE` / `docs`) | |

## Scope Routing

| Content type | Owner location |
|--------------|----------------|
| Cross-project policy | `~/.codex/rules/*` or `~/.claude/rules/*` |
| Repo-specific workflow | `docs/workflow/*` |
| Always-on core principle | `AGENTS.md` / `CLAUDE.md` |
| Runtime config | `~/.codex/config.toml` / `~/.claude/settings.json` |

## Safety and Cost

1. Blast radius:
2. Runtime affected (`Codex`, `Claude`, `both`):
3. Rollback path:
4. Token/cost impact:

## Verification Plan

| Check | Method | Pass criteria |
|-------|--------|---------------|
| Config validity | (`jq`, `toml` check, startup check) | No parse/runtime errors |
| Behavior | Repro test | Expected decision/output observed |
| Regression | Existing flow smoke test | No breakage in baseline workflows |

## Decision

| Outcome | Criteria |
|---------|----------|
| Adopt now | Built-ins insufficient, measurable gain, low risk |
| Defer | Good idea, low current ROI or missing prerequisites |
| Reject | Redundant, over-engineered, or unverified claim |

Final decision:

Reason:

## Learning Loop

1. Store context trace (`problem`, `root_cause`, `fix`, `validation`, `outcome`).
2. If adopted, update owner docs/config once.
3. If rejected/deferred, record reason to avoid repeated re-evaluation.
