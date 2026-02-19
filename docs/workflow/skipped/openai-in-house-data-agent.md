# OpenAI Inside Our In-House Data Agent - Skipped

**Source**: [OpenAI Blog - Inside our in-house data agent](https://openai.com/index/inside-our-in-house-data-agent/)
**Date**: 2026-01-29
**Score**: 3/12

## Why skipped

Most gains in the article depend on OpenAI-internal data estate scale and bespoke infrastructure (enterprise catalog + large internal telemetry surface). The transfer path to Jarvis is weak right now relative to cost.

| Dimension | Score | Notes |
|-----------|-------|-------|
| Novelty | 1/3 | Layered context and evaluators are known patterns in our current harness docs. |
| Relevance | 1/3 | Jarvis is not operating at comparable data-platform scale. |
| Claim validity | 1/3 | Strong as a case study, but external reproducibility evidence is limited. |
| Implementation cost | 0/3 | Recreating similar data substrate is costly and not aligned with current priorities. |

## Claims snapshot

| Claim | Agree? | Evidence | Notes |
|-------|--------|----------|-------|
| Layered context improves data agent usefulness | Yes | OpenAI article | Concept is sound and already represented in our progressive-disclosure design. |
| Evals and memory loops improve reliability | Yes | OpenAI article + our harness direction | Worth keeping as principle, not as a direct implementation import. |
| End-to-end architecture should be copied as-is | No | OpenAI article + external relevance check | Internal dependencies make direct adoption low ROI for Jarvis today. |

## Revisit if

- Jarvis expands into high-volume enterprise data workflows.
- We establish a stable internal data catalog/query layer first.
- We can define a constrained pilot with measurable ROI in < 2 weeks.

