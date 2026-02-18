# IMPLEMENTATION_PLAN.md

Last updated: 2026-02-16
Source architecture: `.agent/ARCHITECTURE.md`

## 1. Goal

Execute the agreed Jarvis architecture with clear phase gates, measurable checks, and rollback-safe delivery.

## 2. Execution Phases

## Phase 0: Baseline and Guardrails

Objectives:
1. Lock baseline behavior and current regressions.
2. Add metrics hooks for memory/latency/error visibility.

Deliverables:
1. Baseline test run snapshot.
2. Runtime health checklist for daemon/WS/menu bar.
3. Correlation ID propagation checklist.

Gate to exit:
1. Baseline recorded and reproducible.
2. No unknown failing tests in core paths.

## Phase 1: A2A Core Enablement

Objectives:
1. Add native A2A server support to Jarvis.
2. Implement contract methods required by `.agent/ARCHITECTURE.md`.

Deliverables:
1. AgentCard endpoint.
2. A2A `message/send`, `message/stream`, `tasks/get`, `tasks/cancel`.
3. Port and auth config:
   - default port `9848` + `JARVIS_A2A_PORT`
   - token bootstrap + `JARVIS_A2A_TOKEN` override

Gate to exit:
1. Local A2A round-trip works with auth.
2. Blocking and non-blocking request modes validated.

## Phase 2: SDK-Native Reliability

Objectives:
1. Implement interrupt-based cancellation.
2. Isolate session continuity by channel/context.

Deliverables:
1. Active-task client registry + `interrupt()` cancellation path.
2. Per-channel/session client strategy.
3. Structured error envelope with layer/code/message/correlation.

Gate to exit:
1. Cancel requests stop running tasks deterministically.
2. No cross-channel context bleed.

## Phase 3: State and Streaming Quality

Objectives:
1. Align internal task state model with A2A lifecycle.
2. Improve streaming/artifact quality.

Deliverables:
1. State mapping support:
   - `submitted`, `working`, `input_required`, `auth_required`,
   - `completed`, `failed`, `canceled`, `rejected`
2. SSE status/event streaming.
3. Artifact mapping for summary/test/build/git/container outputs.

Gate to exit:
1. Lifecycle state transitions are consistent and auditable.
2. Stream reconnect/retry behavior validated.

## Phase 4: OpenClaw Integration Configuration

Objectives:
1. Make OpenClaw -> Jarvis communication deterministic and policy-safe.

Deliverables:
1. Configuration guide for OpenClaw tools:
   - `a2a_delegate`
   - `a2a_poll_task`
   - `a2a_cancel_task`
   - `a2a_discover`
2. Routing and trust-envelope config examples.
3. Correlation/logging propagation examples.

Gate to exit:
1. OpenClaw can delegate and receive completion reliably.
2. Error propagation remains explicit end-to-end.

## Phase 5: Refactor and Scale

Objectives:
1. Reduce orchestration coupling.
2. Prepare for additional autonomous capabilities.

Deliverables:
1. Orchestrator decomposition:
   - session manager
   - task engine
   - hook policy
   - capability registry
   - ingress router
2. Protocol-neutral core models (`TurnRequest`, `TurnResult`, `TaskHandle`, `StructuredError`).

Gate to exit:
1. No behavior regression across adapters.
2. Module-level tests added for extracted components.

## Phase 6: Continuous Learning Engine

Objectives:
1. Implement structured learning pipeline from execution outcomes.
2. Add research/heuristic promotion gates with measurable evidence.

Deliverables:
1. Learning pipeline stages:
   - capture -> reflect -> store -> retrieve -> apply -> validate
2. Pattern schema implementation with required fields:
   - id/type/scope/trigger/recommendation/confidence/evidence/timestamps/frequency/status
3. Config groups:
   - `learning.*` (enablement, thresholds, decay/deprecation)
   - `context.*` (progressive disclosure limits/relevance threshold)
   - `runtime.*` memory guard + long-task streaming requirement
4. Reflection flow:
   - generate pattern candidates from terminal task/tool outcomes
   - keep low-confidence candidates inactive
5. Research adoption flow:
   - dedupe sources
   - structured claim extraction
   - eval/experiment gate before promotion

Gate to exit:
1. Repeated failure classes show measurable first-pass improvement.
2. No unbounded memory/context growth during soak runs.
3. Promoted patterns are evidence-linked and reversible.
4. Learning loop cannot bypass trust/budget/policy gates.

## 3. Acceptance Check Matrix

| Area | Check | Pass Criteria |
|---|---|---|
| A2A Discovery | AgentCard fetch | Valid card, correct endpoint/auth declaration |
| A2A Send | `blocking=false` | Immediate task response, async execution continues |
| A2A Send | `blocking=true` | Deterministic terminal/interrupted response |
| A2A Tasks | `tasks/get` | Accurate status and metadata |
| A2A Cancel | `tasks/cancel` | Running task is interrupted and marked canceled |
| Auth | bad/missing token | Explicit 401/403 structured error |
| WS/Slack | conversational latency | Quick acknowledgement for long operations |
| Memory | daemon RSS trend | No unbounded growth during soak run |
| Reliability | restart/recovery | Daemon restarts cleanly; connections re-establish |
| Observability | error correlation | request/context/task ids present across logs/events |
| Learning | pattern promotion | every promoted pattern has confidence + evidence link |
| Learning | disclosure limits | injected pattern/research counts stay within configured caps |
| Learning | memory control | long-run memory/context stays bounded with decay/deprecation |

## 4. Test Plan (Minimum)

1. Unit tests:
   - state mapping
   - policy decisions
   - auth/token bootstrap
2. Integration tests:
   - A2A send/stream/get/cancel
   - WS + A2A coexistence
3. Soak tests:
   - repeated long-running tasks
   - repeated cancel/retry
   - repeated learning-cycle promotion/deprecation
4. Recovery tests:
   - daemon restart mid-task
   - client reconnect behavior
5. Learning tests:
   - pattern extraction from failure/success events
   - retrieval scoring and capped injection
   - research claim promotion blocked without eval evidence

## 5. Change Management

1. Each phase requires:
   - decision trace stored in Context Graph
   - update to `.agent/ARCHITECTURE.md` if architecture shifts
2. Unresolved items:
   - keep in `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md` only
3. No silent fallback additions.

## 6. Immediate Next Actions

1. Implement Phase 1 scaffolding (A2A app + AgentCard + config).
2. Add Phase 1 integration tests.
3. Run and capture baseline metrics before Phase 2 changes.
4. Add Phase 6 data model scaffolding (`learning` config + pattern schema table).
