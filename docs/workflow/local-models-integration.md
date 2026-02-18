# Local Model Integration Guide

## Overview

Jarvis supports 3 local model providers:

1. **Foundation Models** - Direct Apple on-device AI via Python
2. **LM Studio** - On-demand local model server with memory management
3. **MLX** - Direct MLX inference (future expansion)

## Architecture

### Files Created

| File | Purpose |
|------|---------|
| `src/jarvis/afm_integration.py` | Direct Apple Foundation Models Python integration (~1s latency) |
| `src/jarvis/lm_studio_manager.py` | On-demand LM Studio startup, auto-unload, memory management |
| `src/jarvis/local_model_manager.py` | Unified coordinator between providers |

### Key Design Decisions

1. **Memory Optimization**: LM Studio only starts when a model is selected
-unload**: Model2.**Auto unloads after 5 minutes idle to free RAM
2. **Direct Python**: Foundation Models uses direct Python package (no HTTP bridge)
3. **Provider Detection**: Model ID patterns determine provider type

## Implementation Details

### 1. AFM Integration (`afm_integration.py`)

```python
from jarvis.afm_integration import is_afm_available, generate

# Check availability
if is_afm_available():
    result = generate("What is 2+2?")
    # Returns: {"content": "4.", "latency_ms": 1130, "model": "apple-foundation-models"}
```

- Uses `apple-foundation-models` Python package directly
- No HTTP bridge needed - runs in-process
- Latency: ~1 second
- Available on macOS 26+ with Apple Intelligence enabled

### 2. LM Studio Manager (`lm_studio_manager.py`)

```python
from jarvis.lm_studio_manager import get_lm_studio_manager

lm = get_lm_studio_manager()

# On-demand startup
await lm.ensure_running()  # Starts LM Studio if not running

# Load model
await lm.load_model("qwen2.5-coder-3b-instruct-mlx")

# Auto-unload after idle
lm.record_usage()  # Resets idle timer

# Shutdown when done
await lm.stop()  # Stops LM Studio and frees RAM
```

**Memory Management:**

- Idle timeout: 300 seconds (5 minutes)
- Check interval: 30 seconds
- Auto-unloads model when idle
- Full process cleanup on stop

### 3. Local Model Manager (`local_model_manager.py`)

```python
from jarvis.local_model_manager import get_local_model_manager

mgr = get_local_model_manager()

# Switch between providers
await mgr.switch_model("foundation-models")  # Direct AFM
await mgr.switch_model("qwen2.5-coder-3b-instruct-mlx")  # LM Studio

# Generate
result = await mgr.generate("Hello")
```

**Provider Detection:**

```python
LM_STUDIO_MODEL_PATTERNS = [
    "qwen2.5-coder", "qwen3", "deepseek", "gpt-oss",
    "llama", "mistral", "phi", "gemma", "mixtral",
]

def get_provider_from_model(self, model_id: str) -> ModelProviderType:
    if model_id == "foundation-models":
        return ModelProviderType.FOUNDATION
    elif any(p in model_id.lower() for p in self.LM_STUDIO_MODEL_PATTERNS):
        return ModelProviderType.LMSTUDIO
    else:
        return ModelProviderType.ANTHROPIC
```

## Swift Menu Bar Integration

### WebSocket Protocol

**Request:**

```json
{"action": "get_model_status"}
```

**Response:**

```json
{
  "action": "get_model_status",
  "current_model": "claude-sonnet-4-5-20250929",
  "provider": "anthropic",
  "foundation_available": true,
  "mlx_available": false,
  "lmstudio_running": true,
  "lmstudio_model_loaded": "qwen2.5-coder-3b-instruct-mlx",
  "lmstudio_available_models": ["qwen2.5-coder-3b-instruct-mlx", ...]
}
```

### Swift Implementation

**ModelSelectionView.swift:**

- `foundationAvailable` - Default to `true` on macOS 26+
- Reads LM Studio status from WebSocket via `modelStatus`
- Model switching via `webSocket.sendCommand(action: "switch_model", data: [...])`

**WebSocketClient.swift:**

- Handles `get_model_status` response in `handleLegacyResponse`
- Stores in `modelStatus: ModelStatusInfo?`

**ModelStatusInfo.swift:**

```swift
struct ModelStatusInfo: Codable {
    let currentModel: String?
    let provider: String?
    let foundationAvailable: Bool?
    let lmstudioRunning: Bool?
    let lmstudioModelLoaded: String?
    let lmstudioAvailableModels: [String]?
}
```

## Configuration

### Environment Variables

```bash
# LM Studio (via .env)
ANTHROPIC_BASE_URL=http://localhost:1234
ANTHROPIC_AUTH_TOKEN=lmstudio

# Model Config (config.py)
models.provider_type: "anthropic" | "foundation" | "lmstudio" | "mlx"
```

### Port Configuration

| Service | Port |
|---------|------|
| LM Studio | 1234 |
| WebSocket (Jarvis) | 9847 |
| A2A Server | 9848 |

## Testing

```bash
# Test AFM availability
python -c "from jarvis.afm_integration import is_afm_available; print(is_afm_available())"

# Test LM Studio manager
python -c "
import asyncio
from jarvis.lm_studio_manager import get_lm_studio_manager
async def test():
    lm = get_lm_studio_manager()
    await lm.ensure_running()
    print('LM Studio running:', lm.is_running)
asyncio.run(test())
"

# Test WebSocket
python -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://127.0.0.1:9847') as ws:
        await ws.send(json.dumps({'action': 'get_model_status'}))
        print(await ws.recv())
asyncio.run(test())
"
```

## Orchestrator Architecture

CLI and menu bar use **separate orchestrator instances** — they do not share state at runtime.

```
CLI (jarvis run / jarvis chat)
    └─ new JarvisOrchestrator() per command  (cli.py:101, 172, 648)
       - ephemeral: dies when command finishes
       - reads config from disk at startup

Daemon (start-jarvis.sh → jarvis.daemon)
    └─ one JarvisOrchestrator (daemon.py:125)
       - persistent, long-lived
       - JarvisWSServer holds reference (daemon.py:165-168)
       - Menu bar → WebSocket :9847 → this orchestrator
```

**Implication for `switch_model`**: calling `switch_model` from the menu bar mutates the daemon's in-memory config and saves to disk. A subsequent CLI invocation will re-read the saved config from disk and pick up the local model setting correctly.

## Bugs Fixed (2026-02-18)

### Bug 1: `chat()` never checked `provider_type`

`chat()` in `orchestrator/core.py` went directly to `ClaudeSDKClient` regardless of `provider_type`. `run_task()` had the local model routing, `chat()` did not.

**Fix**: Added provider check + `_chat_local()` in `orchestrator/core.py`:

```python
# In chat(), after emitting chat_user event:
provider_type = getattr(self.config.models, "provider_type", "anthropic")
model_id = self.config.models.executor
if provider_type in ("foundation", "lmstudio"):
    return await self._chat_local(user_message, provider_type, model_id)
```

### Bug 2: `switch_model` used `loop.run_until_complete()` inside async context

The `switch_model` handler in `ws_server.py` called:

```python
# WRONG — raises RuntimeError: This event loop is already running
loop = asyncio.get_event_loop()
switch_result = loop.run_until_complete(local_mgr.switch_model(model))
```

`_handle_command()` is `async`, so calling `run_until_complete()` inside it throws silently. The `except` block returned `{"error": "..."}`, `provider_type` was never set to `"foundation"`, and every chat still hit the Anthropic API with the full tool list — producing:

```
API Error: 400 invalid_request_error — request.tools.21.input_schema.properties: Required
```

**Fix**: Replace with `await`:

```python
# CORRECT
switch_result = await local_mgr.switch_model(model)
```

**Rule**: Never call `loop.run_until_complete()` from inside an `async def`. Always `await` coroutines directly.

## Gotchas

1. **PYTHONPATH**: Swift Process doesn't inherit PYTHONPATH - use absolute paths
2. **macOS 26+**: Foundation Models requires macOS 26+ with Apple Intelligence
3. **LM Studio startup**: First model selection triggers on-demand startup (~10s)
4. **Memory**: LM Studio models use significant RAM - auto-unload prevents exhaustion
5. **Port conflicts**: 9847 for WebSocket, 9848 for A2A (different services)
6. **`run_until_complete()` inside async**: Raises `RuntimeError: This event loop is already running`. Always `await` coroutines inside async functions — never `loop.run_until_complete()`.
7. **Env var override stomps config**: `ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5` in `start-jarvis.sh` overwrites `config.models.executor` at load time. Switch model changes only survive if `provider_type` is also persisted (it is, as of the fix above).

## Verified End-to-End Test

```bash
# 1. Switch to Foundation Model via WebSocket
python3 -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://127.0.0.1:9847') as ws:
        await ws.send(json.dumps({'action': 'switch_model', 'data': {'model': 'foundation-models'}, 'id': 'sw'}))
        resp = json.loads(await ws.recv())
        print('switch:', resp.get('success'), resp.get('provider'))
asyncio.run(test())
"
# Expected: switch: True foundation

# 2. Chat via WebSocket (collect events until chat_assistant arrives)
python3 -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://127.0.0.1:9847') as ws:
        await ws.send(json.dumps({'action': 'chat', 'data': {'message': 'hi'}, 'id': 'c1'}))
        for _ in range(6):
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            etype = resp.get('data', {}).get('event_type', '')
            if etype == 'chat_assistant':
                print('reply:', resp['data']['summary'])
                break
asyncio.run(test())
"
# Expected: reply: Hello! ... (from Foundation Model, cost_usd=0.0)
```

## Future Enhancements

1. **MLX direct integration** - Currently LM Studio handles MLX models
2. **Model hot-swap** - Switch models without restart
3. **Memory monitoring** - Show RAM usage in menu bar
4. **Multiple local models** - Load different models for different tasks
