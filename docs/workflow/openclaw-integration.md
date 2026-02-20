# OpenClaw Integration (Standalone)

Use this guide for OpenClaw operation itself: gateway, channels, model auth, sandboxing, and reliability.

For Jarvis delegation, use `openclaw-jarvis-integration.md`.

## Scope

- OpenClaw gateway/service health
- Slack/runtime diagnostics
- Model provider/auth profile setup
- Sandbox/pairing reliability for agent turns

## Baseline Checks

```bash
openclaw --version
openclaw gateway status
openclaw models status --plain
openclaw channels status --probe
```

## Incident Playbook: "Agent failed before reply"

### Common signatures

- `Failed to inspect sandbox image: Cannot connect to the Docker daemon`
- `gateway closed (1008): pairing required`
- `No API key found for provider "openrouter"`

### Recovery sequence (best-practice)

1. If Docker is not available, disable sandbox mode:

```bash
openclaw config set agents.defaults.sandbox.mode off
openclaw gateway restart
```

2. Approve pending device/scope upgrades:

```bash
openclaw devices list --json
openclaw devices approve <requestId>
```

3. Verify provider/auth profile resolution:

```bash
openclaw models status --plain
jq '.' ~/.openclaw/agents/main/agent/auth-profiles.json
```

Required OpenRouter profile shape:

```json
{
  "provider": "openrouter",
  "mode": "api_key",
  "key": "sk-or-..."
}
```

4. Run deterministic smoke test:

```bash
openclaw agent --agent main -m "Reply with exactly OK" --json --timeout 120
```

Success gate:

- `status` is `ok`
- response text is exactly `OK`
- runtime metadata indicates expected provider

5. Validate recent logs:

```bash
tail -n 120 ~/.openclaw/logs/gateway.err.log
tail -n 120 ~/.openclaw/logs/gateway.log
```

Use timestamps to separate historical errors from current runtime state.

## Doctor + Hardening Loop

```bash
openclaw doctor --non-interactive
openclaw security audit --deep --json
openclaw gateway restart
```

## Slack Reliability Checks

```bash
openclaw channels status --probe
openclaw pairing list slack
```

Verify:

- Slack socket mode is connected
- expected channels are resolved
- no new `agent failed before reply` entries after remediation

## Security Notes

- Rotate any token that was pasted into terminal/chat history.
- Prefer auth profile/env usage over inline secrets in versioned config.

## References

- https://docs.openclaw.ai/cli
- https://docs.openclaw.ai/cli/doctor
- https://docs.openclaw.ai/gateway/configuration-reference
- https://deepwiki.com/openclaw/openclaw
