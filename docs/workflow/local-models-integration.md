# Runtime Model Integration (OpenCode-Only)

## Overview

Jarvis runtime is OpenCode-only.

- Provider: `opencode`
- Model IDs: `opencode/*`
- Delegated A2A tasks: forced to `JARVIS_A2A_OPENCODE_MODEL` (default `opencode/glm-5-free`)

## Routing Rules

- `run_task` -> `_run_task_opencode`
- `chat` -> `_chat_opencode`
- `switch_model` rejects non-`opencode/*` values

## WebSocket Contract

`get_model_status` returns:

- `current_model`
- `provider` = `opencode`
- `provider_type` = `opencode`
- `opencode_available_models`

`switch_model` accepts only `opencode/*` or `opencode:` IDs.

## Validation

```bash
python3 scripts/validate_jarvis.py --full
```

## Notes

- Local model paths are intentionally disabled.
- Anthropic/SDK execution paths are intentionally disabled.
