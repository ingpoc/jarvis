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
  tokenPath: "~/.jarvis/a2a_token",
  defaultWait: false,
  defaultTimeoutSec: 300,
  pollIntervalMs: 1000,
}
```

Optional auth overrides:

- `token` (inline; least preferred)
- `tokenEnv` (default: `JARVIS_A2A_TOKEN`)

## Notes

- Keep Jarvis daemon running so A2A is reachable.
- This plugin intentionally avoids shell execution and talks to A2A over HTTP JSON-RPC.
- Recommended split:
  - OpenClaw-native tools (Perplexity/Browser/Context7) for research discovery.
  - Jarvis delegation for execution-heavy work (coding, structured implementation, long-running actions).
