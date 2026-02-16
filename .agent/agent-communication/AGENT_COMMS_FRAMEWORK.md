# AGENT_COMMMS_FRAMEWORK.md

Last updated: 2026-02-16

Purpose: current file-based comms framework for Codex (review) + Claude (implement) while optimizing Jarvis + OpenClaw config.

## Mission

Build Jarvis as a mac-native, RAM-efficient, highly autonomous execution engine (Claude Agent SDK-first), integrated with OpenClaw via A2A, with explicit failures and progressive-disclosure context use.

## Roles

- Claude: implement changes + publish evidence.
- Codex: verify (diff/tests/runtime) + publish verdict + blockers.
- No major decision is “agreed” without explicit review from the other agent.

## Evidence Ladder (hard rule)

1. DeepWiki (repo reality)
2. Official specs/docs (A2A, Claude Agent SDK, Apple)
3. Local code + tests
4. Blogs/articles (advisory)

If conflicts exist: official spec/docs win.

## Canonical Files

- Stable architecture (agreed/approved only): `.agent/ARCHITECTURE.md`
- In-flight coordination (open items only): `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`
- Execution plan (mutable): `.agent/inflight-communication/IMPLEMENTATION_PLAN.md`
- This framework: `.agent/agent-communication/AGENT_COMMS_FRAMEWORK.md`

## Approval-Gated Updates (user approval required)

- `.agent/MISSION.md`
- `.agent/agent-communication/AGENT_COMMS_FRAMEWORK.md`
- Major restructure of `.agent/ARCHITECTURE.md` (routine content additions ok)

## Implementation/Review Protocol (mandatory)

### Status values (only these)

`PLANNED` → `IN_IMPLEMENTATION` → `READY_FOR_REVIEW` → `CHANGES_REQUESTED` → `READY_FOR_REREVIEW` → `APPROVED`

### Per-item required fields (in inflight file)

1. `**Status: <STATE>**`
2. Claude evidence: files changed, tests run (commands + result), limitations.
3. Codex verdict: `REVIEW: APPROVED` or `REVIEW: CHANGES REQUESTED`, with stable blocker IDs (`A5-B2`).
4. If changes requested: Claude response mapping each blocker ID to exact file refs + verification.

### Anti-ambiguity rules

- Snapshot table must match per-item statuses.
- After `REVIEW: CHANGES REQUESTED`, status must be `CHANGES_REQUESTED` until Claude responds and sets `READY_FOR_REREVIEW`.
- No “fixed/approved” claims without a Codex re-review verdict.

### Promotion rule (mandatory)

Once an item is `APPROVED`:
1. Remove it from `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`.
2. Add the stable outcome to `.agent/ARCHITECTURE.md` (no review chatter).
3. Keep the inflight snapshot containing only non-approved items.

## OpenClaw Scope Rule

OpenClaw code is out of scope. Only configuration + integration contract are in scope.

