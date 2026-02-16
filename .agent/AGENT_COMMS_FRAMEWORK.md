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
3. Keep one canonical decision per topic in `ANALYSIS.md`.
4. Keep only unresolved items in `.agent/ANALYSIS_IMPROVEMENT.md`.
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
   - Agreed -> `.agent/ANALYSIS.md`
   - Unresolved -> `.agent/ANALYSIS_IMPROVEMENT.md`
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
- `.agent/ANALYSIS.md`: agreed decisions only
- `.agent/ANALYSIS_IMPROVEMENT.md`: unresolved items only
- `.agent/AGENT_COMMS_FRAMEWORK.md`: operating framework (this file)

### Approval-Gated Updates (User Approval Required)

The following files must not be changed without explicit user approval:
1. `.agent/MISSION.md`
2. `.agent/AGENT_COMMS_FRAMEWORK.md`
3. Any major rewrite of `.agent/ANALYSIS.md` structure (not routine content additions)

Allowed without prior approval:
1. Add newly agreed decisions to `.agent/ANALYSIS.md`
2. Move unresolved/contested items to `.agent/ANALYSIS_IMPROVEMENT.md`
3. Add implementation progress details to `.agent/IMPLEMENTATION_PLAN.md`
4. Correct typos/formatting in `.agent/*` docs (no semantic changes)

### Codex + Claude Document Management Rules

1. `MISSION.md`:
   - stable north star
   - update only when product mission changes
   - requires user approval always
2. `AGENT_COMMS_FRAMEWORK.md`:
   - governs collaboration process and evidence policy
   - changes require user approval
3. `ANALYSIS.md`:
   - append/update only mutually agreed decisions
   - remove stale sections only if superseded and trace-linked
4. `ANALYSIS_IMPROVEMENT.md`:
   - only unresolved disagreements/open items
   - must be emptied when all open items are resolved
5. `IMPLEMENTATION_PLAN.md`:
   - operational execution plan tied to `ANALYSIS.md`
   - may be updated as phases complete, with decision traces

## 12. Implementation Review Workflow (Claude -> Codex)

This workflow is mandatory for architecture items tracked in `.agent/ANALYSIS.md`.

1. Claude responsibilities:
   - implement agreed architecture items in code
   - for each implemented item, update `.agent/ANALYSIS.md` and append status `READY FOR REVIEW`
   - include concise evidence under the item:
     - files changed
     - tests run
     - known limitations/open risk

2. Codex responsibilities:
   - review every item marked `READY FOR REVIEW`
   - record review result directly in `.agent/ANALYSIS.md` under the same item
   - use explicit verdict label:
     - `REVIEW: APPROVED`
     - `REVIEW: CHANGES REQUESTED`
   - when changes are requested, include concrete blockers and required fixes

3. Completion rule:
   - an implementation point is considered complete only after Codex review is recorded as `REVIEW: APPROVED` in `.agent/ANALYSIS.md`
   - if not approved, item remains open and stays out of the final "completed" set

4. Trace linkage:
   - each reviewed item must link to a decision/implementation trace id where applicable
   - contested review outcomes move to `.agent/ANALYSIS_IMPROVEMENT.md` until resolved

## 13. Source Anchors

- A2A: https://a2a-protocol.org/latest/specification/
- A2A repo: https://github.com/a2aproject/A2A
- OpenClaw repo/docs: https://github.com/openclaw/openclaw
- Jarvis DeepWiki: https://deepwiki.com/ingpoc/jarvis
- Claude Agent SDK docs: https://platform.claude.com/docs/en/agent-sdk/overview
- Claude Agent SDK Python repo: https://github.com/anthropics/claude-agent-sdk-python
