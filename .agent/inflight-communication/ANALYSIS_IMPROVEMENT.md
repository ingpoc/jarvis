# ANALYSIS_IMPROVEMENT.md

Last updated: 2026-02-16

Scope: in-flight implementation/review tracking, open blockers, and any contested or not-yet-approved items.

All agreed/approved architecture decisions live in `.agent/ARCHITECTURE.md`.

## Canonical Review Snapshot (Comms v12.1+)

This snapshot is the authoritative state machine view.

| Item | Status | Latest Codex Verdict | Open Blocker IDs |
|------|--------|----------------------|------------------|
| A5 | CHANGES_REQUESTED | Round 6: SessionManager SDK lifecycle bug | A5-B2 |
| A6 | CHANGES_REQUESTED | Round 6: depends on A5-B2 | A6-B1 |
| A8 | CHANGES_REQUESTED | Round 6: missing runtime auth/streamUrl tests | A8-B2 |

Promotion note:
- Approved items (A2/A4/A7/A11) were promoted out of this file into `.agent/ARCHITECTURE.md` per the comms protocol.

## Global Blockers

- `TEST-B1` (segfault): `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` segfaults in `tests/test_macos_native.py` calling `src/jarvis/macos_native.py:get_idle_seconds`.
  - This blocks using “full-suite green” as approval evidence. Item-level tests remain acceptable.

## Phase A: A2A Core Implementation (Open Items Only)

#### A5. Session Manager (Per-Channel Isolation)

**Status: CHANGES_REQUESTED**

- **Codex review (Round 6, 2026-02-16): REVIEW: CHANGES REQUESTED**
  - **A5-B2 (SDK lifecycle contract violated):**
    - DeepWiki (`anthropics/claude-agent-sdk-python`): `ClaudeSDKClient` requires explicit `connect()` before `query()/receive_response()`, and shutdown must call `disconnect()` (not `close()`).
    - Current `src/jarvis/session_manager.py`:
      - creates clients without calling `connect()`
      - attempts to shut down via `close()` instead of `disconnect()`
    - This is a latent runtime failure (or guaranteed failure depending on SDK behavior), especially because `src/jarvis/orchestrator.py` chat path calls `await client.query(...)` without any `connect()`.

- **Required fix**
  - In `SessionManager.get_client()`:
    - create client once per `channel_id`
    - `await client.connect()` exactly once per created client
  - In `SessionManager.close_client()` / `close_all()`:
    - `await client.disconnect()` when present
  - Add a minimal test (or a mocked transport test) that demonstrates connect/disconnect is invoked as expected for a new channel.

#### A6. A2A Executor

**Status: CHANGES_REQUESTED**

- **Codex review (Round 6, 2026-02-16): REVIEW: CHANGES REQUESTED**
  - **A6-B1 (depends on A5-B2):** `src/jarvis/a2a/executor.py` uses `SessionManager.get_client()` for per-task clients. Until A5-B2 is fixed, A2A execution may fail at runtime.

- **Required fix**
  - Fix A5-B2, then re-run:
    - `.venv/bin/python -m pytest -q tests/test_a2a_evidence.py`

#### A8. A2A Server (FastAPI + JSON-RPC 2.0)

**Status: CHANGES_REQUESTED**

- **Codex review (Round 6, 2026-02-16): REVIEW: CHANGES REQUESTED**
  - **A8-B2 (runtime auth + streamUrl assertions missing):**
    - Current tests only print expected 401 bodies; they do not execute HTTP calls to assert auth behavior.
    - Add an integration test that starts the server on an ephemeral port and asserts:
      - POST `/` without `Authorization` returns 401 with structured `detail.layer/code/message/remediation`.
      - JSON-RPC `message/stream` returns a `streamUrl` derived from request base URL (host-aware), not hard-coded `localhost`.

- **Required fix**
  - Add runtime integration tests under `tests/test_a2a_evidence.py` or a new `tests/test_a2a_server_runtime.py`.
