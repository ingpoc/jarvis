# Local Models Integration Guide

For Apple/MLX repo lookup strategy, use `../apple-mlx/README.md` first.

## Overview

Jarvis runtime no longer integrates the legacy local model-server path.

Current model execution paths:

1. **Foundation Models** - Direct Apple on-device AI via Python (`apple-foundation-models`)
2. **OpenCode** - External provider runtime (`opencode/*` model IDs)
3. **Anthropic-compatible remote providers** - Standard SDK path

## Architecture

### Files

| File | Purpose |
|------|---------|
| `src/jarvis/afm_integration.py` | Direct Apple Foundation Models Python integration |
| `src/jarvis/local_model_manager.py` | Local runtime coordinator (Foundation only) |
| `src/jarvis/opencode_client.py` | OpenCode HTTP client for task/chat execution |
| `src/jarvis/orchestrator/core.py` | Provider routing and execution-mode selection |
| `src/jarvis/ws_server.py` | Model status/switch API for menu bar |

### Routing Rules

- `provider_type=foundation` -> direct local execution (`_chat_local`, `_run_task_local`)
- `provider_type=opencode` -> OpenCode execution (`_chat_opencode`, `_run_task_opencode`)
- all other providers -> Claude Agent SDK path
- `origin=a2a` task execution is policy-forced to OpenCode (model override to `JARVIS_A2A_OPENCODE_MODEL` or `opencode/glm-5-free`)

## WebSocket Contract (Menu Bar)

### `get_model_status`

Request:

```json
{"action":"get_model_status"}
```

Response fields used by app:

```json
{
  "current_model": "opencode/minimax-m2.5-free",
  "provider": "opencode",
  "provider_type": "opencode",
  "foundation_available": true,
  "opencode_available_models": [
    "minimax-m2.5-free",
    "glm-5-free",
    "kimi-k2.5-free",
    "big-pickle",
    "openai/gpt-5-nano"
  ]
}
```

### `switch_model`

- `model="foundation-models"` -> activates local Foundation path
- `model` starting with `opencode/` or `opencode:` -> activates OpenCode path
- all other IDs -> remote Anthropic path

## Menu Bar Startup Guard (macOS)

`start-jarvis.sh` now enforces a stable launch target for menu bar:

- Builds Swift app (`swift build --package-path JarvisApp`)
- Syncs built binary into app bundle executable path
  - `JarvisApp/.build/debug/JarvisApp` -> `JarvisApp/.build/debug/JarvisApp.app/Contents/MacOS/JarvisApp`
- Validates byte-for-byte sync (`cmp -s`)
- Verifies `launchctl` program path matches expected app-bundle executable

This prevents stale/incorrect binary targets from causing menu bar crash loops.

## Configuration

`config.py` model provider types:

```text
anthropic | foundation | mlx | opencode
```

Notes:

- `mlx` remains reserved for future direct runtime work.
- OpenCode can use repo-local `opencode.json` for MCP registration (for example Zapier MCP).
- A2A-origin execution uses `permission_mode="bypassPermissions"` to reduce delegated-task approval deadlocks.
- OpenCode HTTP checks/calls are offloaded from the event loop in async paths to keep A2A polling responsive.
- OpenCode config now includes `context7`, `deepwiki`, `context-graph`, and `token-efficient` MCP entries for retrieval + learning workflows.

## Testing

```bash
# Validate runtime assumptions
python3 scripts/validate_local_models.py

# End-to-end local model checks
python3 scripts/test_local_models.py

# Verify model status payload manually
python -c "import asyncio, websockets, json; async def t():
    async with websockets.connect('ws://127.0.0.1:9847') as ws:
        await ws.send(json.dumps({'type':'command','id':'m1','action':'get_model_status','data':{}}))
        print(await ws.recv())
asyncio.run(t())"
```

## Gotchas

1. **Provider mismatch**: if `models.executor` is `opencode/...` but `provider_type` is not `opencode`, behavior may be inconsistent.
2. **Foundation availability**: requires macOS 26+ with Apple Intelligence enabled.
3. **OpenCode binary path**: daemon environment must include `JARVIS_OPENCODE_BIN` (defaulted in `start-jarvis.sh`).
4. **Menu bar target drift**: always restart through `./start-jarvis.sh`, not ad-hoc launches.
5. **Port ownership**: daemon serves WebSocket on `9847` and A2A on `9848`.
6. **Delegated task timeout defaults**: `JARVIS_OPENCODE_TIMEOUT_SECS` controls long task runtime; `JARVIS_OPENCODE_CHAT_TIMEOUT_SECS` controls chat timeout.
7. **URL-bearing delegated prompts**: orchestrator URL ingestion must be defensive when memory backend lacks `add_research_sources` (guarded in current code).

## Future Enhancements

1. Direct MLX provider implementation
2. Better provider health telemetry in menu bar
3. Provider-specific latency/cost panels in dashboard
