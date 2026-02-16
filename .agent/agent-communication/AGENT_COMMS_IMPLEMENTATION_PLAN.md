# AGENT_COMMS_IMPLEMENTATION_PLAN.md

Last updated: 2026-02-16

Scope: Concrete implementation plan for an unattended “Claude implements, Codex reviews” loop using A2A as the coordination protocol. The audit projection is split into:

- `.agent/ARCHITECTURE.md` (stable, agreed/approved architecture)
- `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md` (in-flight implementation/review log)

References:
- `.agent/agent-communication/AGENT_CONTRACT.md` (workflow + contract; default file-based comms, optional A2A future-mode)
- `.agent/agent-communication/AGENT_COMMS_FRAMEWORK.md` (process, evidence ladder, collaboration rules)

## 0. Definition Of Done

The system runs without user facilitation:

1. Claude implementer can receive an item to implement, implement it, run declared tests, and publish structured evidence.
2. Codex reviewer can receive the submission, run an automated review + verification suite, and return a verdict with stable blocker IDs.
3. The coordinator routes CHANGES_REQUESTED back to implementer until APPROVED.
4. `.agent/ARCHITECTURE.md` and `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md` are updated automatically as a projection of the latest A2A artifacts.
5. No interactive approval prompts occur anywhere. If they would, the system fails fast with a structured error.

## 1. Components (What We’re Building)

1. `claude-implementer` A2A server
2. `codex-reviewer` A2A server
3. `comms-coordinator` (state machine + retries)
4. `analysis-projector` (writes audit projection from artifacts)
   - Projection targets: `.agent/ARCHITECTURE.md` + `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md` (split)

Non-goals:
- A GUI for this loop
- Replacing existing Jarvis channels (WS/Slack/CLI). This loop is for agent-to-agent work coordination.

## 2. Roles (Ownership)

1. Claude (implementer agent) owns:
   - implementer runner behavior
   - implementation evidence artifacts
2. Codex (reviewer agent) owns:
   - reviewer runner behavior
   - review verdict artifacts + blocker IDs
3. Either side can host the coordinator, but it must be deterministic and auditable.

## 3. A2A Contract (Data Shapes)

All payloads are typed JSON objects (no free-form prose fields unless explicitly marked).

1. `implementation_submission`
2. `review_verdict`
3. `fix_response`
4. `approval_stamp`

Exact fields are defined in `.agent/agent-communication/AGENT_CONTRACT.md`.

## 4. Configuration

Create a single config file for the comms loop:

Path:
- `.agent/comms_config.json`

Fields (minimum):
- `claude.base_url`
- `claude.token_env` (name of env var holding bearer token)
- `codex.base_url`
- `codex.token_env`
- `timeouts.submit_seconds`
- `timeouts.review_seconds`
- `timeouts.implement_seconds`
- `retries.max_attempts`
- `sandbox.mode` (must be `workspace-write` or stricter for reviewer)
- `projection.architecture_path` (default `.agent/ARCHITECTURE.md`)
- `projection.inflight_path` (default `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`)

Security:
- Tokens are NEVER stored in git.
- Tokens must be read from env vars or from `~/.agent/*` with 0600 perms.

## 5. Phase Plan

### Phase P0: Repository Layout (1 PR)

Deliverables:
- Add `.agent/agent-communication/AGENT_COMMS_IMPLEMENTATION_PLAN.md` (this file).
- Add `.agent/comms_config.example.json` (sanitized).
- Add `.agent/comms_config.json` to `.gitignore`.

Acceptance:
- Plan + example config exist and contain no secrets.

### Phase P1: Codex Reviewer Service (A2A server + runner) (1-2 PRs)

Goal:
- A2A endpoint that can run an automated review of a submission with no interactive approvals.

Implementation:
1. Add a service module in this repo (suggested):
   - `src/jarvis/comms/codex_reviewer_service.py`
2. Implement A2A endpoints:
   - `/.well-known/agent-card.json`
   - JSON-RPC `message/send`, `message/stream`, `tasks/get`, `tasks/cancel`
3. Runner:
   - Shell out to `codex exec` with a pinned “review prompt template”.
   - Enforce sandbox/approval policy for reviewer:
     - no interactive approvals
     - workspace-write or stricter
4. Output:
   - Produce `review_verdict` artifact with:
     - verdict: APPROVED / CHANGES_REQUESTED
     - stable blocker IDs per item (e.g. `A5-B1`)
     - file refs + commands run + results

Acceptance tests:
1. Unit test: given a synthetic submission payload -> reviewer produces a deterministic JSON verdict shape.
2. Integration smoke: run reviewer service, submit a dummy task, receive a Task id, poll `tasks/get`, and get terminal verdict.

### Phase P2: Claude Implementer Service (A2A server + runner) (1-2 PRs)

Goal:
- A2A endpoint that can implement changes and return evidence.

Implementation:
1. Add service module (suggested):
   - `src/jarvis/comms/claude_implementer_service.py`
2. Implement A2A endpoints:
   - `/.well-known/agent-card.json`
   - JSON-RPC `message/send`, `message/stream`, `tasks/get`, `tasks/cancel`
3. Runner:
   - Shell out to Claude Code (or invoke Claude Agent SDK directly if already embedded).
   - Must be configured with:
     - explicit allowed-tools
     - hooks for fail-fast enforcement
     - non-interactive mode (no prompts that require human approval)
4. Output:
   - `implementation_submission` / `fix_response` artifacts with:
     - files changed
     - tests run (commands + results)
     - known limitations (if any)

Acceptance tests:
1. Unit test: submission -> returns artifact matching schema.
2. Integration smoke: run implementer service, submit a trivial “edit doc” item, verify file change + test evidence, terminal state = completed.

### Phase P3: Coordinator Loop (1 PR)

Goal:
- Deterministic state machine that routes tasks between implementer and reviewer until APPROVED.

Implementation:
1. Module (suggested):
   - `src/jarvis/comms/coordinator.py`
2. State:
   - persist in SQLite (use existing Jarvis MemoryStore or a dedicated `comms_tasks` table)
3. Flow:
   - receive initial item request
   - call implementer -> wait terminal
   - call reviewer -> wait terminal
   - if CHANGES_REQUESTED -> send fix_response back to implementer
   - stop on APPROVED or hard failure
4. Retries:
   - bounded, with explicit failure artifact on exhaustion

Acceptance:
- Run end-to-end on a toy item:
  - first pass fails review
  - second pass passes review
  - coordinator terminates with APPROVED

### Phase P4: Analysis Projector (1 PR)

Goal:
- Keep `.agent/ARCHITECTURE.md` (architecture) and `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md` (in-flight) consistent with the comms state machine automatically.

Implementation:
1. Module:
   - `src/jarvis/comms/analysis_projector.py`
2. Inputs:
   - latest artifacts from implementer + reviewer
3. Output:
   - updates `.agent/ARCHITECTURE.md`:
     - status transitions per comms framework
     - append-only Codex review blocks
     - append-only Claude response blocks
     - stamp “Approved by Codex …” on approval
   - updates `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`:
     - all per-item statuses/evidence/verdicts/blockers while in-flight

Rules:
- Do not rewrite historical Codex blocks.
- Do not rewrite Claude evidence blocks; only append and update the current status line.

Acceptance:
- Given a recorded artifact sequence, projector produces stable deterministic diffs for `.agent/ARCHITECTURE.md` and `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`.

### Phase P5: Hardening (ongoing)

1. Cancellation:
   - `tasks/cancel` cancels active runner processes.
2. Streaming:
   - `message/stream` streams status updates + artifact deltas.
3. Error envelope:
   - layer/code/message/remediation, correlation ids.
4. Security:
   - tokens required; no dev bypass; strict file permissions if file-based tokens are used.
5. Load shedding:
   - rate limit per agent endpoint to prevent runaway loops.

Acceptance:
- Chaos tests:
  - kill/restart coordinator mid-flight; resume from persisted state
  - simulate token/auth failure -> explicit `auth` layer error
  - simulate runner crash -> explicit `runtime` layer error

## 6. Prompts / Harness (Reviewer + Implementer)

### Implementer prompt template

Inputs:
- item_id
- requirements (structured)
- constraints (tools allowed, trust tier)
- repository root
- tests required

Output requirements:
- MUST emit typed artifacts (JSON) and cite file refs.
- MUST run declared tests unless blocked; if blocked, emit failure with remediation.

### Reviewer prompt template

Inputs:
- item_id
- diff/changed files
- tests run by implementer
- claims/evidence from implementer

Output requirements:
- MUST return `review_verdict` typed JSON:
  - stable blocker IDs
  - file refs
  - verification commands run + results

## 7. Open Risks / Decisions Needed

1. Where do these services run?
   - local machine only (launchd) vs remote host
2. What is the source-of-truth workspace for both agents?
   - must be consistent or explicitly mapped per `contextId`.
3. How do we guarantee no interactive prompts from Claude Code?
   - hooks + allowed-tools gating; abort on any approval request event.
