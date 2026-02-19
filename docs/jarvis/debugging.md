# Jarvis Debugging Guide

Common issues and fixes.

## WebSocket Message Format (Critical)

| Wrong | Correct |
|-------|---------|
| `{"action":"chat","message":"..."}` | `{"action":"chat","data":{"message":"..."},"id":"..."}` |

All actions must use the `data` wrapper.

## Log Locations

| Log | Path |
|-----|------|
| Daemon log | `~/.jarvis/logs/daemon.log` |
| Menu bar log | `~/.jarvis/logs/menubar.log` |
| Tunnel log (optional) | `~/.jarvis/logs/tunnel.log` |
| Database | `~/.jarvis/jarvis.db` |

## Event Verification

```sql
SELECT event_type, summary, timestamp
FROM timeline_events
ORDER BY timestamp DESC
LIMIT 10;
```

## Reliable Restart Sequence

```bash
./stop-jarvis.sh
./start-jarvis.sh
```

Verify service health with launchctl and ports:

```bash
launchctl print "gui/$(id -u)/com.jarvis.daemon" | rg "state =|pid ="
launchctl print "gui/$(id -u)/com.jarvis.menubar" | rg "state =|pid =|program =|successive crashes|last terminating signal"
lsof -n -P -iTCP:9847 -sTCP:LISTEN
lsof -n -P -iTCP:9848 -sTCP:LISTEN
```

Note: `start-jarvis.sh` can report a launchctl health timeout even when the service comes up a few seconds later. Confirm with `launchctl print` plus listening ports before declaring failure.

## Menu Bar Not Visible / Crash Loop

If daemon is healthy but no menu bar icon appears:

1. Confirm launchctl target and crash state:

```bash
launchctl print "gui/$(id -u)/com.jarvis.menubar" | rg "program =|state =|job state =|successive crashes|last terminating signal"
```

2. Confirm the target binary is the app-bundle executable:

```bash
launchctl print "gui/$(id -u)/com.jarvis.menubar" | rg "program ="
# Expected suffix:
# JarvisApp/.build/debug/JarvisApp.app/Contents/MacOS/JarvisApp
```

3. Restart cleanly:

```bash
./stop-jarvis.sh
./start-jarvis.sh
```

4. If needed, inspect latest crash report:

```bash
ls -1t ~/Library/Logs/DiagnosticReports | grep '^JarvisApp-.*\.ips$' | head -n 3
sed -n '1,160p' ~/Library/Logs/DiagnosticReports/<latest-file>.ips
```

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Missing 'message'` | Message at top level | Move to `data.message` |
| `Orchestrator not connected` | Daemon not running | Restart daemon |
| `Unknown action: send_voice` | Daemon not restarted after code update | Run `./stop-jarvis.sh && ./start-jarvis.sh` |
| Voice transcript generated but no reply | `send_voice` response path failing | Check `daemon.log` for `send_voice` response/error |
| Voice does not transcribe | `mlx-whisper` or `ffmpeg` missing | Install dependencies in project env |
| Events not broadcast | Wrong message format | Use `data` wrapper |

## Event Types Broadcast

| Event | When |
|-------|------|
| `chat_user` | User message received |
| `chat_assistant` | AI response generated |
| `chat_route` | Routing decision made |
| `chat_async_complete` | Background chat done |
| `chat_intent` | Intent decision emitted |
| `voice_command` | Voice input accepted |
| `tool_use` | Tool invocation |

## Pre-Test Checklist

- [ ] Message uses `{"action": "...", "data": {...}}` format
- [ ] Daemon running (`launchctl print gui/$(id -u)/com.jarvis.daemon`)
- [ ] Port 9847 listening (`lsof -i :9847`)
- [ ] Port 9848 listening (`lsof -i :9848`)

## Run Lint Before Testing

```bash
python3 scripts/jarvis_api_lint.py
```

## Voice Dependency Check (macOS)

```bash
.venv/bin/python -c "import mlx_whisper; print(mlx_whisper.__version__)"
ffmpeg -version
```
