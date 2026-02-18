# Idle Introspection Framework

**Status**: Proposed — implementation is ~90% scaffolded in existing code
**Decision**: Adopt. Single missing piece: `IntrospectionProcessor` class.

---

## The Idea

Use a local foundation model (Apple Silicon, MLX) during system idle time to analyze accumulated context graph traces and self_learning records, producing semantic insights that hash-based analysis cannot.

---

## Is This a Good Idea?

**Yes. Strong yes.**

| Factor | Assessment |
|--------|------------|
| Cost | Zero — local inference, no API calls |
| User impact | Zero — idle-time only, daemon already detects idle |
| Privacy | Total — traces never leave device |
| Value over current | High — semantic clustering finds patterns hash normalization misses |
| Feasibility | Extremely high — 90% of infrastructure already exists in daemon |
| Risk | Low — draft-only output, human review required |

---

## What Already Exists (Verified by Code Inspection)

| Component | Location | What It Does |
|-----------|----------|--------------|
| `_iokit_idle_loop()` | `daemon.py:346` | Polls HIDIdleTime every 30s via IOKit — **fully built, never wired** |
| `_idle_processor` slot | `daemon.py:136` | Initialized to `None`, checked at line 314 — **just needs a value** |
| Idle threshold config | `config.idle.idle_threshold_minutes` | Already in config — **built** |
| Memory pressure check | `daemon.py:372-387` | Unloads MLX when pressure high — **built** |
| `MLXInferenceEngine` | `mlx_inference.py:54` | Async, singleton, uses `Qwen2.5-3B-Instruct-4bit` — **built** |
| `ModelRouter` | `model_router.py:75` | 3-tier routing, adding introspection type rated 5/5 — **trivially extensible** |
| `self_learning.skill_candidates` | `self_learning.py:260` | 3+ occurrence patterns flagged — **built** |
| `MemoryStore` | `memory.py` | Learnings + skill_candidates readable — **built** |
| `DecisionTracer` | `orchestrator/core.py:100` | Stores traces to context graph — **built** |

**The single gap**: `_idle_processor` is `None`. Nothing implements the processor interface.

---

## Apple Silicon Access Strategy

### Foundation Models Framework (macOS 26)

- **Swift-only** — no Python API, PyObjC has no wrapper, no CLI access from daemon
- Option: thin Swift CLI tool called via subprocess — adds complexity, not recommended for v1
- **Ruled out for Python daemon**

### mlx-lm (Recommended)

- Full Python API, same Metal GPU as Foundation Models
- 20-50% faster than llama.cpp on Apple Silicon
- Updated Feb 17, 2026 — actively maintained
- **Jarvis already uses it** via `MLXInferenceEngine`

### mlx-embedding-models (New Requirement)

- `pip install mlx-embedding-models`
- Runs embedding models on Apple Silicon GPU
- Needed for semantic clustering (LLM cannot cluster reliably — embeddings do it correctly)

---

## Two-Stage Pipeline (Agent Recommendation)

Don't ask one model to do everything. Use the right tool for each stage:

```
Stage 1: CLUSTER (embedding model — fast, small)
  nomic-embed-text-v1.5 (137M params, ~500MB)
  via mlx-embedding-models
  Input: 20 trace descriptions
  Output: similarity clusters

Stage 2: SYNTHESIZE (instruct model — generates readable rules)
  Phi-4-mini-4bit (3.8B, ~2.5GB) — highest SLM accuracy
  OR Qwen2.5-Coder-3B-Instruct-4bit — better for code/rule generation
  via mlx-lm (already in Jarvis)
  Input: cluster summary + fix examples
  Output: draft .md rule file

Total memory: ~3GB model + ~500MB embeddings
Total time: ~30-60s per batch of 20 traces on M3/M4
```

**Why two-stage**: Asking a 3-4B LLM to cluster is unreliable. Vector similarity (embeddings) is deterministic and accurate. LLM is only used for the generation task it excels at.

---

## Idle Detection (Already Built)

Daemon already polls HIDIdleTime every 30s at `daemon.py:346`:

```python
# daemon.py:346 — _iokit_idle_loop() already exists
# It runs only when self._idle_processor is set (line 314)
# self._idle_processor is initialized to None (line 136)
```

**Also check thermal state before inference:**

```python
import subprocess

def is_thermal_ok() -> bool:
    result = subprocess.run(
        ["swift", "-e",
         "import Foundation; print(ProcessInfo.processInfo.thermalState.rawValue)"],
        capture_output=True, text=True, timeout=5
    )
    return int(result.stdout.strip()) <= 1  # 0=nominal, 1=fair
```

Or via PyObjC: `NSProcessInfo.processInfo().thermalState()`

---

## Integration Point: What to Build

### The Single Missing Class

```python
# src/jarvis/introspection_processor.py

class IntrospectionProcessor:
    """Implements the _idle_processor interface expected by daemon._iokit_idle_loop().
    Runs when system has been idle for config.idle.idle_threshold_minutes."""

    def __init__(self, memory: MemoryStore, mlx_engine: MLXInferenceEngine):
        self.memory = memory
        self.mlx = mlx_engine

    async def process_idle(self):
        """Called by daemon when idle threshold is reached."""
        if not is_thermal_ok():
            return

        # 1. Collect inputs
        candidates = self.memory.get_skill_candidates(min_occurrences=3)
        # + context graph traces (via MCP or direct DB read)

        # 2. Stage 1: Cluster via embeddings
        clusters = await self._cluster_by_embedding(candidates)

        # 3. Stage 2: Generate draft rules
        for cluster in clusters:
            if cluster.session_count >= 3:  # session-deduped, not raw count
                draft = await self._generate_rule(cluster)
                self._write_draft(draft)

        # 4. Store outcome
        # context_store_trace(...)
```

### Wire Into Daemon (One Line)

```python
# daemon.py — in __init__ or startup
self._idle_processor = IntrospectionProcessor(
    memory=self.memory,
    mlx_engine=get_mlx_engine()
)
# The _iokit_idle_loop() already checks self._idle_processor at line 314
# Setting it is all that's needed to activate idle processing
```

---

## Analysis Prompts

### Stage 2a: Cluster Summary (per cluster)

```
You are analyzing recurring error patterns in an AI coding assistant.

Here are {N} similar errors that share a root cause:
{examples}

In 2 sentences: what is the root cause, and what single rule would prevent all of them?
Output JSON: {"root_cause": str, "prevention_rule": str, "severity": "high|medium|low"}
```

### Stage 2b: Draft Rule Generation

```
Write a .claude/rules/ markdown file for this recurring error pattern.
Structure: ## Pattern, ## Why It Happens, ## Prevention (before/after), ## Detection.
Max 50 lines. Be specific, actionable.

Pattern: {root_cause}
Prevention: {prevention_rule}
Examples: {fix_examples}
```

---

## Output: Draft Rules Only

```
.claude/rules/
    draft-unicode-regex.md       ← introspection generated
    draft-async-state.md         ← introspection generated
    unicode-regex.md             ← human promoted from draft
```

`check-existing.sh` (from introspect skill) prevents duplicating active rules.

**Human promotion flow**: Review draft → rename to active → optionally promote to CLAUDE.md after 5+ sessions.

---

## Should Jarvis Do It or Foundation Model Directly?

**Jarvis orchestrates, local MLX model analyzes.**

| Role | Owner |
|------|-------|
| Idle detection | Daemon `_iokit_idle_loop()` — already built |
| Thermal check | `IntrospectionProcessor.process_idle()` |
| Data collection | `IntrospectionProcessor` reads MemoryStore + context graph |
| Embedding clustering | `mlx-embedding-models` (nomic-embed-text-v1.5) |
| Rule generation | `MLXInferenceEngine` (already in Jarvis) or Phi-4-mini-4bit |
| Output writing | `IntrospectionProcessor` writes to `.claude/rules/draft-*.md` |
| Human notification | Jarvis startup message: "2 draft rules generated during idle" |

The foundation model is a pure analysis tool. Jarvis provides trigger, context, and integration.

---

## Phased Implementation

### Phase 1: Minimal (1 session) — highest ROI

1. Create `IntrospectionProcessor` class with `process_idle()` stub
2. Wire `self._idle_processor = IntrospectionProcessor(...)` in `daemon.py`
3. Implement Stage 1 (embedding clustering) using `mlx-embedding-models`
4. Write cluster summaries to `~/.jarvis/logs/introspect.log`
5. **Verify idle loop fires** by watching log after 5 min inactivity

### Phase 2: Rule Generation (2nd session, after Phase 1 validated)

1. Implement Stage 2 (Phi-4-mini or Qwen2.5-Coder-3B for rule generation)
2. Write draft rules to `.claude/rules/draft-*.md`
3. Add thermal state check
4. Add session-dedup to pattern counting (date-group traces before counting)
5. Call `check-existing.sh` before writing to avoid duplicates

### Phase 3: Closed Loop (after drafts validated by human)

1. Track promoted vs ignored drafts
2. Surface pending drafts in Jarvis startup message
3. Store introspection outcomes in context graph
4. Adjust prompts based on accepted/rejected rate

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Model generates bad rules | Draft-only, human review required |
| OOM during inference | Daemon already has memory pressure check (line 372-387), unloads MLX |
| Running during user activity | HIDIdleTime check — already built in `_iokit_idle_loop()` |
| Thermal throttling | Check thermalState before starting inference |
| Cross-project trace contamination | Filter by project_dir before embedding/clustering |
| `_idle_processor` crashes daemon | Process errors in `try/except`, log and continue, never propagate |

---

## Why This Makes Jarvis Better Over Time

| Current (`self_learning.py`) | Proposed (+ Introspection) |
|------------------------------|---------------------------|
| Hash-based: "Unicode apostrophe in extractQuarterly" ≠ "Unicode apostrophe in extractYearly" | Embedding-based: both cluster to same root cause |
| Rule description: "Fix for: {error[:100]}" template | LLM-generated: readable, actionable, with before/after |
| Can't synthesize cross-category patterns | Finds: "these 4 errors share async state mutation root" |
| All patterns equal weight | Prioritizes by session-frequency + severity |
| Analysis only after each task | Background analysis of all historical traces during idle |

The goal: each session has slightly fewer mistakes than the last, because idle hours convert past mistakes into prevention rules.

---

## Integration Notes

**Tier**: 1 (Reference — architecture designed, not yet implemented)
**Created**: 2026-02-18
**Sessions Used**: 0
**Promotion Status**: Pending Phase 1 implementation

### Key files to create/modify

| File | Change |
|------|--------|
| `src/jarvis/introspection_processor.py` | Create — the missing `_idle_processor` implementation |
| `src/jarvis/daemon.py:136` | Wire: `self._idle_processor = IntrospectionProcessor(...)` |
| `requirements.txt` / `pyproject.toml` | Add: `mlx-embedding-models` |
