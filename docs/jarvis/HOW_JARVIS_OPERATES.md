# How Jarvis Operates

## Runtime Model

Jarvis runs in **OpenCode-only mode**.

- Task execution: `JarvisOrchestrator.run_task()` -> OpenCode runtime
- Chat execution: `JarvisOrchestrator.chat()` -> OpenCode runtime
- Pipeline mode: compatibility alias only (`run_pipeline()` delegates to `run_task()`)
- Provider enforcement: non-OpenCode model/provider inputs are normalized to OpenCode free defaults

## Entry Points

| Interface | Entry Point | Runtime |
|---|---|---|
| CLI | `jarvis run ...` | OpenCode |
| WebSocket | `run_task`, `chat`, `send_voice` actions | OpenCode |
| A2A | `POST /` (`message/send`, `tasks/get`, `tasks/cancel`) | OpenCode |
| NanoClaw bridge | A2A delegation | OpenCode |

## A2A Bridge

Jarvis A2A default endpoint is `http://127.0.0.1:9848`.

```bash
jarvis a2a health -j
jarvis a2a card -j
jarvis a2a send "review this repo" -j
jarvis a2a get <task-id> -j
jarvis a2a wait <task-id> --timeout 300 -j
jarvis a2a cancel <task-id> -j
```

## Mail Digest Path

Mail digest is deterministic/local logic over Zapier MCP retrieval.

- Retrieval: `ZapierMailClient`
- Digesting: `LocalMailDigestService` heuristics
- Model refinement: disabled in OpenCode-only runtime

## Trust, Budget, and Learning

Both chat/task paths still run through shared governance:

- Trust engine
- Budget controller
- Event timeline
- Context-file append
- Decision tracing and learning loop
