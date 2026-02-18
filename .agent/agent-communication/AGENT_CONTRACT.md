# AGENT_CONTRACT.md

Last updated: 2026-02-16

Purpose: Single source of truth for **workflow + contract** between implementer (Claude) and reviewer (Codex). This file is referenced by implementation plans and automation.

This repo currently follows **file-based communication** for implementation/review loops. A direct A2A-based loop is specified here as a **future-mode contract** for automation; it must not silently replace file-based comms until explicitly enabled.

## 1. Actors

1. **Claude (Implementer)**
   - Writes code changes.
   - Writes *implementation evidence*.
   - Responds to review blockers.
2. **Codex (Reviewer)**
   - Reviews changes.
   - Writes verdicts and blocker IDs.
   - Approves or requests changes.

## 2. Current Workflow (Default): File-Based Comms

### 2.1 Canonical Documents

1. `.agent/ARCHITECTURE.md`
   - Contains current Jarvis architecture (agreed/approved decisions only).
2. `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`
   - Contains implementation/review tracking for in-flight work, plus unresolved/contested items.
3. `.agent/agent-communication/AGENT_COMMS_FRAMEWORK.md`
   - Process + evidence ladder (governs collaboration).

### 2.2 Implementation Review State Machine (Required)

Canonical states (only these):

1. `PLANNED`
2. `IN_IMPLEMENTATION`
3. `READY_FOR_REVIEW`
4. `CHANGES_REQUESTED`
5. `READY_FOR_REREVIEW`
6. `APPROVED`

Strict transitions:

1. Claude starts: `PLANNED -> IN_IMPLEMENTATION`
2. Claude completes + evidence: `IN_IMPLEMENTATION -> READY_FOR_REVIEW`
3. Codex reviews:
   - pass: `READY_FOR_REVIEW -> APPROVED`
   - fail: `READY_FOR_REVIEW -> CHANGES_REQUESTED`
4. Claude addresses blockers: `CHANGES_REQUESTED -> READY_FOR_REREVIEW`
5. Codex re-reviews:
   - all blockers closed: `READY_FOR_REREVIEW -> APPROVED`
   - any blocker open: `READY_FOR_REREVIEW -> CHANGES_REQUESTED`

Anti-ambiguity rules:

1. If the latest Codex verdict is `REVIEW: CHANGES REQUESTED`, item status MUST be `CHANGES_REQUESTED` or `READY_FOR_REREVIEW` (never `APPROVED`).
2. If the latest Codex verdict is `REVIEW: APPROVED`, item status MUST be `APPROVED`.
3. Only Codex closes blocker IDs. Claude may mark blockers as “addressed”, not “closed”.
4. Snapshot consistency:
   - If `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md` includes a snapshot table, it must match per-item `Status:` values.
   - After a Codex `REVIEW: CHANGES REQUESTED`, the snapshot row remains `CHANGES_REQUESTED` until Claude posts a response and sets `READY_FOR_REREVIEW`.

### 2.3 Required Per-Item Structure in `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`

Each implementation item (in-flight) must include:

1. `Status: <STATE>`
2. `Implementation Evidence (Claude)`:
   - files changed
   - tests run (commands + results)
   - known limitations
3. `Codex Review (Round N)`:
   - `REVIEW: APPROVED` or `REVIEW: CHANGES REQUESTED`
   - blocker list with stable blocker ids (`A5-B1`, `B2-B1`, ...)
4. `Claude Response to Review (Round N)` (only when changes requested):
   - one line per blocker id:
     - `A5-B1 -> addressed in <file:line> + verification evidence`

## 3. Future Workflow (Optional): Direct Agent-to-Agent Comms (A2A)

This mode enables unattended coordination. It is **off by default** and must be explicitly enabled by configuration/automation.

### 3.1 Transport + Discovery

1. HTTP + JSON-RPC 2.0
2. Discovery via `/.well-known/agent-card.json`
3. Bearer token (or stronger) auth on every request

### 3.2 Typed Payloads (No Free-Form Prose as the Contract)

1. `implementation_submission` (Claude -> Codex)
2. `review_verdict` (Codex -> Claude)
3. `fix_response` (Claude -> Codex)
4. `approval_stamp` (Codex -> Claude)

These are the canonical payload shapes for automation and must remain stable once implemented.

### 3.3 Required Methods

1. `message/send`
2. `message/stream`
3. `tasks/get`
4. `tasks/cancel`

### 3.4 Projection Rule (Audit Output)

Even in direct-comms mode, the audit projection remains file-based:

1. `.agent/ARCHITECTURE.md` contains agreed/approved architecture decisions only.
2. `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md` contains implementation/review tracking (statuses, evidence, verdicts, blockers).
3. Update statuses based on the latest A2A artifacts.
4. Append-only for Codex review text and Claude evidence/response blocks.
5. Never silently diverge the audit record from the A2A event stream.

### 3.5 Fail-Fast Policy

If direct-comms mode is enabled and A2A fails:

1. emit a structured error artifact (`layer`, `code`, `message`, `remediation`, correlation ids)
2. open a comms blocker id (e.g., `COMMS-B1`)
3. do not fall back silently to file-only coordination

## 4. Learnings Policy (How We Update This Contract)

1. Process learnings (e.g., ambiguity prevention, blocker closure rules) belong here.
2. Tool/protocol learnings (A2A/MCP/Codex/Claude Code) belong here only when they change the contract surface.
3. Architecture decisions belong in `.agent/ARCHITECTURE.md`, not in this file.
