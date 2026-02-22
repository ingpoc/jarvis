# Jarvis-NanoClaw Single-Path Checklist

Goal: keep exactly one integration path and remove all non-essential alternatives.

## Canonical Path (Only Path)

- [x] **Chosen path is fixed**: `NanoClaw -> Jarvis A2A JSON-RPC`.
- [x] Submission method is fixed: `message/send` with `blocking=false`.
- [x] Status method is fixed: `tasks/get` polling.
- [x] Cancellation method is fixed: `tasks/cancel`.
- [x] No parallel integration path is allowed (no duplicate WS/CLI bridge contract for NanoClaw dispatch).

## Contract (Required Fields)

- [x] Request payload accepts: `run_id`, `message`, `context_id` (optional), `resume_session_id` (optional), `timeouts` (optional), `priority` (optional), `task_type` (optional).
- [x] Duplicate `run_id` is idempotent (returns existing task, does not re-execute).
- [x] Response includes: `run_id`, `taskId`, `status`, `createdAt`, `updatedAt`.
- [x] Terminal response includes normalized `result`, `error`, and `artifacts`.

## Telemetry and Supervisor Data

- [x] Terminal artifacts include usage block with `input_tokens`, `output_tokens`, `duration_ms`, `peak_rss_mb`.
- [x] Timeout/failure includes normalized machine-readable error code.
- [x] Every run emits audit correlation artifact containing `run_id`, `context_id`, `task_id`, and `worker_identity`.

## Runtime and Security

- [x] Bearer auth remains mandatory for A2A endpoints.
- [ ] Dedicated NanoClaw auth scope/token is used (NanoClaw-owned rollout).
- [ ] Required mounted paths are validated at task start (NanoClaw container contract).
- [x] No sensitive env values are returned in results/artifacts/log summaries.

## Code Simplification (Remove Non-Essential Paths)

- [x] Removed/disabled legacy dispatch logic not used by NanoClaw path.
- [x] Removed naming/path assumptions tied to OpenClaw where not needed for NanoClaw path.
- [x] One execution flow in code: submit -> execute -> finalize -> poll/cancel.
- [x] One status source of truth: `a2a_tasks` persisted state.

## Tests (Required)

- [x] Unit: payload validation for required fields (including `run_id`).
- [x] Unit: idempotency behavior for duplicate `run_id`.
- [x] Unit: usage telemetry extraction and artifact emission.
- [x] Integration: one successful run via canonical path.
- [x] Integration: timeout/failure run with clear error code + audit artifact.
- [x] Integration: cancellation flow correctness.

## Jarvis Files

- `src/jarvis/a2a/server.py`
- `src/jarvis/a2a/executor.py`
- `src/jarvis/a2a/task_store.py`
- `src/jarvis/orchestrator/core.py`
- `src/jarvis/opencode_client.py`
- `tests/test_a2a_*`
- `tests/test_opencode_client.py`
