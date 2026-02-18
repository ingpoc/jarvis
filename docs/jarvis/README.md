# Jarvis Index

Project-specific conventions and references.

| Document | Purpose | When to Use |
|----------|---------|-------------|
| [conventions.md](conventions.md) | Container, git, tools | Working in repo |
| [debugging.md](debugging.md) | Common issues, fixes | Debugging |
| [api-reference.md](api-reference.md) | WebSocket API | Integrating |

## Quick Start

```bash
# Start daemon
./start-jarvis.sh

# Test WebSocket
python scripts/test_ws_client.py

# Run lint
python scripts/jarvis_api_lint.py
```

## Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Agent instructions |
| `AGENTS.md` | Same as CLAUDE.md (OpenAI compat) |
| `docs/` | Detailed documentation |
| `scripts/` | Utilities and linters |

## Architecture

```
jarvis/
├── daemon.py          # Background service
├── ws_server.py       # WebSocket server
├── orchestrator/      # Message handling
├── memory.py          # Vector store
└── model_router.py    # LLM routing
```
