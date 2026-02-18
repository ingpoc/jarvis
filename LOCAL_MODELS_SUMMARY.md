# Local Models Integration - Summary

## What Was Implemented

### 1. New Python Modules

| File | Purpose |
|------|---------|
| `src/jarvis/afm_integration.py` | Direct Apple Foundation Models integration (~1s latency) |
| `src/jarvis/lm_studio_manager.py` | LM Studio on-demand startup, auto-unload, memory management |
| `src/jarvis/local_model_manager.py` | Unified coordinator between providers |

### 2. Swift Menu Bar Changes

- `JarvisApp/Sources/JarvisApp/Views/ModelSelectionView.swift` - Model selection UI with provider status
- `JarvisApp/Sources/JarvisApp/Models/JarvisStatus.swift` - Added ModelStatusInfo fields
- `JarvisApp/Sources/JarvisApp/WebSocketClient.swift` - Handle get_model_status response

### 3. Configuration Changes

- `src/jarvis/config.py` - Added `provider_type` field to ModelConfig
- `src/jarvis/ws_server.py` - Added switch_model handler with config persistence
- `src/jarvis/orchestrator/core.py` - Added `_run_task_local()` for local model execution

### 4. Scripts Created

| Script | Purpose |
|--------|---------|
| `scripts/validate_local_models.py` | Validate AFM, LM Studio, WebSocket |
| `scripts/test_local_models.py` | Detailed end-to-end testing |
| `scripts/build_jarvis_app.sh` | Clean Swift build |

### 5. Documentation

- `docs/workflow/local-models-integration.md` - Complete integration guide
- Updated `AGENTS.md` and `CLAUDE.md` with scripts reference

---

## How It Works

### Architecture

```
Menu Bar (Swift)
    |
    v
WebSocket (port 9847) --> ws_server.py
    |
    v
local_model_manager.py --> afm_integration.py (Foundation)
                       --> lm_studio_manager.py (LM Studio)
```

### Provider Detection

- `foundation-models` → Direct AFM Python package
- `/` or `qwen` or `deepseek` in model ID → LM Studio
- Otherwise → Claude Agent SDK (Anthropic)

### Memory Management

- LM Studio starts **on-demand** (first model request)
- Model auto-unloads after **5 minutes idle**
- Full cleanup when switching providers

---

## Issues — RESOLVED (2026-02-18)

### ~~Issue 1: Foundation Model Selection Not Persisting~~ ✅ FIXED

**Was**: After selecting "Foundation Model" in menu bar and saying "hi", got:

```
API error: 400 invalid_request_error - tools.21.input_schema.properties: Required
```

**Root cause**: Two bugs combined:

1. **`switch_model` (ws_server.py)** called `loop.run_until_complete(local_mgr.switch_model(model))` inside an `async def`, which raises `RuntimeError: This event loop is already running`. The config's `provider_type` was never set to `"foundation"`. The exception was silently swallowed by the outer `except` block.

2. **`chat()` (orchestrator/core.py)** had no `provider_type` check — it always routed to `ClaudeSDKClient` regardless.

**Fixes applied**:

- `ws_server.py`: replaced `loop.run_until_complete(...)` with `await local_mgr.switch_model(model)`
- `orchestrator/core.py`: added provider check in `chat()` + new `_chat_local()` method

See `docs/workflow/local-models-integration.md` → "Bugs Fixed" for full details.

---

## Testing Commands

```bash
# Test AFM directly
python3 -c "
import asyncio
from jarvis.local_model_manager import get_local_model_manager
async def test():
    mgr = get_local_model_manager()
    await mgr.switch_model('foundation-models')
    result = await mgr.generate('say hi')
    print(result['content'])
asyncio.run(test())
"

# Check WebSocket status
python3 -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://127.0.0.1:9847') as ws:
        await ws.send(json.dumps({'action': 'get_model_status'}))
        print(json.dumps(json.loads(await ws.recv()), indent=2))
asyncio.run(test())
"

# Run validation
python scripts/validate_local_models.py
```

---

## Files Modified

1. `src/jarvis/afm_integration.py` (NEW)
2. `src/jarvis/lm_studio_manager.py` (NEW)
3. `src/jarvis/local_model_manager.py` (NEW)
4. `src/jarvis/config.py` - Added provider_type
5. `src/jarvis/ws_server.py` - Added switch_model handler
6. `src/jarvis/orchestrator/core.py` - Added _run_task_local(), provider detection in_build_options
7. `JarvisApp/Sources/JarvisApp/Views/ModelSelectionView.swift` - UI updates
8. `JarvisApp/Sources/JarvisApp/Models/JarvisStatus.swift` - Added fields
9. `JarvisApp/Sources/JarvisApp/WebSocketClient.swift` - Handle response
10. `AGENTS.md` - Updated scripts reference
11. `CLAUDE.md` - Updated scripts reference

---

## Next Steps (for debugging AI)

1. Make `chat()` method in `orchestrator/core.py` check `provider_type` and call local model
2. Or route through `run_task()` instead of `chat()` for local models
3. Ensure Foundation Model returns proper response format
