# .agent/ README

This folder is the **agent workspace** for the Jarvis repo. It is designed to:

1. Keep **stable architecture** separate from **in-flight implementation/review chatter**.
2. Make Codex <-> Claude collaboration explicit, auditable, and low-ambiguity.
3. Support **progressive disclosure**: load only what you need for the current step.

## Writing Rules (Mandatory)

When updating any `.agent/*` document:
1. Be concise and concrete. Prefer short bullets over paragraphs.
2. Progressive disclosure is required:
   - Put the minimal stable truth in `ARCHITECTURE.md`.
   - Put churn, logs, and coordination details only in `inflight-communication/*`.
3. Avoid duplication. Reference the canonical file instead of copying text.

## Files And Folders

### `.agent/MISSION.md`

**What it is:** The north star for Jarvis (product/agent mission).  
**Stability:** High. Changes are rare and should reflect real product direction shifts.  
**Who edits:** Human-approved only (per comms rules).  
**When to read:** At the start of any architecture discussion or if decisions feel misaligned.

### `.agent/ARCHITECTURE.md`

**What it is:** The **current agreed/approved** Jarvis architecture (facts + decisions).  
**What it is not:** A status log, review thread, or per-PR implementation tracker.  
**Who edits:** Either agent, but only to add mutually agreed decisions; avoid rewriting structure without approval.  
**When to read:** When deciding where to implement, what invariants exist, what “done” looks like architecturally.

### `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`

**What it is:** The **in-flight communication log** for Codex <-> Claude implementation + review.

Contains:
- statuses (state machine)
- blocker IDs
- per-item evidence (Claude)
- review verdicts (Codex)
- known limitations + follow-ups

**Who edits:**
- Claude: implementation evidence + response blocks.
- Codex: review verdict blocks + blocker IDs + approvals.

**When to read:** Any time you are implementing, reviewing, or tracking open blockers.

### `.agent/inflight-communication/IMPLEMENTATION_PLAN.md`

**What it is:** The execution plan tied to the architecture and the current in-flight work.  
**Who edits:** Either agent, but keep it operational and concise.  
**When to read:** Before starting a large implementation pass; to avoid drifting work.

### `.agent/agent-communication/AGENT_COMMS_FRAMEWORK.md`

**What it is:** The **current comms protocol** Codex and Claude follow right now (file-based).  
Includes: evidence ladder, review mechanics, and promotion rule (approved moves to architecture).  
**Stability:** Medium-high. This is “how we operate.”  
**When to read:** When uncertain about review mechanics, ownership, or what constitutes approval.

### `.agent/agent-communication/AGENT_CONTRACT.md`

**What it is:** The canonical **workflow + contract** between implementer and reviewer.

Contains:
- Default (current): file-based comms contract
- Future-mode (optional): A2A agent-to-agent contract (off by default)

**When to read:** When updating tooling/automation for comms, or migrating to A2A.

### `.agent/agent-communication/AGENT_COMMS_IMPLEMENTATION_PLAN.md`

**What it is:** The plan to migrate from file-based comms to A2A-based direct comms.  
**When to read:** When implementing the A2A comms loop services/coordinator/projector.

### `.agent/user/USER_WORKSPACE.md`

**What it is:** User-provided requirements, preferences, and high-signal constraints (continuous learning engine ideas, workflow preferences).  
**Stability:** Medium. Updated when the user revises goals/constraints.  
**When to read:** When designing learning loops, memory, harness behavior, autonomy controls.

## How Agents Should Use This Folder (Operational Rules)

1. Start with `.agent/MISSION.md` and `.agent/ARCHITECTURE.md` to understand goals + current architecture.
2. For any implementation/review work, operate only in:
   - `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`
   - `.agent/inflight-communication/IMPLEMENTATION_PLAN.md`
3. Promote to `.agent/ARCHITECTURE.md` only after agreement/approval (no in-flight chatter).
4. After Codex marks an item `APPROVED`, remove it from inflight and add the stable outcome to architecture (promotion rule).
5. Never “close” blocker IDs unless you are the reviewer (Codex).
6. Keep context small:
   - load only the sections relevant to the current item/blocker
   - do not paste large logs unless they are required evidence

## When To Update Which File

Use this as the primary decision table for edits:

1. Update `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md` when:
   - any implementation item status changes (`PLANNED` -> `IN_IMPLEMENTATION` -> ...).
   - Claude adds implementation evidence, test results, limitations, or response-to-review.
   - Codex adds review verdicts, blocker IDs, re-review outcomes, or approval stamps.
   - anything is still in dispute or not yet approved.

2. Update `.agent/inflight-communication/IMPLEMENTATION_PLAN.md` when:
   - the execution plan needs sequencing changes (phases/gates).
   - you add/remove deliverables, gates, or test requirements for in-flight work.
   - you discover prerequisites that must be satisfied before continuing.

3. Update `.agent/ARCHITECTURE.md` when:
   - an architecture decision is mutually agreed/approved and should become “current state”.
   - you are documenting stable invariants/interfaces (A2A contract shape, session model, trust model).
   - you are removing or superseding an older architecture decision (must be trace-linked).
   - Do not add per-PR progress, review chatter, or temporary workarounds here.

4. Update `.agent/user/USER_WORKSPACE.md` when:
   - the user adds new product goals, preferences, autonomy constraints, or workflow expectations.
   - the user provides new research inputs to be considered for future evolution.
   - This file is inputs, not decisions: do not treat it as automatically adopted architecture.

5. Update `.agent/MISSION.md` when:
   - the product mission changes (rare).
   - Requires explicit user approval.

6. Update `.agent/agent-communication/AGENT_COMMS_FRAMEWORK.md` when:
   - you need to change the current (file-based) operating protocol, evidence ladder, or review mechanics.
   - Requires explicit user approval.

7. Update `.agent/agent-communication/AGENT_CONTRACT.md` when:
   - you are changing the workflow/contract surface between implementer and reviewer (status rules, artifact schema).
   - Changes should be minimal and contract-driven (avoid duplicating architecture here).

8. Update `.agent/agent-communication/AGENT_COMMS_IMPLEMENTATION_PLAN.md` when:
   - you are implementing the migration from file-based comms to direct A2A comms.
   - you discover missing components (coordinator/projector/service endpoints) or need new acceptance tests.

## Review (Why This Structure Is Good / What To Watch)

**What’s working well:**
1. Clear separation: stable architecture (`ARCHITECTURE.md`) vs in-flight tracking (`inflight-communication/*`).
2. Clear comms governance: comms protocol docs are grouped under `agent-communication/`.
3. Progressive disclosure is now structurally enforced (you can open only the folder you need).

**Risks / improvements to consider:**
1. `ARCHITECTURE.md` is still fairly large. If it grows further, split into:
   - `ARCHITECTURE.md` (1-page summary)
   - `ARCHITECTURE_DETAILS.md` (long-form decisions)
2. In-flight logs can still bloat. Consider rotating old rounds into `inflight-communication/archive/YYYY-MM-DD.md` once items are approved.
3. Ensure every “review” is backed by runnable evidence; otherwise the log becomes aspirational instead of auditable.
