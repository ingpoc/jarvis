# Z.AI (GLM Models) Setup for Jarvis

## Problem Solved

The Claude Agent SDK validates model IDs against a whitelist. Raw model IDs like `glm-4.7` are not in the whitelist and will be rejected.

**Solution**: Use model aliases (opus/sonnet/haiku) + environment variables to route through z.ai.

## Quick Setup

### 1. Get Your Z.AI API Key

Visit [z.ai](https://z.ai) and create an account, then generate an API key from your dashboard.

### 2. Set Environment Variables

```bash
export ANTHROPIC_BASE_URL="https://api.z.ai/api/anthropic"
export ANTHROPIC_AUTH_TOKEN="your-z.ai-api-key-here"
export ANTHROPIC_DEFAULT_OPUS_MODEL="glm-5"
export ANTHROPIC_DEFAULT_SONNET_MODEL="glm-5"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="glm-5"
```

**Persistent Setup** (add to `~/.zshrc` or `~/.bashrc`):

```bash
# Z.AI Configuration (GLM-5 for all tiers)
export ANTHROPIC_BASE_URL="https://api.z.ai/api/anthropic"
export ANTHROPIC_AUTH_TOKEN="${ZAI_API_KEY}"  # Reference env var if you prefer
export ANTHROPIC_DEFAULT_OPUS_MODEL="glm-5"
export ANTHROPIC_DEFAULT_SONNET_MODEL="glm-5"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="glm-5"
```

### 3. Configure Jarvis to Use Aliases

Jarvis now uses aliases by default. If you changed them, reset to:

```bash
jarvis config models.executor=sonnet
jarvis config models.planner=opus
jarvis config models.reviewer=sonnet
jarvis config models.quick=haiku
```

Or edit `~/.jarvis/config.json`:

```json
{
  "models": {
    "executor": "sonnet",
    "planner": "opus",
    "reviewer": "sonnet",
    "quick": "haiku"
  }
}
```

### 4. Verify Setup

```bash
# Test that z.ai is routed correctly
export ANTHROPIC_BASE_URL="https://api.z.ai/api/anthropic"
export ANTHROPIC_AUTH_TOKEN="your-key"

python -c "
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
import asyncio

async def test():
    opts = ClaudeAgentOptions(model='sonnet')
    async with ClaudeSDKClient(options=opts) as client:
        await client.query('Say hello')
        async for msg in client.receive_response():
            print(f'✅ z.ai routing works! Got message type: {type(msg).__name__}')
            break

asyncio.run(test())
"
```

## How It Works

```
Jarvis Config       Claude Agent SDK         Z.AI
─────────────────  ──────────────────────────────────
model: "sonnet"  →  ClaudeAgentOptions    →  GLM-4.7
(alias)             checks ANTHROPIC_*     (via env vars)
                    env vars
```

The SDK looks at `ANTHROPIC_DEFAULT_SONNET_MODEL` environment variable and uses that model ID when calling the API endpoint specified by `ANTHROPIC_BASE_URL`.

## Model Mapping

| Jarvis Config | SDK Alias | Z.AI Environment Var | Default |
|---------------|-----------|----------------------|---------|
| executor      | sonnet    | ANTHROPIC_DEFAULT_SONNET_MODEL | glm-5 |
| planner       | opus      | ANTHROPIC_DEFAULT_OPUS_MODEL   | glm-5 |
| reviewer      | sonnet    | ANTHROPIC_DEFAULT_SONNET_MODEL | glm-5 |
| quick         | haiku     | ANTHROPIC_DEFAULT_HAIKU_MODEL  | glm-5 |

## Troubleshooting

### Error: "Unknown model 'glm-4.7'"

**Cause**: You're still using raw model IDs instead of aliases.

**Fix**: Use aliases (sonnet/opus/haiku) and set environment variables.

### Error: "Failed to connect to <https://api.z.ai/>..."

**Cause**: ANTHROPIC_BASE_URL is not set or invalid.

**Verification**:

```bash
echo $ANTHROPIC_BASE_URL
echo $ANTHROPIC_AUTH_TOKEN  # Should be masked, but should exist
```

### Error: "401 Unauthorized"

**Cause**: Invalid or expired API key.

**Fix**:

1. Check your z.ai dashboard API keys
2. Regenerate if needed
3. Update ANTHROPIC_AUTH_TOKEN

### Working but slow?

Z.AI may be under load. Check their status page or contact support.

## Using Standard Claude Models Again

If you want to switch back to standard Anthropic Claude models:

```bash
# Unset z.ai environment variables
unset ANTHROPIC_BASE_URL
unset ANTHROPIC_AUTH_TOKEN
unset ANTHROPIC_DEFAULT_OPUS_MODEL
unset ANTHROPIC_DEFAULT_SONNET_MODEL
unset ANTHROPIC_DEFAULT_HAIKU_MODEL

# Jarvis will use default Anthropic API (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY="your-anthropic-key"
```

Or set Jarvis to use full model IDs:

```bash
jarvis config models.executor=claude-sonnet-4-5-20250929
jarvis config models.planner=claude-opus-4-6
```

## References

- [Z.AI Documentation](https://docs.z.ai)
- [Claude Agent SDK Options](https://code.claude.com/docs/en/sdk/sdk-typescript)
- [Claude Code Model Configuration](https://docs.claude.com/en/docs/claude-code/model-config)
