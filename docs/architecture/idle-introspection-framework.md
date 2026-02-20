# Idle Introspection Framework

**Status**: Implemented (model-independent)
**Goal**: Learn from repeated failures during idle time without adding cloud cost or runtime risk.

## Overview

During idle windows, Jarvis analyzes recurring patterns from:
- `skill_candidates` (repeated implementation patterns)
- `learnings` (error/fix history)

It clusters similar patterns using deterministic text similarity and writes draft prevention rules to:
- `.claude/rules/draft-introspect-*.md`

Human review is still required before any rule becomes active.

## Current Design

### Triggering

- Daemon polls idle state via IOKit in `src/jarvis/daemon.py`.
- If idle threshold is reached, it triggers `IntrospectionProcessor`.
- Runs are capped (`MAX_RUNS_PER_DAY`) and cancelled on user activity.

### Stage 1: Pattern Clustering

- Data is collected from memory store candidates/learnings.
- Similarity uses TF-IDF/Jaccard-style token overlap (`_tfidf_clusters`).
- No local LLM dependency is required for clustering.

### Stage 2: Draft Rule Synthesis

- For significant clusters, Jarvis writes a deterministic markdown draft.
- Output sections:
  - `## Pattern`
  - `## Why It Happens`
  - `## Prevention`
  - `## Detection`
  - `### Examples`

## Why This Version

- Stable: no model boot/runtime crash risk in daemon idle path.
- Cheap: no API calls.
- Explainable: deterministic clustering and deterministic draft format.
- Reviewable: draft-only output, human promotion gate unchanged.

## Key Files

- `src/jarvis/introspection_processor.py`
- `src/jarvis/daemon.py`
- `src/jarvis/idle_mode.py`

## Safety Controls

- Daily run limit (`MAX_RUNS_PER_DAY`)
- Thermal guard check before processing
- Cancellation on activity/hibernate
- Draft-only output (no auto-activation)

## Future Enhancements

1. Improve clustering quality with better token normalization.
2. Add confidence scoring per generated draft.
3. Show pending draft count in app status/notifications.
4. Add acceptance feedback loop (promoted vs ignored drafts).
