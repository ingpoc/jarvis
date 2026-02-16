# ANALYSIS_IMPROVEMENT.md

Last updated: 2026-02-16

Scope: in-flight implementation/review tracking, open blockers, and any contested or not-yet-approved items.

All agreed/approved architecture decisions live in `.agent/ARCHITECTURE.md`.

## Canonical Review Snapshot (Comms v12.1+)

This snapshot is the authoritative state machine view.

| Item | Status | Latest Codex Verdict | Open Blocker IDs |
|------|--------|----------------------|------------------|
| - | - | - | - |

## Global Blockers

- `TEST-B1` (segfault): `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` segfaults in `tests/test_macos_native.py` calling `src/jarvis/macos_native.py:get_idle_seconds`.
  - This blocks using "full-suite green" as approval evidence. Item-level tests remain acceptable.

