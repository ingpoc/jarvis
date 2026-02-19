# OpenAI Unlocking The Codex Harness (Distilled)

**Source**: [OpenAI Blog - Unlocking the Codex harness](https://openai.com/index/unlocking-the-codex-harness/)
**Date**: 2026-02-04
**Score**: 9/12 - Adapt
**Evaluation**: research-evaluator

## Verdict

**Rationale**: The thread/turn/item model and bidirectional protocol map directly to long-running agent workflows we already need. We should adapt the interaction model, not copy Codex-specific implementation details.

| Dimension | Score | Notes |
|-----------|-------|-------|
| Novelty | 2/3 | Structured conversation primitives are useful and more explicit than current ad-hoc flow notes. |
| Relevance | 3/3 | Directly relevant to Jarvis multi-step task execution and tool-event handling. |
| Claim validity | 2/3 | Primary-source blog claims are supported by `openai/codex` app-server protocol evidence. |
| Implementation cost | 2/3 | Incremental adaptation to docs/process is low; full protocol parity would be higher cost. |

## Claims Analysis

| Claim | Agree? | Evidence | Notes |
|-------|--------|----------|-------|
| Harness uses thread -> turn -> item primitives | Yes | OpenAI article + `openai/codex` DeepWiki evidence | Confirmed in public app-server protocol docs/structure. |
| Protocol is bidirectional and streams granular events | Yes | OpenAI article + `openai/codex` DeepWiki evidence | Strong fit for agent observability and review loops. |
| Approval is first-class in runtime loop | Yes | OpenAI article + Codex approval request/response model | Matches our need for explicit high-impact approval boundaries. |
| Architecture enables richer IDE/agent integrations | Partial | OpenAI article | True for Codex stack; Jarvis must map to Claude SDK runtime boundaries. |

## What to Take

- Use explicit `thread`, `turn`, and `item` vocabulary in workflow docs and planning.
- Treat tool approvals as protocol events, not informal prompts.
- Prefer event-stream traces over final-summary-only traces for long tasks.
- Keep interface boundaries clean between orchestration loop and tool runtime.

## What to Modify / Watch Out For

- Do not assume Codex app-server contracts are drop-in for Claude Agent SDK.
- Avoid overfitting Jarvis internals to one runtime's wire protocol.
- Keep the policy layer runtime-agnostic: same principle, different mechanism (Codex policy vs Claude hooks).

## Memory Promotion

**Memory Action**: Defer
**Reason**: Captured as workflow reference; no new durable memory beyond existing governance decision yet.

## Integration Notes

**Tier**: 1 (Reference)
**Sessions Used**: 0
**Promotion Status**: Pending validation
**Debate**: No
