# Jarvis Conventions

Project-specific patterns and rules.

---

## Container Management

| Rule | Reason |
|------|--------|
| Use Apple Containers for execution | Isolated, safe |
| Mount project source with `--volume` | Persistent changes |
| Clean up after task | No zombie containers |

**Pattern**: `container_run` → `container_exec` → work → `container_stop`

---

## Git Workflow

| Rule | Reason |
|------|--------|
| Never force-push to main/master | Preserve history |
| Create new commits (never amend) | History integrity |
| Use HEREDOC for commit messages | Proper formatting |
| Pre-commit hooks always run | Quality gates |
| No `--no-verify` flag | No bypassing |

**Current identity**: openclaw-gurusharan / <gupta.huf.gurusharan@gmail.com>

---

## Tool Usage

| Tool | Use For |
|------|---------|
| Token-efficient MCP | Large file processing (98% savings) |
| Context7 MCP | Framework docs |
| DeepWiki MCP | GitHub repo docs |
| Browser automation | Headless Playwright in containers |

---

## Security Boundaries

| Level | Can | Cannot |
|-------|-----|--------|
| T2 (DEVELOPER) | Write code, run tests, git commits | Production deploys, CI/CD mods |
| NEVER | Deploy to production | Delete main branch |

---

## File Organization

```
src/jarvis/
├── daemon.py                  # Background service (port 9847 WS, 9848 A2A)
├── ws_server.py               # WebSocket API surface
├── orchestrator/              # Message handling pipeline
│   └── core.py                # Main orchestrator
├── local_model_manager.py     # AFM local runtime switching
├── afm_integration.py         # Apple Foundation Models integration
├── config.py                  # Configuration
└── self_learning.py           # Learning loops

scripts/
├── validate_jarvis.py         # Full project validation
├── validate_local_models.py   # Local models validation
├── test_local_models.py       # Local model integration smoke tests
└── jarvis_api_lint.py         # WebSocket format linter

tests/
├── test_model_router.py
├── test_orchestrator_handle_message.py
└── test_skill_generator.py
```

---

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `JARVIS_PORT` | 9847 | WebSocket port |
| `JARVIS_LOG_DIR` | ~/.jarvis/logs | Log location |
| `JARVIS_DB` | ~/.jarvis/jarvis.db | SQLite database |
| `JARVIS_WORKSPACE` | ~/.jarvis/workspaces | Root for Jarvis-created execution workspaces |
| `OPENCODE_CONFIG` | N/A (auto-discovered in workspace) | OpenCode runtime config |
| `JARVIS_A2A_TOKEN` | ~/.jarvis/system/jarvis_config/a2a_token | A2A auth token file |
| `VOYAGE_API_KEY` | {env} | Context Graph MCP |
| `ZAPIER_MCP_TOKEN` | {env} | Zapier MCP |

### Workspace Auto-Discovery

When OpenClaw spawns OpenCode in `~/.jarvis/workspaces/`:

1. Finds `opencode.json` → loads MCP servers + agents
2. Finds `AGENTS.md` → loads workspace rules
3. Loads `instructions` from opencode.json → loads IDENTITY.md, SOUL.md, PRINCIPLES.md

### Runtime Ownership

| Path | Owner | Mutability |
|------|-------|------------|
| `~/.jarvis/system/jarvis_config/*` | Human/operator | Immutable to delegated tasks |
| `~/.jarvis/system/opencode_config/*` | Human/operator | Immutable baseline runtime config |
| `~/.jarvis/runtime_workflow/*` | Jarvis | Mutable self-evolution docs/workflows |
| `~/.jarvis/workspaces/*` | Jarvis | Mutable task execution outputs |

---

---

## Jarvis-Core Mandatory Rules

| Rule | Reason |
|------|--------|
| Startup checks fail-fast | Abort with `FATAL` log if env cannot load |
| Launchd compatibility | Daemon must not depend on reading project files at runtime |
| Port cleanup safety | Kill only listeners (`-sTCP:LISTEN`), never all processes |
| Launchctl validation | Don't trust single PID; validate via service state + port readiness |

---

## Verification Standard

After startup or daemon lifecycle changes:

- [ ] `./stop-jarvis.sh` then `./start-jarvis.sh` completes, or service health is verified manually
- [ ] `launchctl print gui/$(id -u)/com.jarvis.daemon` reports running state
- [ ] Daemon WebSocket port 9847 and A2A port 9848 are listening
- [ ] Menu bar process running and connected

---

## Harness Governance (.agent)

| Rule | Enforcement |
|------|-------------|
| `.agent/ARCHITECTURE.md` | Stable, approved decisions only |
| `.agent/inflight-communication/` | Open items only |
| Promotion | When APPROVED, move to ARCHITECTURE.md |
| Progressive disclosure | Keep stable docs short |
| Governance lint | `python3 scripts/agent_docs_lint.py` |
| Research artifact gate | Enforces `research-evaluator` output sections in `docs/workflow/` |
| Memory gate | Enforces typed `memory/` structure + note schema + index coverage |

---

## Runtime Default

`start-jarvis.sh` defaults to `launchctl` for both daemon and menu bar:

- `JARVIS_DAEMON_START_MODE=launchctl`
- `JARVIS_MENUBAR_START_MODE=launchctl`

For delegated A2A execution:

- provider policy is `opencode_only`
- permission mode is `bypassPermissions`
