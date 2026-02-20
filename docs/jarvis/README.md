# Jarvis Index

Project-specific conventions and references.

| Document | Purpose | When to Use |
|----------|---------|-------------|
| [conventions.md](conventions.md) | Container, git, tools | Working in repo |
| [debugging.md](debugging.md) | Common issues, fixes | Debugging |
| [api-reference.md](api-reference.md) | WebSocket API | Integrating |
| [scripts.md](scripts.md) | Validation/build scripts | Verifying changes |
| [HOW_JARVIS_OPERATES.md](HOW_JARVIS_OPERATES.md) | End-to-end execution model | Architecture deep dive |
| [../workflow/openclaw-jarvis-integration.md](../workflow/openclaw-jarvis-integration.md) | OpenClaw plugin + routing setup | OpenClaw integration |

## Quick Start

```bash
# Start daemon + menu bar
./start-jarvis.sh

# Stop everything
./stop-jarvis.sh

# Full validation (recommended before commit)
python3 scripts/validate_jarvis.py

# A2A bridge helpers (for OpenClaw integration)
jarvis a2a health -j
jarvis a2a send "hello" --non-blocking -j
```

## Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Agent instructions |
| `AGENTS.md` | Same as CLAUDE.md (OpenAI compat) |
| `docs/` | Detailed documentation |
| `scripts/` | Utilities and linters |

## Architecture

```
src/jarvis/
├── daemon.py                  # Background service
├── ws_server.py               # WebSocket server (port 9847)
├── orchestrator/              # Message handling + routing
├── local_model_manager.py     # AFM local provider switching
└── a2a/server.py              # A2A server (port 9848)
```

## Voice Path (Current)

```
Voice tab (JarvisApp)
  -> VoiceRecorder (records + local Whisper transcription on macOS)
  -> WebSocket action: send_voice
  -> JarvisOrchestrator.handle_message(...)
  -> immediate reply payload
  -> app text-to-speech playback
```
