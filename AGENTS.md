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
|need a diagram / architecture diagram → workflow/draw-io-diagram-generation.md
|local models / LM Studio / Foundation Models → workflow/local-models-integration.md
|principles:{agent-first.md,progressive-disclosure.md,determinism.md,token-efficiency.md}
|updating docs / storing bugs / context graph → workflow/context-learning-loop.md
|workflow:{openai-harness.md,vercel-agents-md.md,local-models-integration.md,context-learning-loop.md}
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

## Scripts

### Validation Scripts

Run these **before submitting changes** to ensure everything works:

| Script | When to Run | Purpose |
|--------|-------------|---------|
| `python3 scripts/validate_jarvis.py` | After any Python/Swift changes | Full validation: config, DB, ports, API lint |
| `python3 scripts/validate_local_models.py` | After local model changes | Validate AFM, LM Studio, WebSocket integration |
| `python3 scripts/test_local_models.py` | Debugging local models | Detailed end-to-end testing of models |
| `bash scripts/build_jarvis_app.sh` | After Swift changes | Clean Swift build with fresh DerivedData |

### Linting Scripts

| Script | When to Run | Purpose |
|--------|-------------|---------|
| `python3 scripts/jarvis_api_lint.py` | After API changes | Python API lint (21 files) |
| `python3 scripts/agent_docs_lint.py` | After doc changes | Agent docs lint |

### Local Models

| Script | When to Run | Purpose |
|--------|-------------|---------|
| `python3 scripts/test_local_models.py` | Testing AFM/LM Studio | Tests: AFM availability, LM Studio startup, WebSocket response |

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
