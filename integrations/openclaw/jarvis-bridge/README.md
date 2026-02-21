# Jarvis Bridge Plugin

Routes execution tasks from OpenClaw to Jarvis A2A.

## Exposed surfaces

- Tool (preferred): `jarvis_delegate_task`
- Tool (legacy alias): `jarvis_code_task`
- Gateway RPC method: `jarvis.codeTask`
- Gateway RPC method (preferred): `jarvis.delegateTask`
- Command: `/jarvis <task>`
- Skills:
  - `jarvis-coder` (`/jarvis-coder <task>`) for coding
  - `jarvis-chief` (`/jarvis-chief <task>`) for general execution tasks

## Plugin config

Add under `plugins.entries.jarvis-bridge.config`:

```json5
{
  baseUrl: "http://127.0.0.1:9848",
  tokenPath: "~/.jarvis/system/jarvis_config/a2a_token",
  defaultWait: false,
  defaultTimeoutSec: 18000,
  pollIntervalMs: 1000,
}
```

Optional auth overrides:

- `token` (inline; least preferred)
- `tokenEnv` (default: `JARVIS_A2A_TOKEN`)

## Notes

- Keep Jarvis daemon running so A2A is reachable.
- This plugin intentionally avoids shell execution and talks to A2A over HTTP JSON-RPC.
- Follow-up continuity fields:
  - `jobId`: stable logical task thread id inside OpenClaw scope.
  - `followUp=true`: resume latest job in current scope when `jobId/contextId` are omitted.
  - `contextId`: stable A2A context routing key.
  - `resumeSessionId`: explicit OpenCode session resume id (survives Jarvis restart).
- Recommended split:
  - OpenClaw-native tools (Perplexity/Browser/Context7) for research discovery.
  - Jarvis delegation for execution-heavy work (coding, structured implementation, long-running actions).
- Reliability pattern for long work:
  - Delegate in small atomic steps with explicit completion tokens (`DONE_STEP1`, `DONE_STEP2`, ...).
  - Default to non-blocking (`wait=false`) and only use `wait=true` for bounded checks.
  - For coding tasks, explicitly state `OPENCODE ONLY` in the delegated task text.

## Validation Quickstart

Use Jarvis A2A/task-store evidence as the source of truth.

```bash
# 1) Health
openclaw gateway health
python3 -m jarvis.cli a2a health -j

# 2) Delegate from OpenClaw (non-blocking)
openclaw gateway call jarvis.delegateTask \
  --params '{"task":"OPENCODE ONLY. Reply with exactly: OPENCLAW_A2A_CHECK_OK","wait":false,"jobId":"validation-a2a"}' \
  --timeout 60000 --json

# 3) Get latest A2A task created for that job/context
sqlite3 ~/.jarvis/jarvis.db \
  "select id,status,context_id,result from a2a_tasks where context_id='ctx-validation-a2a' order by created_at desc limit 1;"

# 4) Verify via A2A tasks/get
python3 -m jarvis.cli a2a get <a2a-task-id> -j
```

Expected:
- A2A task status is `completed`
- result is `OPENCLAW_A2A_CHECK_OK`

Note:
- Gateway `wait` calls can timeout while Jarvis still completes the task.
- Prefer A2A task status + timeline over gateway wait response for final validation.
