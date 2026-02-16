# MISSION.md

Last updated: 2026-02-16

## Mission

Build Jarvis into a mac-native, continuously learning, highly autonomous, and RAM-efficient agent platform powered by Claude Agent SDK, where harness quality (state correctness, cancellation, observability, and policy control) is the primary performance multiplier, and OpenClaw interoperates as orchestrator through a reliable A2A contract.

## Strategic Objectives

1. Make Jarvis conversational by default while preserving deterministic execution contracts for long-running delegated tasks.
2. Establish Jarvis as a continuous learning engine: capture outcomes, extract patterns, validate, and promote only evidence-backed improvements.
3. Maximize Claude Agent SDK native capabilities (sessions, hooks, MCP, subagents, interrupt/cancel) before custom reimplementation.
4. Keep architecture modular with one shared execution core and thin protocol adapters (WS/Slack/CLI/A2A).
5. Maintain mac-native operational excellence: launchd lifecycle, resilient reconnect/recovery, and bounded RAM growth.
6. Keep OpenClaw integration configuration-first and protocol-correct through A2A.

## Product Outcomes

1. Jarvis can autonomously plan, implement, test, review, and report across coding workflows when policy permits.
2. Jarvis can execute non-coding workflows (research, analysis, monitoring) with structured outputs and explicit confidence/evidence.
3. Jarvis can continuously improve from mistakes and successes without degrading reliability or safety.
4. Jarvis can be delegated to from OpenClaw through stable A2A methods (`send/stream/get/cancel`) with clear state transitions.
5. Jarvis can use MCP servers, skills, and subagents in bounded, auditable, policy-governed ways.

## Engineering Principles

1. DeepWiki-first architecture research, official docs second, code validation third.
2. Harness-first engineering: fix state, cancellation, observability, and contracts before chasing model-level gains.
3. Progressive disclosure of context: inject only relevant, high-signal memory/patterns.
4. No hidden fallback behavior; fail fast with explicit remediation.
5. Policy gates (trust, budget, approvals) always control autonomy.
6. Learned patterns require eval/experiment evidence before promotion.
7. Decisions and outcomes are traceable in Context Graph.

## Quality Bar

1. Correctness with explicit, auditable state transitions across all ingress paths.
2. Low-latency conversational UX with non-blocking behavior for long operations.
3. Bounded memory growth for long-lived daemon sessions; no unbounded buffering.
4. Deterministic cancellation, recovery, and restart behavior.
5. Clear observability and structured diagnostics for users/operators.
6. Regression/eval checks protect against silent quality drift.

## Non-Negotiables

1. `.agent/ARCHITECTURE.md` contains only agreed/approved architecture decisions.
2. `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md` contains in-flight implementation/review tracking and unresolved items.
3. OpenClaw integration is configuration-first and protocol-correct.
4. Jarvis remains the execution engine; OpenClaw remains the orchestrator.
5. Continuous learning cannot bypass trust/budget/policy gates.
6. Research insights are never auto-adopted without validation evidence.
