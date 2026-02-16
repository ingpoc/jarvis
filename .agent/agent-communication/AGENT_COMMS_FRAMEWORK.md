# AGENT_COMMMS_FRAMEWORK.md

Last updated: 2026-02-16
Purpose: Operating framework for Codex + Claude to continuously optimize Jarvis architecture and OpenClaw configuration.

## 1. Mission

Build Jarvis as a mac-native, RAM-efficient, highly autonomous agent system powered by Claude Agent SDK, integrated with OpenClaw via A2A, with explicit failures and progressive-disclosure context usage.

## 2. Roles and Responsibility

- Codex:
  - Implementation authority in Jarvis repo.
  - Validates feasibility against real code/runtime.
  - Converts accepted architecture decisions into concrete changes/tests.
- Claude:
  - Architecture challenger and alternate-design generator.
  - Protocol/compliance reviewer (A2A, SDK capabilities, security model).
  - Flags long-term risks, coupling, and maintainability gaps.

Neither agent can mark a major decision “agreed” without explicit review from the other.

## 3. Evidence Ladder (Mandatory)

For each non-trivial architecture decision:
1. DeepWiki first (repo-grounded architecture and implementation reality).
2. Official docs second:
   - Claude Agent SDK docs/repo
   - OpenClaw docs/repo
   - A2A spec/docs
   - Apple docs/repos for mac-native behavior
3. Local code validation third.
4. External articles/blogs last (advisory only).

If DeepWiki and official docs conflict, official docs/spec win.

## 4. Progressive-Disclosure Protocol

To control context and improve reliability:
1. Start with summary-level findings only.
2. Load detailed docs only for currently contested/active decisions.
3. Keep one canonical architecture decision per topic in `.agent/ARCHITECTURE.md`.
4. Keep implementation/review tracking and unresolved/contested items in `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`.
5. Avoid duplicate policy text across files.

## 5. Decision Lifecycle

For every architecture cycle:
1. Baseline:
   - Current state (code + runtime behavior)
   - Target state
2. Proposal A/B:
   - At least one viable alternative
3. Challenge pass:
   - Codex critiques Claude proposal
   - Claude critiques Codex proposal
4. Resolution:
   - Agreed -> `.agent/ARCHITECTURE.md`
   - Unresolved -> `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`
5. Trace:
   - Store decision in Context Graph

## 6. Architecture Review Axes (Hard Gate)

A proposal is not accepted unless all are addressed:
1. Correctness
2. Latency/performance
3. RAM/CPU efficiency
4. Reliability/recovery
5. Security/trust boundaries
6. Observability/diagnostics
7. Operational complexity
8. Evolution/upgrade risk

## 7. Jarvis Capability Framework

Jarvis must support:
1. Conversational continuity across ingress channels.
2. Autonomous tool selection with policy controls.
3. Sub-agent spawning when complexity justifies decomposition.
4. MCP server usage (static + dynamic additions).
5. Skill usage and safe skill extension.
6. Coding and non-coding workflows:
   - coding: plan, implement, test, review, report
   - non-coding: research, monitoring, analysis, summarization
7. macOS-native integrations:
   - launchd-managed lifecycle
   - notifications
   - container runtime integration
   - local model/runtime pathways where applicable

## 8. Performance and Memory SLO Guidance

Jarvis architecture changes should target:
1. Bounded resident memory growth for long-lived daemon sessions.
2. No unbounded in-memory event accumulation.
3. Streaming over bulk buffering for long-running tasks.
4. Explicit backpressure/retry behavior for adapters.
5. Configurable timeouts with explicit failure reporting.

## 9. OpenClaw Integration Framework (Config-Only Scope)

OpenClaw development is out of scope; configuration and integration contract are in scope.

Required OpenClaw configuration outcomes:
1. Register Jarvis delegation tools (`a2a_delegate`, `a2a_poll_task`, `a2a_cancel_task`, `a2a_discover`).
2. Set Jarvis endpoint + auth token + routing policy.
3. Map OpenClaw delegation intents to Jarvis trust envelopes.
4. Propagate correlation IDs through delegation chain.
5. Configure blocking/non-blocking behavior per task class.

Required Jarvis contract for OpenClaw:
1. Stable AgentCard discovery.
2. A2A send/stream/get/cancel support.
3. Structured error schema with layer + code + remediation.
4. Deterministic task state transitions and artifact outputs.

## 10. Autonomy Controls

Autonomy must remain controllable via:
1. Trust tiers
2. Budget limits
3. Hook-based pre/post tool policies
4. Explicit approval gates for high-risk actions
5. Audit traces in Context Graph

## 11. Documentation Contract

Required files and ownership:
- `.agent/ARCHITECTURE.md`: current Jarvis architecture (agreed/approved only)
- `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`: implementation/review tracking + unresolved/contested items
- `.agent/agent-communication/AGENT_COMMS_FRAMEWORK.md`: operating framework (this file)

### Approval-Gated Updates (User Approval Required)

The following files must not be changed without explicit user approval:
1. `.agent/MISSION.md`
2. `.agent/agent-communication/AGENT_COMMS_FRAMEWORK.md`
3. Any major rewrite of `.agent/ARCHITECTURE.md` structure (not routine content additions)

Allowed without prior approval:
1. Add newly agreed decisions to `.agent/ARCHITECTURE.md`
2. Move unresolved/contested items to `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`
3. Add implementation progress details to `.agent/inflight-communication/IMPLEMENTATION_PLAN.md`
4. Correct typos/formatting in `.agent/*` docs (no semantic changes)

### Codex + Claude Document Management Rules

1. `MISSION.md`:
   - stable north star
   - update only when product mission changes
   - requires user approval always
2. `AGENT_COMMS_FRAMEWORK.md`:
   - governs collaboration process and evidence policy
   - changes require user approval
3. `ARCHITECTURE.md`:
   - append/update only mutually agreed/approved architecture decisions
   - remove stale sections only if superseded and trace-linked
4. `inflight-communication/ANALYSIS_IMPROVEMENT.md`:
   - implementation/review tracking for in-flight work
   - unresolved disagreements/open items
   - must be emptied only when there is no in-flight implementation/review work AND no open disagreements
5. `inflight-communication/IMPLEMENTATION_PLAN.md`:
   - operational execution plan tied to `.agent/ARCHITECTURE.md`
   - may be updated as phases complete, with decision traces

## 12. Implementation Review Workflow (Claude -> Codex)

This workflow is mandatory for implementation items tracked in `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`.

### 12.1 Canonical Status States (Only These Allowed)

1. `PLANNED`
2. `IN_IMPLEMENTATION`
3. `READY_FOR_REVIEW`
4. `CHANGES_REQUESTED`
5. `READY_FOR_REREVIEW`
6. `APPROVED`

No free-form status text is allowed outside these values.

### 12.2 Ownership Rules

1. Claude owns:
   - code implementation
   - implementation evidence block
   - response-to-review block
2. Codex owns:
   - review verdict block
   - blocker definitions
   - final approval marker
3. Claude must not edit or delete prior Codex review text.
4. Codex must not rewrite Claude implementation evidence; only append review outcome.

### 12.3 Required Structure Per Item in `inflight-communication/ANALYSIS_IMPROVEMENT.md`

Every implementation item must contain these fields:

1. `Status: <STATE>`
2. `Implementation Evidence (Claude)`:
   - files changed
   - tests run (commands + result)
   - known limitations
3. `Codex Review (Round N)`:
   - `REVIEW: APPROVED` or `REVIEW: CHANGES REQUESTED`
   - blocker list with stable blocker ids (`B1`, `B2`, ...)
4. `Claude Response to Review (Round N)` (only when changes requested):
   - mapping for each blocker id:
     - `B# -> addressed in <file:line> + test/verification evidence`

### 12.4 State Machine (Strict Transitions)

1. Claude starts item: `PLANNED -> IN_IMPLEMENTATION`
2. Claude completes first pass with evidence: `IN_IMPLEMENTATION -> READY_FOR_REVIEW`
3. Codex reviews:
   - pass: `READY_FOR_REVIEW -> APPROVED`
   - fail: `READY_FOR_REVIEW -> CHANGES_REQUESTED`
4. Claude addresses each blocker id and updates response block:
   - `CHANGES_REQUESTED -> READY_FOR_REREVIEW`
5. Codex re-reviews:
   - all blockers closed: `READY_FOR_REREVIEW -> APPROVED`
   - any blocker open: `READY_FOR_REREVIEW -> CHANGES_REQUESTED`

### 12.5 Anti-Ambiguity Rules

1. An item cannot remain `READY_FOR_REVIEW` or `READY_FOR_REREVIEW` after a Codex verdict is posted.
2. If Codex verdict is `REVIEW: CHANGES REQUESTED`, status must be `CHANGES_REQUESTED`.
3. If Codex verdict is `REVIEW: APPROVED`, status must be `APPROVED`.
4. Contradictions are not allowed:
   - no “fixed” claim without corresponding Codex re-review verdict.
   - no “approved” claim if any blocker id remains open.
5. Snapshot consistency:
   - Any summary/snapshot table in `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md` must reflect the same status state machine as per-item sections.
   - After Codex posts `REVIEW: CHANGES REQUESTED`, both the per-item `Status:` and the snapshot row must be `CHANGES_REQUESTED` until Claude posts a response and transitions to `READY_FOR_REREVIEW`.

### 12.6 Claude Behavior After Review Comments

When Codex requests changes, Claude must:

1. Keep prior Codex review block unchanged.
2. Add `Claude Response to Review (Round N)` with one line per blocker id.
3. Include exact file references and verification evidence for each blocker.
4. Update status to `READY_FOR_REREVIEW` only after every blocker id has a response entry.
5. Request Codex re-review explicitly after updating evidence.

### 12.7 Codex Behavior After Re-Review

1. Re-check each blocker id against code and tests.
2. Append new `Codex Review (Round N+1)` verdict.
3. Mark each prior blocker id as `closed` or `still open`.
4. Set status to:
   - `APPROVED` when all blockers are closed.
   - `CHANGES_REQUESTED` otherwise.
5. If approved, add a one-line completion stamp:
   - `Approved by Codex on <date>, Round <N>`

### 12.8 Completion Rule

An implementation item is complete only when:

1. latest Codex verdict is `REVIEW: APPROVED`
2. item status is `APPROVED`
3. no open blocker ids remain

### 12.9 Trace Linkage

1. Each review round should include decision/implementation trace ids when available.
2. Contested architecture-level disagreements move to `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md`.

## 13. Source Anchors

- A2A: https://a2a-protocol.org/latest/specification/
- A2A repo: https://github.com/a2aproject/A2A
- OpenClaw repo/docs: https://github.com/openclaw/openclaw
- Jarvis DeepWiki: https://deepwiki.com/ingpoc/jarvis
- Claude Agent SDK docs: https://platform.claude.com/docs/en/agent-sdk/overview
- Claude Agent SDK Python repo: https://github.com/anthropics/claude-agent-sdk-python
