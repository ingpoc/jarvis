# Apple-MLX DeepWiki Router (Jarvis)

Use this page as the source of truth for Apple-native/MLX repo lookup.
Keep only routing/decision logic here. Pull implementation detail from DeepWiki on demand.

## What to Keep in Repo Docs

- Jarvis-specific architecture and constraints (`src/jarvis/*`, model picker behavior, WS contracts).
- Operational runbooks (startup, launchctl, validation scripts, known gotchas).
- Repo-routing map: which GitHub repo to DeepWiki for each use case.

## What to Pull from DeepWiki

- Framework internals and API details.
- Performance tuning specifics.
- Component-specific implementation patterns (Whisper, mlx-lm server internals, container internals).

## Primary Repos (Now / Future)

Only high-value repos for Jarvis now or likely near-future:

| Priority | Repo | Use Now | Use Future | Why |
|---|---|---|---|---|
| P0 | `apple/container` | Yes | Yes | Directly relevant to Jarvis container CLI/system lifecycle and startup health behavior. |
| P0 | `ml-explore/mlx-examples` | Yes | Yes | Canonical source for MLX Whisper behavior (`Audio Processing -> Whisper`). |
| P1 | `ml-explore/mlx-lm` | Partial | Yes | Direct local LLM server/generation path if Jarvis expands beyond LM Studio bridge. |
| P1 | `ml-explore/mlx` | Partial | Yes | Low-level MLX performance tuning (Metal backend, memory model, primitives). |
| P2 | `apple/containerization` | No | Maybe | Lower-level internals when `apple/container` docs are insufficient. |

## DeepWiki Decision Map

1. Daemon/container startup reliability, `container system start/status`, launchctl/service lifecycle:
Use `apple/container`

2. Speech-to-text on Apple Silicon (mlx-whisper behavior, audio pipeline, conversion flow):
Use `ml-explore/mlx-examples`

3. Direct local model serving/generation path (non-LM-Studio future track):
Use `ml-explore/mlx-lm`

4. MLX performance/memory/kernel optimization:
Use `ml-explore/mlx`

5. Rare deep runtime internals of Apple containers:
Use `apple/containerization`

## Query Templates

Use these short prompts with DeepWiki:

- `apple/container`: "For launchctl-managed daemon startup, what is the recommended health-check and service-state verification path?"
- `ml-explore/mlx-examples`: "Where is Whisper implemented and what is the exact transcription flow (audio load -> mel -> decode)?"
- `ml-explore/mlx-lm`: "What are the server/model-loading semantics and non-production caveats for local HTTP serving?"
- `ml-explore/mlx`: "Which Metal backend and memory-model details matter most for Apple Silicon performance tuning?"

## Non-DeepWiki Fallback

Some repos may not be indexed in DeepWiki at a given time.
Current example relevant to Jarvis Foundation Models Python bindings:

- `btucker/apple-foundation-models-py` (fallback to GitHub README/issues when not indexed)
