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
