# Local Model Integration Guide

## Overview

Jarvis supports 3 local model providers:

1. **Foundation Models** - Direct Apple on-device AI via Python
2. **LM Studio** - On-demand local model server with memory management
3. **MLX** - Direct MLX inference (future expansion)

## Architecture

### Files

| File | Purpose |
|------|---------|
| `src/jarvis/afm_integration.py` | Direct Apple Foundation Models Python integration (~1s latency) |
| `src/jarvis/lm_studio_manager.py` | On-demand LM Studio startup, auto-unload, memory management |
| `src/jarvis/local_model_manager.py` | Unified coordinator between providers |

### Key Design Decisions

1. **Memory Optimization**: Models only load into memory when explicitly selected via menu bar
2. **Auto-unload**: Model unloads after 5 minutes idle to free RAM
3. **Direct Python**: Foundation Models uses direct Python package (no HTTP bridge)
4. **Provider Detection**: Model ID patterns determine provider type
5. **External-process-aware**: `is_api_available()` detects LM Studio regardless of who started it

## Implementation Details

### 1. AFM Integration (`afm_integration.py`)

```python
from jarvis.afm_integration import is_afm_available, generate

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

# Detects running LM Studio (Jarvis-managed or externally-started)
await lm.ensure_running()

# Loads model into memory via minimal inference request
await lm.load_model("qwen2.5-coder-3b-instruct-mlx")

# Resets idle timer
lm.record_usage()

# Stops LM Studio and frees RAM (Jarvis-managed only)
await lm.stop()
```

**Memory Management:**

- Idle timeout: 300 seconds (5 minutes)
- Check interval: 30 seconds
- Auto-unloads model when idle
- `unload_model()` guards on `_model_loaded`, not `is_running`

**Service Detection:**

```python
@property
def is_running(self) -> bool:
    """True only for Jarvis-managed process."""
    return self._process is not None and self._process.poll() is None

def is_api_available(self) -> bool:
    """True if LM Studio API is reachable — regardless of who started it."""
    try:
        req = urllib.request.Request(f"{LM_STUDIO_BASE_URL}/v1/models")
        urllib.request.urlopen(req, timeout=2)
        return True
    except Exception:
        return False
```

Use `is_running` to track Jarvis-owned processes. Use `is_api_available()` for all user-facing availability checks.

**Model Loading:**

`load_model()` sends a minimal valid inference request to trigger LM Studio to load the model:

```python
payload = json.dumps({
    "model": model_id,
    "messages": [{"role": "user", "content": "."}],
    "max_tokens": 1,
}).encode()
# Non-blocking — large models take 60–120s
await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=120))
```

LM Studio requires a valid request body (`messages` field mandatory) to trigger model loading.

### 3. Local Model Manager (`local_model_manager.py`)

```python
from jarvis.local_model_manager import get_local_model_manager

mgr = get_local_model_manager()

await mgr.switch_model("foundation-models")               # Direct AFM
await mgr.switch_model("qwen2.5-coder-3b-instruct-mlx")  # LM Studio

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
    elif "/" in model_id or any(p in model_id.lower() for p in self.LM_STUDIO_MODEL_PATTERNS):
        return ModelProviderType.LMSTUDIO
    else:
        return ModelProviderType.ANTHROPIC
```

## Swift Menu Bar Integration

### WebSocket Protocol

**get_model_status request/response:**

```json
{"action": "get_model_status"}
```

```json
{
  "current_model": "claude-sonnet-4-5-20250929",
  "provider": "anthropic",
  "foundation_available": true,
  "mlx_available": false,
  "lmstudio_running": true,
  "lmstudio_model_loaded": "qwen2.5-coder-3b-instruct-mlx",
  "lmstudio_available_models": ["qwen2.5-coder-3b-instruct-mlx", ...]
}
```

`lmstudio_running` = `lm_mgr.is_running or lm_mgr.is_api_available()` — detects externally-started instances.

### Swift Implementation

**ModelSelectionView.swift:**

- Sends `get_model_status` on `onAppear`
- Renders LM Studio model rows when `lmstudioAvailableModels` is non-empty
- Model switching via `webSocket.sendCommand(action: "switch_model", data: [...])`

**ModelStatusInfo (CodingKeys):**

```swift
struct ModelStatusInfo: Codable {
    let currentModel: String?           // "current_model"
    let provider: String?
    let foundationAvailable: Bool?      // "foundation_available"
    let lmstudioRunning: Bool?          // "lmstudio_running"
    let lmstudioModelLoaded: String?    // "lmstudio_model_loaded"
    let lmstudioAvailableModels: [String]?  // "lmstudio_available_models"
}
```

## Configuration

### Environment Variables

```bash
# Model Config (config.py)
models.provider_type: "anthropic" | "foundation" | "lmstudio" | "mlx"
```

### Port Configuration

| Service | Port |
| ------- | ---- |
| LM Studio | 1234 |
| WebSocket (Jarvis) | 9847 |
| A2A Server | 9848 |

## Testing

```bash
# Test AFM availability
python -c "from jarvis.afm_integration import is_afm_available; print(is_afm_available())"

# Test LM Studio detection (works for externally-started instances)
python -c "
import asyncio
from jarvis.lm_studio_manager import get_lm_studio_manager
async def test():
    lm = get_lm_studio_manager()
    print('is_running:', lm.is_running)
    print('is_api_available:', lm.is_api_available())
    print('available_models:', lm.available_models)
asyncio.run(test())
"

# Test get_model_status via WebSocket
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

```text
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

**Implication for `chat()`**: must check `provider_type` before routing. Both `chat()` and `run_task()` go through the same provider check — if `provider_type` is `foundation` or `lmstudio`, route to `_chat_local()` instead of the Claude SDK.

## Gotchas

1. **PYTHONPATH**: Swift Process doesn't inherit PYTHONPATH — use absolute paths
2. **macOS 26+**: Foundation Models requires macOS 26+ with Apple Intelligence enabled
3. **LM Studio startup**: If Jarvis starts LM Studio, first model selection takes ~10s
4. **Memory**: LM Studio models use significant RAM — auto-unload prevents exhaustion
5. **Port conflicts**: 9847 for WebSocket, 9848 for A2A (different services)
6. **`run_until_complete()` inside async**: Raises `RuntimeError: This event loop is already running` — always `await` coroutines directly inside `async def`
7. **Env var override**: `ANTHROPIC_DEFAULT_SONNET_MODEL` in `start-jarvis.sh` overwrites `config.models.executor` at load time — `provider_type` must also be persisted on switch
8. **`is_running` ≠ service available**: `is_running` tracks Jarvis-owned processes only — always use `is_api_available()` for user-facing checks
9. **`load_model()` requires valid request body**: LM Studio returns 422 without `messages` field — send minimal valid inference request to trigger loading
10. **Large model load timeout**: 20B+ models take 60–120s to load — use `run_in_executor` with `timeout=120`

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

# 2. Chat via WebSocket
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
