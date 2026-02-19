# Jarvis Scripts Reference

## Validation Scripts

Run these **before submitting changes**:

| Script | When to Run | Purpose |
|--------|-------------|---------|
| `python3 scripts/validate_jarvis.py` | After any Python/Swift changes | Full validation: config, DB, ports, governance lint, API lint |
| `python3 scripts/validate_local_models.py` | After local model changes | Validate AFM, LM Studio, WebSocket integration |
| `python3 scripts/test_local_models.py` | Debugging local models | Detailed end-to-end testing of models |
| `bash scripts/build_jarvis_app.sh` | After Swift changes | Clean Swift build with fresh DerivedData |

## Linting Scripts

| Script | When to Run | Purpose |
|--------|-------------|---------|
| `python3 scripts/jarvis_api_lint.py` | After API changes | Python API lint (21 files) |
| `python3 scripts/agent_docs_lint.py` | After doc changes | Agent docs lint + research gate + memory gate |
| `bash scripts/install_git_hooks.sh` | Once per clone/machine | Installs repo-managed hooks (`core.hooksPath=.githooks`) |

## Local Models

| Script | When to Run | Purpose |
|--------|-------------|---------|
| `python3 scripts/test_local_models.py` | Testing AFM/LM Studio | Tests: AFM availability, LM Studio startup, WebSocket response |

## Logs & Cache

| Path | Use |
|------|-----|
| `~/.jarvis/logs/daemon.log` | Runtime |
| `/tmp/jarvis-daemon.log` | Startup |

Clear bytecode cache after Python changes:

```bash
find src -name "*.pyc" -delete && find src -name "__pycache__" -type d -exec rm -rf {} +
```
