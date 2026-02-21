# OpenClaw + Jarvis Integration

Use this guide to make OpenClaw route execution tasks to Jarvis over A2A.

Standalone OpenClaw runtime operations (gateway/channels/model auth/sandbox/pairing) are documented in `openclaw-integration.md`.

## OpenClaw Research Verdict (2026-02-19)

**Source**:
- https://docs.openclaw.ai/tools/plugin
- https://docs.openclaw.ai/plugins/manifest
- https://docs.openclaw.ai/tools/skills
- https://deepwiki.com/search/in-openclaw-plugin-sdk-what-is_bc3719fb-c94e-4d4d-b1ce-4dadc70f9062
- https://deepwiki.com/search/for-openclaw-gateway-cli-openc_1e7e5607-d143-4c32-bd18-9b0b1160520b

**Score**: 11/12 — **Adopt**

| Dimension | Score | Notes |
|-----------|-------|-------|
| Novelty | 2/3 | Plugin/gateway model is known, but direct Jarvis A2A delegation pattern is new in this stack |
| Relevance | 3/3 | Directly solves current need: OpenClaw routes, Jarvis executes coding tasks |
| Claim validity | 3/3 | Verified by live calls: `openclaw gateway call jarvis.codeTask` delegates and returns completed A2A tasks |
| Implementation cost | 3/3 | Hours-level additive integration; no core architecture rewrite |
| Total | 11/12 | Adopt |

### Claims Analysis

| Claim | Agree? | Evidence | Notes |
|-------|--------|----------|-------|
| `registerGatewayMethod` handler args come from `params` | Yes | DeepWiki + live behavior | Using `payload` caused empty inputs; switching to `params` fixed call path |
| `openclaw gateway call --params` maps to plugin handler params | Yes | DeepWiki + successful `jarvis.codeTask` calls | Confirmed end-to-end with structured JSON params |
| OpenClaw can route coding tasks to external executor over gateway/plugin | Yes | Live plugin run | Verified with `OPENCLAW_JARVIS_OK` and code-generation task |
| Non-Anthropic fallback is needed when Anthropic subscription is exhausted | Yes | Runtime test evidence | Use `opencode` provider (or `foundation` for lightweight local turns) to keep delegation operational |

## Goal

- Keep OpenClaw as channel/router and research conductor.
- Delegate execution-heavy tasks to Jarvis (`http://127.0.0.1:9848`) using A2A token auth.
- Prevent repeated research loops by persisting a research/work ledger in workspace memory.
- For large multi-stream engineering work, use the parallel execution pattern in `docs/workflow/opencode-parallel-worktrees.md`.

## Recommended Operating Split

| Work type | Primary runtime | Why |
|-----------|------------------|-----|
| Discovery research (agent harness trends, market scan, doc lookup) | OpenClaw (Perplexity/Browser/Context7) | Faster source collection, native MCP access |
| Execution-heavy tasks (coding/refactor/repo implementation, long procedural tasks) | Jarvis via A2A | Better implementation loop and local model routing controls |
| Session continuity and dedupe | OpenClaw MEMORY + daily logs + research ledger | Avoid re-researching the same topic and preserve next-step queue |

## What was implemented in this repo

- Plugin source: `integrations/openclaw/jarvis-bridge`
- Tool (preferred): `jarvis_delegate_task`
- Tool (legacy alias): `jarvis_code_task`
- Gateway RPC method: `jarvis.codeTask`
- Gateway RPC method (preferred): `jarvis.delegateTask`
- Command: `/jarvis <task>`
- Skill: `jarvis-coder` (deterministic `/jarvis-coder <task>` for coding)
- Skill: `jarvis-chief` (deterministic `/jarvis-chief <task>` for general delegation)

## Continuous Research Rollout (2026-02-20)

OpenClaw was upgraded from passive heartbeat-only behavior to scheduled research intake + execution delegation.

### Enabled runtime features

- Plugins enabled: `jarvis-bridge`, `mcp-bridge`, `slack`, `lobster`, `llm-task`
- Plugin staged but disabled: `thread-ownership` (requires a reachable slack-forwarder ownership API)
- Tool policy expanded to permit scheduling/workflow surfaces:
  - allow includes `group:automation`, `cron`, `lobster`, `llm-task`
  - high-risk surfaces (`group:runtime`, `group:fs`, `group:web`, `nodes`) remain denied

### Scheduled research jobs

Created via `openclaw cron add`:

1. `research-harness-scan` every 6h
2. `research-openai-anthropic-updates` every 6h
3. `research-indian-stocks-scan` every 12h

All jobs target `session=main` with `wake=next-heartbeat` and system-event payloads that enforce:

- dedupe check against research ledger before new research
- explicit verdict (`Adopt/Adapt/Skip`)
- queue + memory update after each cycle

### Workspace control files refactored

In OpenClaw workspace (`/Users/gurusharan/Documents/remote-claude/Research/clawdbot/workspace`):

- `SOUL.md`
- `MEMORY.md`
- `AGENTS.md`
- `HEARTBEAT.md`
- `TOOLS.md`
- `PRINCIPLES.md`
- `BOOT.md`
- `UPDATE.md`
- `references/source-watchlist.md`
- `references/research-ledger.md`
- `references/jarvis-work-queue.md`

Net effect: continuous research intake, anti-loop memory discipline, and explicit research-to-execution handoff to Jarvis.

### Operational caveat observed

`openclaw` gateway RPC calls can intermittently return `1006` closure in this environment; a quick `openclaw gateway health` call before cron/gateway operations stabilizes command reliability.

## OpenClaw Runtime Failures (Reference)

For standalone OpenClaw runtime recovery (sandbox/pairing/auth/slack), follow:

- `docs/workflow/openclaw-integration.md`

## OpenClaw Workspace Files To Use Intentionally

| File | Role in this vision |
|------|---------------------|
| `AGENTS.md` | Primary operating rules and delegation contract (what to do first each session) |
| `SOUL.md` | Tone/persona constraints only; avoid putting tactical workflow here |
| `USER.md` | User preferences and communication style |
| `TOOLS.md` | Tool routing policy (OpenClaw-native research vs Jarvis delegation) |
| `HEARTBEAT.md` | Continuous work loop and heartbeat checklist |
| `MEMORY.md` | Durable long-term patterns and stable decisions |
| `memory/YYYY-MM-DD.md` | Day-level running log and recent outcomes |
| `PRINCIPLES.md` | Concise non-negotiables and anti-loop rules |
| `references/research-ledger.md` | Dedupe register for research scopes/results/review dates |
| `references/jarvis-work-queue.md` | Backlog of execution tasks that should be delegated to Jarvis |

Notes from docs + runtime behavior:

- Subagent bootstrap is minimal (`AGENTS.md` + `TOOLS.md`), so critical routing rules must be present there.
- `PRINCIPLES.md` is custom (not a built-in injected file), so ensure `BOOT.md` explicitly points to it.
- Keep `HEARTBEAT.md` short and action-oriented to avoid token waste.

## OpenClaw Update Ownership Map

When updating OpenClaw behavior, change the owner file first:

| Change type | Owner file/location | Why |
|-------------|---------------------|-----|
| Bridge runtime behavior (JSON-RPC, wait/polling, task flow) | `integrations/openclaw/jarvis-bridge/index.ts` | Source of truth for tool/gateway behavior |
| Bridge config defaults/schema | `integrations/openclaw/jarvis-bridge/openclaw.plugin.json` | Default values and allowed ranges |
| Bridge operator instructions | `integrations/openclaw/jarvis-bridge/README.md` | Human-facing plugin usage |
| OpenClaw command behavior (`/jarvis-chief`, `/jarvis-coder`) | `integrations/openclaw/jarvis-bridge/skills/*/SKILL.md` | Deterministic skill routing and task shaping |
| OpenClaw live workspace operating rules | `/Users/gurusharan/Documents/remote-claude/Research/clawdbot/workspace/AGENTS.md` | Session contract actually read by OpenClaw |
| OpenClaw tool routing policy | `/Users/gurusharan/Documents/remote-claude/Research/clawdbot/workspace/TOOLS.md` | Runtime tool-choice policy |
| OpenClaw startup reads/health checks | `/Users/gurusharan/Documents/remote-claude/Research/clawdbot/workspace/BOOT.md` | Boot-time control plane |
| OpenClaw workflow docs index | `/Users/gurusharan/Documents/remote-claude/Research/clawdbot/workspace/docs/workflow/README.md` | Compressed trigger-based docs routing |
| OpenClaw queue + dedupe memory | `/Users/gurusharan/Documents/remote-claude/Research/clawdbot/workspace/references/{research-ledger.md,jarvis-work-queue.md}` | Durable anti-loop continuity |
| Integration-level policy in this repo | `docs/workflow/openclaw-jarvis-integration.md` | Canonical cross-repo playbook |

Verification after updates:

1. `openclaw plugins list --json` shows expected `workspaceDir` and `jarvis-bridge` source path.
2. `openclaw config get plugins.entries.jarvis-bridge.config --json` matches expected defaults.
3. Run one direct RPC smoke test with `jarvis.delegateTask`.

## Recommended OpenClaw config

```json5
{
  plugins: {
    allow: ["jarvis-bridge", "slack", "mcp-bridge"],
    load: {
      paths: [
        "/Users/gurusharan/Documents/remote-claude/Codex/jarvis-mac/integrations/openclaw/jarvis-bridge",
      ],
    },
    entries: {
      "jarvis-bridge": {
        enabled: true,
        config: {
          baseUrl: "http://127.0.0.1:9848",
          tokenPath: "~/.jarvis/system/jarvis_config/a2a_token",
          defaultWait: false,
          defaultTimeoutSec: 18000,
          pollIntervalMs: 1000,
        },
      },
    },
  },
  tools: {
    // Keep OpenClaw surface constrained and route coding via plugin tool.
    profile: "minimal",
    allow: ["group:plugins", "group:sessions", "group:messaging"],
    deny: ["group:runtime", "group:fs", "group:web", "group:ui", "cron", "gateway", "nodes"],
  },
}
```

## Verification checklist

1. `openclaw plugins list` shows `jarvis-bridge` as `loaded`.
2. `openclaw skills info jarvis-coder` shows eligible/loaded.
3. `.venv/bin/python -m jarvis.cli a2a health -j` returns `status: ok`.
4. In OpenClaw chat: `/jarvis-coder refactor auth middleware` delegates to Jarvis.
5. In OpenClaw chat: `/jarvis-chief audit this repo and propose refactor plan` delegates to Jarvis.
6. Optional explicit command path: `/jarvis add retries to HTTP client`.
6. Direct RPC check:
   - `openclaw gateway call jarvis.delegateTask --params '{"task":"Reply with exactly: OPENCLAW_JARVIS_OK","wait":true}' --timeout 180000 --json`
   - Expect `final.status: completed` and `final.result: OPENCLAW_JARVIS_OK`.

## Delegation Reliability Notes (2026-02-20)

- Prefer non-blocking bridge default (`defaultWait: false`) and explicitly set `wait: true` only for bounded tasks.
- For long implementation work, split into atomic steps with completion markers (`DONE_STEP1`, `DONE_STEP2`, ...).
- Keep coding delegation on OpenCode:
  - `models.provider_type=opencode`
  - `models.executor=opencode/<model>`
- OpenClaw/A2A delegated tasks are runtime-forced to OpenCode provider in Jarvis (menu-bar chat provider switching remains independent).
- If a delegated task stays `working` without `updatedAt` movement, cancel and re-submit a smaller step.

### Workspace Rule Sync Checklist

Ensure OpenClaw workspace control files mirror runtime behavior:

- `AGENTS.md`: preferred RPC examples should default to non-blocking (`wait:false`) and mention step markers.
- `TOOLS.md`: route implementation-heavy work via `jarvis_delegate_task` / `jarvis.delegateTask`.
- `BOOT.md`: includes `AGENTS.md`, `TOOLS.md`, and ledgers in startup reads.
- `references/jarvis-work-queue.md`: track atomic delegated steps and checkpoints.

### Follow-up Session Continuity (OpenClaw -> Jarvis -> OpenCode)

Best-practice resume contract:

1. OpenClaw persists per-scope `jobId -> {contextId, opencodeSessionId}` in `~/.openclaw/jarvis-bridge-jobs.json`.
2. Follow-ups should reuse `jobId` (or `followUp=true`) so `contextId` stays stable.
3. If available, pass `resumeSessionId` to A2A `message/send` so OpenCode resumes even after daemon restart.
4. Jarvis still keeps an in-memory `channel_id -> session_id` map for fast same-process resumes.

### Dynamic MCP Overlay (Jarvis Self-Managed)

MCP source of truth is split intentionally:

1. Immutable base (human-managed): `~/.jarvis/system/opencode_config/opencode.json` (`mcp` section).
2. Mutable overlay (Jarvis-managed): `~/.jarvis/workspaces/.opencode/.mcp.json` (`mcpServers` section).
3. Effective runtime map (auto-generated on startup): `~/.jarvis/runtime_workflow/.mcp.json`.

Merge rule:

- Runtime `mcpServers = base(opencode.json.mcp enabled) + overlay(.opencode/.mcp.json)`.
- Overlay can add/override entries.
- Overlay can remove base entries with `{"disabled": true}` on that server key.
- Do not hand-edit `~/.jarvis/runtime_workflow/.mcp.json`; it is generated output and will be overwritten on startup.

### OpenClaw-Owned Context Graph Loop

OpenClaw should maintain its own continuity graph in addition to flat ledgers.

Minimum contract:

1. Before starting non-trivial work, query prior traces for similar scope:
   - `context_query_traces(query=\"...\", category=\"...\")`
2. After each non-trivial failure->fix or design decision, store a trace:
   - `context_store_trace(decision=\"...\", category=\"...\", outcome=\"success|failure\")`
3. After rollout validation, update outcome on pending traces:
   - `context_update_outcome(trace_id=\"...\", outcome=\"success|failure\")`

Recommended category map:

- `research`: source verdicts and adoption decisions
- `workflow`: routing/dedupe/automation decisions
- `delegation`: Jarvis task-shaping and timeout behavior
- `error`: concrete failure signatures and fixes

AGENTS/TOOLS/BOOT implications:

- `AGENTS.md`: must require query-before-new-work and store-after-non-trivial-fix.
- `TOOLS.md`: must include context-graph tools in preferred evidence/memory path.
- `BOOT.md`: should include a quick context-graph readiness check in startup routine.

## Coding Model Selection (Anthropic Exhausted)

For coding tasks delegated from OpenClaw, run Jarvis on OpenCode:

```bash
.venv/bin/python -m jarvis.cli config models.executor=opencode/default
.venv/bin/python -m jarvis.cli config models.provider_type=opencode
bash ./stop-jarvis.sh
bash ./start-jarvis.sh
```

Why: if `provider_type=anthropic` while subscription is exhausted, delegated tasks can fail upstream before execution.

### Register Zapier MCP in OpenCode

For OpenCode-backed mail access, keep runtime OpenCode config at `~/.jarvis/system/opencode_config/opencode.json`:

```json
{
  "mcp": {
    "zapier": {
      "type": "remote",
      "enabled": true,
      "url": "https://mcp.zapier.com/api/v1/connect",
      "headers": {
        "Authorization": "Bearer {env:ZAPIER_MCP_TOKEN}"
      }
    }
  }
}
```

Then set `ZAPIER_MCP_TOKEN` in Jarvis daemon env (`~/.jarvis/system/jarvis_config/.env`) and restart Jarvis.

## Operational notes

- `openclaw update` can succeed while service restart fails; run `openclaw gateway restart` manually.
- If gateway service is not installed: `openclaw gateway install` then `openclaw gateway start`.
- `openclaw security audit --deep --json` should be part of periodic checks.

## Hardening notes observed

- Prefer explicit `plugins.allow` to trust-pin only required plugins.
- Review custom/global plugins (`~/.openclaw/extensions/*`) before enabling.
- Avoid inline secrets in config where possible; prefer token files or env variables.

## References

- OpenClaw plugins: https://docs.openclaw.ai/tools/plugin
- Plugin manifest: https://docs.openclaw.ai/plugins/manifest
- Skills: https://docs.openclaw.ai/tools/skills
- Slash commands and skill dispatch: https://docs.openclaw.ai/tools/slash-commands
- Tool profiles: https://docs.openclaw.ai/tools
- Configuration reference: https://docs.openclaw.ai/gateway/configuration-reference
