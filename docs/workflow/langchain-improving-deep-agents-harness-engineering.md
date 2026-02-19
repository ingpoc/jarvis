# LangChain Improving Deep Agents With Harness Engineering (Distilled)

**Source**: [X post by @Vtrivedy10](https://x.com/Vtrivedy10/status/2023805578561060992), [LangChain Blog](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/), [Terminal Bench 2.0 leaderboard](https://www.tbench.ai/leaderboard/terminal-bench/2.0)
**Date**: 2026-02-17
**Score**: 8/12 - Adapt
**Evaluation**: research-evaluator

## Verdict

**Rationale**: This is directly relevant to Jarvis because it gives concrete harness levers (prompt, tools, middleware) and a repeatable trace-improvement loop. We should adapt the loop patterns, but avoid blindly copying benchmark-specific heuristics.

| Dimension | Score | Notes |
|-----------|-------|-------|
| Novelty | 2/3 | Adds concrete middleware patterns and a trace-analyzer loop with measurable outcomes. |
| Relevance | 3/3 | Directly targets our current problem: making agent behavior more reliable over repeated sessions. |
| Claim validity | 2/3 | Claims are supported by the linked LangChain write-up and leaderboard snapshot; still single-team evidence. |
| Implementation cost | 1/3 | Some ideas are cheap (checklists, loop detection), but robust trace infra and eval loops require ongoing investment. |

## Claims Analysis

| Claim | Agree? | Evidence | Notes |
|-------|--------|----------|-------|
| Harness-only changes improved benchmark performance (52.8 -> 66.5) with fixed model | Yes | LangChain blog + Terminal Bench leaderboard | Current leaderboard shows Deep Agents at 66.5 (Top 5 at time checked). |
| Self-verification must be enforced; agents do not naturally verify enough | Yes | LangChain blog (Build/Verify/Fix loop + PreCompletionChecklistMiddleware) | Aligns with our own observed failure mode: early stopping after plausible first fix. |
| Trace-driven outer loop improves harness quality | Yes | LangChain blog (trace analyzer skill flow) | Strong pattern for continuous improvement with measurable signals. |
| Reasoning budget staging can beat always-max reasoning | Partial | LangChain blog | Plausible and useful heuristic, but benchmark/task dependent. Needs local validation. |
| Model-specific harness tuning matters | Yes | LangChain blog | Consistent with cross-model differences we already account for between Claude and Codex runtimes. |

## What to Take

- Make verification an explicit completion gate for coding tasks (`plan -> build -> verify -> fix`).
- Use trace analysis as a recurring outer loop to identify failure clusters, then patch harness behavior.
- Add lightweight loop-detection reminders when repeated edits hit the same file without progress.
- Inject deterministic environment context early (working directories, available tools, constraints).
- Keep model-specific harness variants rather than one universal prompt policy.

## What to Modify / Watch Out For

- Avoid overfitting to benchmark-style tasks; validate changes on Jarvis real workflows.
- Treat leaderboard gains as directional, not guaranteed for all environments.
- Keep guardrails proportional; do not add heavy middleware for low-frequency failure modes.
- Track regressions: any new harness rule should have a rollback path and evidence trail.

## Memory Promotion

**Memory Action**: Add
**Memory Notes**: `memory/lessons/2026-02-19-social-post-intake-needs-fallback-cascade.md`
**Reason**: Durable retrieval lesson from repeated social-link research intake failures.

## Integration Notes

**Tier**: 1 (Reference)
**Sessions Used**: 0
**Promotion Status**: Pending validation
**Debate**: No
