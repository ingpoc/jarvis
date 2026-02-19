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
jarvis/
├── daemon.py          # Background service (port 9847)
├── ws_server.py       # WebSocket server
├── orchestrator/      # Message handling pipeline
│   └── core.py        # Main orchestrator
├── memory.py          # Vector store (ChromaDB)
├── model_router.py    # LLM routing (local/cloud)
├── mlx_inference.py   # Local MLX inference
├── config.py          # Configuration
└── self_learning.py   # Learning loops

scripts/
├── jarvis_api_lint.py # WebSocket format linter
└── test_ws_client.py  # WebSocket test client

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

- [ ] `stop-jarvis.sh` then `start-jarvis.sh` pass with clean logs
- [ ] Daemon WebSocket port listening
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

## Current Branch

`jarvis-ui-enhancement-log-viewer`
