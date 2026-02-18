# Jarvis Debugging Guide

Common issues and fixes.

---

## WebSocket Message Format (CRITICAL)

| Wrong | Correct |
|-------|---------|
| `{"action": "chat", "message": "..."}` | `{"action": "chat", "data": {"message": "..."}, "id": "..."}` |

**All messages MUST use `data` wrapper** for action parameters.

### Actions Requiring Data Wrapper

chat, run_task, message, read_file, git_status, build_project, run_tests

---

## Log Locations

| Log | Path |
|-----|------|
| Daemon log | `~/.jarvis/logs/daemon.log` |
| Startup log | `/tmp/jarvis-daemon.log` |
| Database | `~/.jarvis/jarvis.db` |

---

## Event Verification

```sql
SELECT event_type, summary, timestamp
FROM timeline_events
ORDER BY timestamp DESC
LIMIT 10;
```

---

## Bytecode Cache Issues

After modifying Python files:

```bash
find src -name "*.pyc" -delete && \
find src -name "__pycache__" -type d -exec rm -rf {} +
```

---

## Daemon Restart Sequence

```bash
# Kill existing
kill $(pgrep -f "jarvis.daemon")
sleep 2

# Start fresh
nohup .venv/bin/python -m jarvis.daemon > /tmp/jarvis-daemon.log 2>&1 &
sleep 3

# Verify
ps aux | grep jarvis.daemon
```

---

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Missing 'message'` | Message at top level | Move to `data.message` |
| `Orchestrator not connected` | Daemon not running | Restart daemon |
| Events not broadcast | Wrong message format | Use `data` wrapper |
| `'MemoryStore' has no attribute` | Stale bytecode | Clear `__pycache__` |

---

## Event Types Broadcast

| Event | When |
|-------|------|
| `chat_user` | User message received |
| `chat_assistant` | AI response generated |
| `chat_route` | Routing decision made |
| `chat_async_complete` | Background chat done |
| `tool_use` | Tool invocation |

---

## Pre-Test Checklist

- [ ] Message uses `{"action": "...", "data": {...}}` format
- [ ] Daemon running (`ps aux | grep jarvis.daemon`)
- [ ] Port 9847 listening (`lsof -i :9847`)
- [ ] Bytecode cache cleared after code changes

---

## Run Lint Before Testing

```bash
python3 scripts/jarvis_api_lint.py
```
