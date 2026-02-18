# WebSocket API Reference

---

## Connection

```
ws://localhost:9847
```

---

## Message Format

All messages use this structure:

```json
{
  "action": "<action_name>",
  "data": { /* action-specific params */ },
  "id": "<optional_request_id>"
}
```

---

## Actions

### chat

Send a message to Jarvis.

```json
{
  "action": "chat",
  "data": {
    "message": "Hello Jarvis"
  },
  "id": "msg-001"
}
```

### run_task

Execute a task.

```json
{
  "action": "run_task",
  "data": {
    "task": "build the project"
  },
  "id": "task-001"
}
```

### get_status

Get daemon status.

```json
{
  "action": "get_status",
  "data": {},
  "id": "status-001"
}
```

### read_file

Read a file.

```json
{
  "action": "read_file",
  "data": {
    "path": "/path/to/file"
  },
  "id": "read-001"
}
```

---

## Response Format

```json
{
  "id": "<request_id>",
  "status": "success" | "error",
  "data": { /* response data */ },
  "error": "<error_message_if_any>"
}
```

---

## Events (Broadcast)

| Event | When | Data |
|-------|------|------|
| `chat_user` | User message | `{message}` |
| `chat_assistant` | AI response | `{message}` |
| `chat_route` | Routing decision | `{model, reason}` |
| `chat_async_complete` | Background done | `{message}` |
| `tool_use` | Tool invoked | `{tool, params}` |

---

## Error Handling

| Error Code | Meaning |
|------------|---------|
| 400 | Invalid message format |
| 404 | Action not found |
| 500 | Internal error |

---

## Lint Rule

Run before testing WebSocket changes:

```bash
python3 scripts/jarvis_api_lint.py
```

Checks:

- All actions have `data` wrapper
- Required fields present
- No top-level params
