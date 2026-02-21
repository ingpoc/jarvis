# Jarvis Scripts Reference

## Startup / Runtime

| Script | When to Run | Purpose |
|--------|-------------|---------|
| `./start-jarvis.sh` | Normal startup | Starts daemon + menu bar (launchctl by default), auto-reloads stale LaunchAgent targets |
| `./stop-jarvis.sh` | Before restart / shutdown | Stops daemon, menu bar, optional tunnel |

## Validation Scripts

Run these **before submitting changes**:

| Script | When to Run | Purpose |
|--------|-------------|---------|
| `python3 scripts/validate_jarvis.py` | After any Python/Swift changes | Full validation: config, DB, ports, governance lint, API lint |
| `bash scripts/build_jarvis_app.sh` | After Swift changes | Clean Swift build with fresh DerivedData |

## Linting Scripts

| Script | When to Run | Purpose |
|--------|-------------|---------|
| `python3 scripts/jarvis_api_lint.py` | After API changes | Python API lint (21 files) |
| `python3 scripts/agent_docs_lint.py` | After doc changes | Agent docs lint + research gate + memory gate |
| `bash scripts/install_git_hooks.sh` | Once per clone/machine | Installs repo-managed hooks (`core.hooksPath=.githooks`) |

## Voice Runtime Dependencies (macOS)

| Dependency | Verify |
|------------|--------|
| `ffmpeg` on PATH | `ffmpeg -version` |

## Logs & Cache

| Path | Use |
|------|-----|
| `~/.jarvis/logs/daemon.log` | Runtime |
| `~/.jarvis/logs/menubar.log` | Menu bar app build/runtime |
| `~/.jarvis/logs/tunnel.log` | Localtunnel logs (when enabled) |
| `~/.jarvis/system/jarvis_config/.env` | Runtime environment file loaded by startup |
| `~/.jarvis/system/jarvis_config/a2a_token` | A2A auth token |
| `~/.jarvis/system/opencode_config/opencode.json` | OpenCode runtime config |

Clear bytecode cache after Python changes:

```bash
find src -name "*.pyc" -delete && find src -name "__pycache__" -type d -exec rm -rf {} +
```
