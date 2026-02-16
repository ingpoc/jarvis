# Jarvis Testing

Source of truth: `.agent/ARCHITECTURE.md` (last updated: 2026-02-16).

Goal: verify Jarvis behaves as the architecture claims across UI + WS + A2A + container runtime, with explicit failures (no silent fallback).

## Architecture Validation (Gate)

- [ ] `.agent/ARCHITECTURE.md` includes an "Implemented" section for:
  - A2 AgentCard
  - A4 A2A task store persistence
  - A5 SessionManager lifecycle-correct (`connect`/`disconnect`)
  - A6 A2A executor session isolation
  - A7 SSE streaming surface
  - A8 runtime contract coverage tests
  - A11 daemon lifecycle integration

## Expected Features (From Architecture)

### Core

- [ ] Single shared execution core (`JarvisOrchestrator`) used by WS/Slack/CLI/A2A adapters.
- [ ] Per-channel SDK sessions via `SessionManager` (no context bleeding).
- [ ] Fail-fast policy enforcement via hooks (budget/trust).

### A2A Server

- [ ] `GET /.well-known/agent-card.json` works (discovery).
- [ ] JSON-RPC methods via `POST /`:
  - [ ] `message/send`
  - [ ] `message/stream`
  - [ ] `tasks/get`
  - [ ] `tasks/cancel`
- [ ] `GET /stream/{task_id}` streams SSE events.
- [ ] `GET /health` returns ok + active task count.
- [ ] Auth is enforced (Bearer token), failures are structured: `detail.layer/code/message/remediation`.
- [ ] `message/stream` returns host-aware `streamUrl` derived from request base URL.
- [ ] Task persistence: A2A tasks survive restart (SQLite via MemoryStore).

### macOS App + Daemon

- [ ] Daemon runs under launchd and serves WS (port 9847).
- [ ] Menu bar app connects/disconnects reliably and reflects daemon status.
- [ ] Full app shows the same underlying event stream as menu bar.
- [ ] Crashes and runtime failures are visible via logs/events (no protocol breakage).

### Containers (Runtime Integration)

- [ ] Container runtime command exists and is discoverable (`container` CLI).
- [ ] `get_containers` does not crash when runtime is missing; it must return an explicit error (screams).
- [ ] When a container is started through Jarvis tools, it appears in the Containers UI/tab.

## Test Plan (Smoke)

### 1) Startup / Health

Commands:
```bash
bash ./stop-jarvis.sh
bash ./start-jarvis.sh
```

Pass criteria:
- [ ] Daemon WS port listening (9847)
- [ ] Menu bar app running and shows connected
- [ ] Logs show no FATAL startup errors

### 2) A2A Contract (Local)

Pre-req:
- A2A enabled (config/env), default port 9848.

Checks:
- [ ] `GET http://127.0.0.1:9848/health` returns 200
- [ ] `GET http://127.0.0.1:9848/.well-known/agent-card.json` returns 200
- [ ] `POST /` without Authorization returns 401 structured error
- [ ] `message/stream` returns `streamUrl` with correct host:port

### 3) WS Contract (Menu Bar / Command Center)

Checks:
- [ ] `get_status` returns Swift-compatible top-level fields
- [ ] `get_containers` does not crash; if runtime missing, explicit error is shown
- [ ] Commands return correlated responses (echoed request ids)

### 4) Conversational Task (Non-Container)

Checks:
- [ ] Simple chat ("hi") returns assistant response (not forced into run_task)
- [ ] A longer request produces tool usage in timeline and visible artifacts

### 5) Containerized Task (If Runtime Present)

Checks:
- [ ] Jarvis creates a container for the task and it remains running as needed
- [ ] Container shows in Containers tab
- [ ] Task emits lifecycle events and completes

## Evidence (To Capture)

For each failing check, capture:
- exact command used
- exact error text
- relevant log snippet
- timestamp

