# Jarvis Roadmap (Finalized)

## Goal
Build Jarvis as a conversational agent that uses Claude Agent SDK to maximum effect, gets better every session, and improves its workflow autonomously using chat history + curated research inputs (including X bookmarks), without hiding failures.

## Product Principles
- Conversational by default: chat first, tools second.
- Fail fast, fully visible errors: no masking and no silent fallback.
- Memory as a system: preserve corrections, decisions, and outcomes.
- Controlled autonomy: Jarvis can propose and test workflow improvements, then promote only validated changes.

## P0 (Must Implement)
1. Conversational-first orchestration and intent router
- What to implement: route every incoming message through `chat -> intent classify -> (respond directly OR execute task/tools)`.
- Why high value: prevents accidental "hi" becoming full task runs; aligns UX with natural conversation.
- Benefit: lower unnecessary tool calls, better trust and usability.
- Acceptance: non-actionable messages never enqueue `run_task`; actionable prompts consistently produce tool-backed execution.

2. Deterministic task lifecycle and recovery
- What to implement: hard state machine `queued -> running -> success|failed|cancelled`, idempotent transitions, startup reconciler for stale `in_progress`.
- Why high value: removes ghost tasks and broken UI/task state after crashes or restarts.
- Benefit: reliable status in menu bar/full app/Slack, fewer operator interventions.
- Acceptance: daemon restart leaves zero orphan `in_progress` rows.

3. Hooks-based governance and auditable tool contract
- What to implement: standard hook-driven envelope for each tool call (`request_id`, `origin`, `timeout`, `exit_code`, `stderr`, `traceback`, `duration_ms`); block dangerous actions in `PreToolUse`; log outcomes in `PostToolUse`.
- Why high value: Claude Agent SDK hooks are the correct control point for safety, policy, and traceability.
- Benefit: every failure is diagnosable; policy enforcement is centralized.
- Acceptance: every tool invocation in timeline has correlation ID + terminal outcome.

4. Provider/model preflight before serving requests
- What to implement: startup checks for base URL, auth token, model names, tool-capable dry-run, and explicit health report.
- Why high value: prevents runtime "no textual error" failures from reaching users.
- Benefit: immediate configuration feedback and faster recovery.
- Acceptance: daemon refuses "ready" state on invalid model/provider config.

5. Slack reliability and anti-spam guardrails
- What to implement: queue + dedupe + cooldown + per-channel policy + 429 `Retry-After` handling + async ack path for Events API.
- Why high value: avoids channel spam and disabling from rate/failure thresholds.
- Benefit: stable Slack operation during idle and high message volume.
- Acceptance: no repeated duplicate posts; rate-limit events handled without user-visible flood.

6. Container execution policy: `job` vs `service`
- What to implement: explicit run modes and validation rules; if backend cannot support requested mode, fail with exact remediation and backend recommendation.
- Why high value: eliminates confusion around short-lived process exits and failed `exec`.
- Benefit: predictable container behavior and cleaner user expectations.
- Acceptance: container failures return mode-aware diagnostics, never ambiguous "stopped" only.

## P1 (Implement Next)
1. Memory architecture for continuous learning
- What to implement: global memory + project memory + decision-trace store + regression log, with periodic compaction.
- Why high value: turns past corrections into reusable precedent instead of re-debugging.
- Benefit: higher answer quality and lower token/tool churn over time.
- Acceptance: repeated classes of errors show increasing first-pass success.

2. Workflow optimization loop (autonomous but controlled)
- What to implement: idle loop that researches only new items (deduped), proposes workflow diffs, runs verification tasks, and promotes updates only on evidence.
- Why high value: converts research into measured improvements, not repetitive posting.
- Benefit: Jarvis improves process quality without spamming channels.
- Acceptance: each promoted workflow change includes test evidence and rollback path.

3. X bookmarks ingestion pipeline for research inputs
- What to implement: OAuth2 PKCE bookmark reader, scheduled sync, dedupe hash, "already reviewed" tracking, ranking, and channel-scoped conclusions.
- Why high value: gives Jarvis a durable research backlog instead of repeated links.
- Benefit: broader and fresher workflow ideas with memory of what was already learned.
- Acceptance: no duplicate research summaries for same bookmark revision.

4. Capability governance for MCP/subagents/skills
- What to implement: registry for dynamic additions with validation, health checks, permission scope, audit trail, and rollback.
- Why high value: safe extensibility is required for autonomous capability growth.
- Benefit: Jarvis can expand tools without destabilizing core operation.
- Acceptance: newly added MCP/skill appears in available-tools list only after passing health checks.

5. Conversation memory UX controls
- What to implement: save/edit/delete memories, scoped to personal/global/project, and explicit "save this correction" prompts.
- Why high value: keeps memory high signal and user-correctable.
- Benefit: better long-term accuracy without hidden memory drift.
- Acceptance: users can inspect and modify stored memory from app UI.

6. Skills-as-SOP library for repeatable engineering tasks
- What to implement: convert recurring workflows into versioned skills (setup, implementation, testing, review, deploy, rollback), with trigger criteria and anti-pattern notes.
- Why high value: stabilizes quality across sessions and reduces prompt variance.
- Benefit: fewer regressions and faster autonomous execution for repeated task classes.
- Acceptance: top recurring workflows execute through skill paths with measurable lower failure rate.

7. Eval-driven agent quality loop
- What to implement: maintain a regression suite of representative prompts/tasks; run before promoting workflow or memory changes.
- Why high value: prevents silent quality drift as Jarvis self-modifies.
- Benefit: safer autonomy and higher confidence in workflow updates.
- Acceptance: every promoted workflow change has pre/post eval results.

## P2 (Apple Native and Scale)
1. LaunchAgent-first single-instance runtime
- What to implement: one daemon and one menu bar owner via launchd/ServiceManagement, no extra terminal fan-out.
- Benefit: stable background lifecycle and predictable startup/shutdown.

2. Unified diagnostics surface
- What to implement: in-app diagnostics for WS health, task queue, model checks, container backend state, Slack delivery status, recent failures.
- Benefit: faster root-cause isolation.

3. Apple container backend maturity path + Docker fallback
- What to implement: explicit compatibility matrix and runtime backend selection policy.
- Benefit: reliable execution across workloads while Apple container ecosystem matures.

4. Sleep/wake and network transition hardening
- What to implement: reconnect strategy with state replay and pending request reconciliation.
- Benefit: fewer false-disconnects and dropped actions.

5. Minimal-tool surface with progressive disclosure
- What to implement: expose only required tools by default; unlock additional tools by intent/scope.
- Benefit: improved reliability and lower accidental misuse/tool noise.

## Research-Validated Notes (What changes from earlier drafts)
- Keep Claude Agent SDK primitives central: hooks, subagents, skills, MCP, and settings sources.
- Prefer goal-level prompting over over-prescriptive path instructions in autonomous workflows.
- Build a decision-trace memory (what was decided, why, and outcome), not just static notes.
- For Slack, design for rate/latency constraints from day one.
- For X research ingestion, use bookmarks API with OAuth scopes and dedupe; post conclusions only to research channel.

## Cross-Framework Principles Applied to Jarvis
- Skills should encode reusable SOPs, not long prompt prose.
- Keep reasoning and execution separate: chat/planning in agent layer, actions through explicit tool/shell contracts.
- Use layered context with compaction: metadata first, pull full details on demand.
- Preserve institutional memory as decision traces with outcomes, not raw logs.
- Treat agent quality like tests: run evals before promoting autonomous workflow changes.

## Source References
- [R1] Claude Agent SDK overview: https://platform.claude.com/docs/en/agent-sdk/overview
- [R2] Claude Agent SDK hooks: https://platform.claude.com/docs/en/agent-sdk/hooks
- [R3] Claude Agent SDK subagents: https://platform.claude.com/docs/en/agent-sdk/subagents
- [R4] Claude Agent SDK skills: https://platform.claude.com/docs/en/agent-sdk/skills
- [R5] Claude Agent SDK MCP: https://platform.claude.com/docs/en/agent-sdk/mcp
- [R6] Claude Code common workflows (parallel sessions/worktrees): https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/common-workflows
- [R7] Interactive tools in Claude: https://claude.com/blog/interactive-tools-in-claude
- [R8] Slack API rate limits: https://api.slack.com/apis/rate-limits
- [R9] Slack Events API reliability/rate behavior: https://api.slack.com/events-api
- [R10] Apple launchd guidance: https://support.apple.com/en-uz/guide/terminal/apdc6c1077b-5d5d-4d35-9c19-60f2397b2369/mac
- [R11] Apple container runtime tool: https://github.com/apple/container
- [R12] Apple Containerization package: https://github.com/apple/containerization
- [R13] Context graph thesis: https://foundationcapital.com/context-graphs-ais-trillion-dollar-opportunity/
- [R14] Inside OpenAI in-house data agent: https://openai.com/index/inside-our-in-house-data-agent/
- [R15] X Bookmarks API intro: https://developer.x.com/en/docs/x-api/tweets/bookmarks/introduction
- [R16] X Bookmarks integration details: https://developer.x.com/en/docs/x-api/tweets/bookmarks/integrate
