# ARCHITECTURE.md

Last updated: 2026-02-16
Source of truth: mutually agreed architecture between Agent A and Agent B.

## Scope

Jarvis is the system we are building. OpenClaw is an external orchestrator that delegates development work to Jarvis.

## Agreed Ground Truth

### A2A protocol facts (agreed)

1. Primary transport is HTTP + JSON-RPC 2.0.
2. Discovery uses `/.well-known/agent-card.json`.
3. Core methods needed for this project:
   - `message/send`
   - `message/stream`
   - `tasks/get`
   - `tasks/cancel`
4. `SendMessageConfiguration.blocking` must be supported for both modes.
5. Task states needed in Jarvis mapping:
   - `submitted`
   - `working`
   - `input_required`
   - `auth_required`
   - `completed`
   - `failed`
   - `canceled`
   - `rejected`

### OpenClaw facts (agreed)

1. OpenClaw does not natively expose A2A server/client as first-class runtime protocol.
2. OpenClaw should integrate with Jarvis through A2A client tools.
3. OpenClaw remains orchestration/UI/channel layer; Jarvis remains execution engine.

### Jarvis current-state facts (agreed)

1. Jarvis already has mature execution core (Claude Agent SDK + hooks + MCP tools).
2. Jarvis currently exposes WS/Slack/CLI interfaces, but not native A2A server.
3. Jarvis has robust event/timeline/memory surfaces that can back A2A task and stream responses.

## Jointly Agreed Architecture

1. Jarvis is a **Claude Agent SDK-first execution platform** with protocol adapters.
2. OpenClaw integrates with Jarvis via **A2A** (client -> Jarvis server).
3. Jarvis keeps one shared execution core; WS/Slack/CLI/A2A are thin ingress adapters.
4. Policy enforcement (trust/budget/tool permissions) is centralized in SDK hooks.
5. Failures must be explicit, structured, and correlated across protocol boundaries.

## Target System Layout

```text
Ingress Adapters
- WS (menu bar/full app)
- Slack bridge
- CLI
- A2A HTTP server
        │
        ▼
Protocol-Neutral Core
- SessionManager (ClaudeSDKClient continuity/pooling)
- TaskEngine (sync + async task lifecycle)
- HookPolicyEngine (PreToolUse/PostToolUse)
- AgentTeamEngine (planner/executor/tester/reviewer when needed)
        │
        ▼
Capability Plane
- MCP servers (container/git/browser/review/context)
- Dynamic capability registry
        │
        ▼
State/Observability
- MemoryStore + TaskStore mapping
- EventCollector (single canonical event bus)
- StructuredError + correlation IDs
```

## A2A Integration Decisions

1. Jarvis exposes native A2A HTTP endpoint on a separate port from WS.
2. Use A2A SDK/server framework rather than custom JSON-RPC plumbing.
3. Implement A2A core methods first:
   - `message/send`
   - `message/stream`
   - `tasks/get`
   - `tasks/cancel`
4. Support both `blocking=false` and `blocking=true`.
5. Advertise only implemented capabilities in AgentCard.
6. Keep A2A ingress as adapter only; no business logic fork from WS/Slack/CLI.

## Protocol Mapping (Agreed)

### Task state mapping

1. Internal task created -> `submitted`
2. Internal in-progress -> `working`
3. Trust/approval pending -> `input_required`
4. Auth/provider credential needed -> `auth_required`
5. Success -> `completed`
6. Runtime/model/tool failure -> `failed`
7. Cancellation path invoked -> `canceled`
8. Policy budget/trust refusal before execution -> `rejected`

### Result and artifact mapping

1. Execution summary text -> task summary artifact.
2. Test/build output -> text artifacts.
3. Git metadata (branch/commit/PR URL) -> structured data artifact.
4. Container diagnostics/log snippets -> text artifact.

### Streaming mapping

1. Emit task lifecycle updates over `message/stream`.
2. Emit intermediate artifacts for progress visibility.
3. Emit terminal state explicitly with correlation id.

## Claude Agent SDK Optimization Decisions

1. Use persistent `ClaudeSDKClient` sessions with explicit lifecycle management.
2. Add interrupt-driven cancellation for long-running tasks.
3. Keep hooks as the single policy gate for all ingress paths.
4. Keep single-pass conversational default; escalate to multi-agent team flow only for complex tasks.
5. Normalize all outcomes into a stable internal result schema shared by WS/Slack/A2A.
6. Reuse SDK-native tool/MCP integration primitives instead of duplicating execution logic per adapter.

## macOS Native Decisions

1. launchd-supervised service lifecycle remains mandatory.
2. Unified event stream powers both menu bar and full app.
3. Container runtime failures are fail-fast and explicit.
4. Health/crash telemetry is surfaced to UI with actionable detail.
5. A2A service lifecycle must be managed alongside existing daemon services.

## Security and Error Contract (Agreed)

1. No hidden fallback paths.
2. Structured error envelope across layers:
   - `layer`: `discovery` | `auth` | `transport` | `task` | `runtime`
   - `code`: protocol/HTTP/runtime code
   - `message`: actionable text
   - correlation fields (`context_id`, `task_id`, request id)
3. Auth model in AgentCard must reflect actual enforcement.
4. Side-effecting operations must carry dedupe/correlation metadata.

## Implementation Sequence (Agreed)

1. Add A2A dependencies in `pyproject.toml`.
2. Implement AgentCard builder.
3. Implement A2A executor and task-store adapter over existing MemoryStore.
4. Add A2A server app and daemon startup integration.
5. Add A2A state mapping (`submitted`, `working`, `input_required`, `auth_required`, `completed`, `failed`, `canceled`, `rejected`).
6. Add SSE streaming and artifact mapping.
7. Add OpenClaw delegation tools (`a2a_delegate`, `a2a_poll_task`, `a2a_cancel_task`).
8. Add conformance and end-to-end integration tests.

## Refactor Priorities (Agreed)

1. Split orchestration responsibilities into smaller modules:
   - session management
   - task engine
   - hook policy
   - capability registry
   - ingress routing
2. Introduce protocol-neutral domain models:
   - `TurnRequest`
   - `TurnResult`
   - `TaskHandle`
   - `StructuredError`
3. Keep WS/Slack/A2A as translators over one shared core API.

## Invariants

1. No hidden fallback paths.
2. No ingress-specific policy forks.
3. No protocol adapter bypassing core execution logic.
4. All side-effecting calls carry correlation and dedupe metadata.

## Primary References

- <https://a2a-protocol.org/latest/specification/>
- <https://a2a-protocol.org/latest/definitions/>
- <https://github.com/a2aproject/A2A>
- <https://github.com/openclaw/openclaw>
- <https://platform.claude.com/docs/en/agent-sdk/python>
- <https://github.com/anthropics/claude-agent-sdk-python>

## DeepWiki Validation Snapshot

Validated against DeepWiki repository docs:

1. `ingpoc/jarvis`:
   - Confirms dual-layer design (Swift macOS app + Python daemon).
   - Confirms orchestration responsibilities currently centered in `JarvisOrchestrator`.
   - Confirms Claude Agent SDK integration via `ClaudeSDKClient`, hooks, dynamic agents, and MCP servers.
   - Confirms macOS-native stack: menu bar app, launchd lifecycle, notifications, Apple container integration.

2. `anthropics/claude-agent-sdk-python`:
   - Confirms strong support for long-lived conversation sessions, hooks, custom tools/MCP, resource control, and session continuity.
   - Confirms `ClaudeSDKClient.interrupt()` method exists for task cancellation.
   - Confirms session forking, file checkpointing, and additional hooks (SubagentStart/Stop, PreCompact, etc.) that Jarvis should utilize.
   - Supports the agreed direction to make Jarvis core SDK-first and adapter-thin.

3. `openclaw/openclaw`:
   - Confirms best external-agent integration path is a plugin-provided custom tool capability.
   - Supports using OpenClaw as orchestrator and Jarvis as delegated execution agent over A2A.

---

## DeepWiki-Informed Decisions (Newly Agreed)

### SDK Cancellation Strategy

Both agents agree:

1. Jarvis must implement SDK `ClaudeSDKClient.interrupt()` support for A2A `tasks/cancel` compliance.
2. Store active `ClaudeSDKClient` instances per task for cancellation capability.
3. Keep `asyncio.TimeoutError` as fallback for hung SDK/CLI processes.
4. Implementation pattern:

```python
self._active_tasks: dict[str, ClaudeSDKClient] = {}

async def cancel_task(self, task_id: str) -> bool:
    client = self._active_tasks.get(task_id)
    if client:
        await client.interrupt()
        return True
    return False
```

### Session Management Strategy

Both agents agree:

1. Current single `_chat_client` shared across channels causes context bleeding.
2. Fix: Per-channel `ClaudeSDKClient` instances keyed by channel origin.
3. No "session pool" complexity needed — SDK's `resume` parameter handles continuity.
4. Implementation pattern:

```python
self._chat_clients: dict[str, ClaudeSDKClient] = {}

async def _get_client_for_channel(self, origin: str) -> ClaudeSDKClient:
    if origin not in self._chat_clients:
        self._chat_clients[origin] = ClaudeSDKClient(options=self._build_options())
        await self._chat_clients[origin].connect()
    return self._chat_clients[origin]
```

### Message vs Task Routing (Resolved)

Both agents agree on contract-first routing:

1. `blocking=false`: Always return `Task` immediately, run in background.
2. `blocking=true`: Run synchronously, return `Message` (conversational) or `Task` (work).
3. No keyword heuristics or model-tool-inspection for routing decisions.
4. The `blocking` flag alone determines the contract.

### Refactor Priority Order (Agreed)

Both agents agree on this priority sequence:

1. **FIRST:** Add SDK `interrupt()` support (A2A compliance blocker)
2. **SECOND:** Implement `JarvisAgentExecutor` with proper async handling
3. **THIRD:** Per-channel session clients (fix context bleeding)
4. **FOURTH:** Add A2A task state mapping to MemoryStore
5. **FIFTH:** Extract shared hooks to `jarvis_hooks.py` (eliminate duplication between orchestrator.py and agents.py)
6. **SIXTH:** Split orchestrator if still >1000 lines after above

### SDK Features to Utilize (Backlog)

Both agents agree these SDK features should be utilized, prioritized by A2A requirements:

| Priority | SDK Feature | A2A Relevance |
|----------|-------------|---------------|
| **Critical** | `interrupt()` | Required for `tasks/cancel` |
| **High** | `can_use_tool` callback | Fine-grained tool policy |
| **High** | `SubagentStart/Stop` hooks | Pipeline lifecycle tracking |
| **Medium** | `fork_session=True` | Alternative exploratory workflows |
| **Medium** | `enable_file_checkpointing` | Rollback capability |
| **Low** | `PreCompact` hook | Conversation compaction control |
| **Low** | `bypassPermissions` mode | T4 autonomous mode |

### OpenClaw Integration Details (Agreed)

Both agents agree:

1. OpenClaw integration uses **custom tools**, not a channel plugin.
2. Tools required: `a2a_delegate`, `a2a_poll_task`, `a2a_cancel_task`, `a2a_discover`.
3. OpenClaw's `sessions_spawn` model is process-local; A2A requires HTTP client — different architecture.
4. Packaging can be single plugin package later; tools first for rapid iteration.

## Open Question Resolutions (Promoted)

These were open questions in `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md` and are now promoted as accepted decisions.

### 1) A2A port policy

Decision:

1. Use default fixed port `9848`.
2. Support override via `JARVIS_A2A_PORT`.
3. AgentCard endpoint URL must reflect the effective runtime port.

### 2) A2A auth bootstrap

Decision:

1. Auto-generate bearer token on first run.
2. Store in `~/.jarvis/a2a_token` with strict file permissions.
3. Allow override through `JARVIS_A2A_TOKEN`.
4. Return explicit 401/403 on auth failure with structured error metadata.

### 3) Default trust tier for A2A callers

Decision:

1. Default A2A caller trust tier is T1.
2. Allow per-caller overrides via `a2a.caller_tiers`.
3. Denials must include explicit required-tier reason.

### 4) Multi-workspace strategy

Decision:

1. Use explicit `contextId -> workspace` mapping as primary mechanism.
2. If mapping is missing, use deterministic instance default workspace fallback.
3. Keep auto-discovery disabled by default.

### 5) Session forking policy

Decision:

1. Do not enable `fork_session` by default in v1.
2. Allow explicit opt-in for exploratory/speculative requests.
3. When used, include fork lineage in trace metadata.

## Continuous Learning Engine Decisions (Promoted from USER_WORKSPACE)

### Learning Pipeline (Required)

Jarvis continuous learning loop must follow:

1. Capture: task/tool/result events with correlation ids.
2. Reflect: derive root-cause/prevention patterns from failures and high-signal successes.
3. Store: persist typed patterns (not raw prompt transcripts).
4. Retrieve: relevance-rank patterns per task context.
5. Apply: inject minimal high-signal guidance (progressive disclosure).
6. Validate: measure outcome deltas and update pattern confidence.

### Pattern Schema (Required Fields)

Each pattern record must include:

1. `pattern_id`
2. `type`: `failure | success | heuristic | research`
3. `scope`: `global | project | task-class`
4. `trigger_signature`
5. `recommendation`
6. `confidence`
7. `evidence`
8. `first_seen`, `last_seen`, `frequency`
9. `status`: `active | deprecated | rejected`

### Research Adoption Policy

1. Research inputs are deduped and structured before use.
2. No automatic adoption of research claims.
3. Promotion requires eval/experiment evidence and confidence threshold.
4. Low-confidence patterns stay inactive.

### Progressive Disclosure Policy

1. Inject metadata-first, then only top relevant patterns.
2. Enforce cap on injected patterns/research items.
3. Avoid bulk memory dumps into prompts.

### Configuration Decisions (Required)

Add/standardize config groups:

1. `learning.*` (enablement, confidence thresholds, decay/deprecation policy)
2. `context.*` (progressive disclosure limits and relevance thresholds)
3. `runtime.*` (memory guard and long-task streaming expectations)
4. `a2a.*` (already agreed: port/auth/caller tier/context workspace mapping)

### Priority Alignment

Before advanced reflection/research workers:

1. fix cancellation/state correctness
2. ensure A2A contract reliability
3. ensure session isolation
4. then scale continuous-learning features

## Implementation And Review Tracking

Implementation/review status is tracked in `.agent/inflight-communication/ANALYSIS_IMPROVEMENT.md` to keep this document focused on agreed/approved architecture decisions.
