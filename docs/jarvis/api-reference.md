# WebSocket API Reference

## Connection

```text
ws://127.0.0.1:9847
```

## Message Format

All client requests use:

```json
{
  "action": "<action_name>",
  "data": {},
  "id": "optional-request-id"
}
```

Use the `data` wrapper for action parameters.

## Common Actions

| Action | Required `data` fields | Notes |
|--------|-------------------------|-------|
| `chat` | `message` | Non-blocking conversational chat |
| `message` | `message` | Alias of `chat` with intent event emission |
| `send_voice` | `text` | Voice transcript in, direct reply out |
| `run_task` | `description` | Optional `mode`: `pipeline` or default single-agent |
| `get_status` | none | Daemon/task/preflight status |
| `get_timeline` | none (optional `limit`) | Timeline events |
| `get_model_status` | none | Active model/provider plus local-model availability |
| `switch_model` | `model` | Persists model/provider selection |
| `read_file` | `file_path` | Reads local file content (truncated at 20k chars) |
| `run_tests` | none | Queues test task |
| `build_project` | none | Queues build task |

For full action list, see `src/jarvis/ws_server.py`.

## Voice Request Example

```json
{
  "action": "send_voice",
  "id": "voice-001",
  "data": {
    "text": "what is the status of my current work"
  }
}
```

## Response Format

Server responses include a wrapped payload and mirrored top-level fields:

```json
{
  "type": "response",
  "id": "voice-001",
  "action": "send_voice",
  "data": {
    "success": true,
    "reply": "Status is ...",
    "_meta": {
      "request_id": "voice-001",
      "action": "send_voice",
      "duration_ms": 812
    }
  },
  "success": true,
  "reply": "Status is ..."
}
```

If an action fails, `data.error` is populated.

## Broadcast Events

| Event | Meaning |
|-------|---------|
| `chat_user` | User message received |
| `chat_assistant` | Assistant response generated |
| `chat_route` | Routing/provider decision |
| `chat_async_complete` | Async response complete |
| `chat_intent` | Intent decision from `message` action |
| `voice_command` | Voice transcript accepted |
| `tool_use` | Tool invocation emitted by orchestrator |

## Lint Rule

Run after any WS contract change:

```bash
python3 scripts/jarvis_api_lint.py
```
