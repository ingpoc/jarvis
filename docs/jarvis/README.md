# Jarvis Index

Project-specific conventions and references.

| Document | Purpose | When to Use |
|----------|---------|-------------|
| [conventions.md](conventions.md) | Container, git, tools | Working in repo |
| [debugging.md](debugging.md) | Common issues, fixes | Debugging |
| [api-reference.md](api-reference.md) | WebSocket API | Integrating |
| [scripts.md](scripts.md) | Validation/build scripts | Verifying changes |
| [HOW_JARVIS_OPERATES.md](HOW_JARVIS_OPERATES.md) | End-to-end execution model | Architecture deep dive |
| [../workflow/openclaw-integration.md](../workflow/openclaw-integration.md) | OpenClaw gateway/channels/model/sandbox operations | OpenClaw runtime integration |
| [../workflow/openclaw-jarvis-integration.md](../workflow/openclaw-jarvis-integration.md) | OpenClaw plugin + routing setup for Jarvis delegation | OpenClaw ↔ Jarvis integration |
| [../workflow/local-models-integration.md](../workflow/local-models-integration.md) | Provider routing + OpenCode runtime behavior | Model/delegation runtime |

## Quick Start

```bash
# Start daemon + menu bar
./start-jarvis.sh

# Stop everything
./stop-jarvis.sh

# Full validation (recommended before commit)
python3 scripts/validate_jarvis.py

# A2A bridge helpers (for OpenClaw integration)
.venv/bin/python -m jarvis.cli a2a health -j
.venv/bin/python -m jarvis.cli a2a send "hello" --non-blocking -j
```

## Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Agent instructions |
| `AGENTS.md` | Same as CLAUDE.md (OpenAI compat) |
| `docs/` | Detailed documentation |
| `scripts/` | Utilities and linters |

## Runtime Home Layout (`~/.jarvis`)

```text
~/.jarvis/
├── system/
│   ├── jarvis_config/      # Human-managed runtime config (.env, config, launch env, A2A token)
│   │   ├── IDENTITY.md     # Who Jarvis is
│   │   ├── SOUL.md         # How Jarvis behaves
│   │   ├── PRINCIPLES.md   # Execution rules
│   │   └── a2a_token       # A2A authentication
│   └── opencode_config/    # OpenCode config (opencode.json)
├── runtime_workflow/       # Jarvis-managed workflow context
│   ├── AGENTS.md          # Global workspace rules
│   ├── .mcp.json          # MCP server config
│   └── docs/workflow/     # Detailed procedures
├── workspaces/            # Task workspaces created by Jarvis
│   ├── AGENTS.md          # Symlink → runtime_workflow/AGENTS.md
│   ├── opencode.json      # Symlink → system/opencode_config/opencode.json
│   ├── .mcp.json         # Symlink → runtime_workflow/.mcp.json
│   ├── docs/             # Symlink → runtime_workflow/docs
│   └── memory/           # Learning traces
├── logs/                  # daemon.log, menubar.log
├── pids/                  # process/service PID files
└── jarvis.db              # runtime database
```

## OpenCode Configuration

OpenCode loads from `~/.jarvis/workspaces/` with:

| File | Source | Purpose |
|------|--------|---------|
| `opencode.json` | `~/.jarvis/system/opencode_config/opencode.json` | MCP servers, agents, permissions |
| `AGENTS.md` | `~/.jarvis/runtime_workflow/AGENTS.md` | Workspace rules |
| Instructions | `~/.jarvis/system/jarvis_config/{IDENTITY,SOUL,PRINCIPLES}.md` | Identity loaded every session |

### Config Layers (MCP)

| Layer | Path | Owner | Rule |
|------|------|-------|------|
| Base MCP config | `~/.jarvis/system/opencode_config/opencode.json` (`mcp`) | Human-managed | Immutable source of truth |
| Dynamic MCP overlay | `~/.jarvis/workspaces/.opencode/.mcp.json` (`mcpServers`) | Jarvis-managed | Add/override/remove runtime MCP entries |
| Effective runtime MCP | `~/.jarvis/runtime_workflow/.mcp.json` (`mcpServers`) | Auto-generated | Derived at startup from base + overlay |

Startup behavior:
- Jarvis merges base + overlay into effective runtime MCP map.
- Jarvis should never need to edit base `opencode.json` for dynamic MCP additions.
- Do not hand-edit effective runtime `.mcp.json`; it is generated output.

### MCP Servers Configured

| Server | Type | Purpose |
|--------|------|---------|
| `context7` | local (npx) | Codebase search |
| `deepwiki` | remote | Documentation search |
| `context-graph` | local | Learning/trace storage |
| `token-efficient` | local | Large data processing |
| `zapier` | remote | Automation |

### Startup Drift Check

Run this quick verification after runtime/config changes:

```bash
# 1) Base config hash (track unexpected changes)
shasum -a 256 ~/.jarvis/system/opencode_config/opencode.json

# 2) Overlay presence/content
test -f ~/.jarvis/workspaces/.opencode/.mcp.json && cat ~/.jarvis/workspaces/.opencode/.mcp.json || echo "NO_OVERLAY"

# 3) Effective merged runtime keys
jq -r '.mcpServers | keys[]' ~/.jarvis/runtime_workflow/.mcp.json
```

## Self-Evolution Loop

```
1. Query Context Graph BEFORE: context_query_traces(query="...", category="...")
2. Execute task
3. On failure→fix: context_store_trace(decision, category, outcome)
4. On pattern (3+): generate draft rule
5. Human review → promote to AGENTS.md
6. Next session: better from learned patterns
```

See `docs/workflow/context-learning-loop.md` for details.

Operational rule:

- `system/*` is authoritative runtime config.
- `runtime_workflow/*` is where Jarvis self-evolves docs/workflows.
- `workspaces/*` is execution output (project worktrees, artifacts).

## Control Plane Tabs (App)

- `Workspace`: runtime config, activity, and canonical runtime paths
- `MCP`: OpenCode-discovered MCP server inventory
- `Skills`: OpenCode-discovered skill inventory
- `Tools`: OpenCode-discovered tool surfaces (with fallback)

## Jarvis Docs Maintenance Contract

- Jarvis should update workflow docs after non-trivial work or failure->fix paths.
- Keep `AGENTS.md` compressed and trigger-based.
- Put procedural details in `docs/workflow/*.md`.
- Load docs progressively:
  1. Start with `AGENTS.md` trigger/index.
  2. Open only relevant workflow doc(s).
  3. Load deeper references only if blocked.

Primary doc for this behavior:

- `docs/workflow/jarvis-autonomous-evolution.md`

## Architecture

```
src/jarvis/
├── daemon.py                  # Background service
├── ws_server.py               # WebSocket server (port 9847)
├── orchestrator/              # Message handling + routing
├── opencode_client.py         # OpenCode runtime bridge
└── a2a/server.py              # A2A server (port 9848)
```

## Voice Path (Current)

```
Voice tab (JarvisApp)
  -> VoiceRecorder (records + local Whisper transcription on macOS)
  -> WebSocket action: send_voice
  -> JarvisOrchestrator.handle_message(...)
  -> immediate reply payload
  -> app text-to-speech playback
```
