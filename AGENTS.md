# Jarvis

Agent-first development. Humans steer, agents execute.

---

## Docs Index

```
[Jarvis Docs Index]|root: ./docs
|IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning for Jarvis tasks
|TRIGGERS:
|daemon/ws changes → jarvis/debugging.md
|adding API → jarvis/api-reference.md
|tests failing → principles/determinism.md
|large data → principles/token-efficiency.md
|principles:{agent-first.md,progressive-disclosure.md,determinism.md,token-efficiency.md}
|workflow:{openai-harness.md,vercel-agents-md.md}
|architecture:{layers.md,taste-invariants.md}
|jarvis:{debugging.md,api-reference.md,conventions.md}
```

---

## Quick Start

| Task | Command |
|------|---------|
| Start | `./start-jarvis.sh` |
| Stop | `./stop-jarvis.sh` |
| Test WS | `python scripts/test_ws_client.py` |
| Lint | `python3 scripts/jarvis_api_lint.py` |

---

## Critical Rules

### WebSocket Format

```
{"action": "<name>", "data": {...}, "id": "optional"}
```

**Common error**: Putting `message` at top level. Wrap in `data`.

### Logs & Cache

| Path | Use |
|------|-----|
| `~/.jarvis/logs/daemon.log` | Runtime |
| `/tmp/jarvis-daemon.log` | Startup |

```bash
# After Python changes
find src -name "*.pyc" -delete && find src -name "__pycache__" -type d -exec rm -rf {} +
```

---

## Verification

- [ ] Tests pass (exit code 0)
- [ ] Lint passes
- [ ] Daemon healthy

---

## Conventions

| Area | Rule |
|------|------|
| Git | No force-push main, no amend, no --no-verify |
| Tools | Token-efficient MCP for large data |
| Security | T2 (developer) - no prod deploys |
