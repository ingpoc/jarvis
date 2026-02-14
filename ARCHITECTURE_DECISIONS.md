# Jarvis v2.0 Architectural Decisions & Trade-offs

This document explains the "why" behind key architectural choices in the Jarvis v2.0 design and how they differ from the current implementation.

---

## 1. Single Long-Lived SDK Session vs. Multi-Instance

### Decision
**Use one ClaudeSDKClient per project, not multiple instances**

### Rationale
- **Problem**: Each ClaudeSDKClient spawns a Claude Code CLI subprocess (20–30+ seconds overhead)
- **Scale**: 5 parallel tasks would require 5 instances = 100–150 seconds just for initialization
- **Memory**: Each instance retains 200–300MB baseline

### Implementation
- Planner, Executor, Tester, Reviewer are SDK **subagents**, not separate processes
- Register via AgentDefinition with isolated context windows and tool restrictions
- All coordination happens within one orchestrator session via Task tool

### Trade-offs
| Benefit | Cost |
|---------|------|
| Sub-second task switching | Shared context window (managed via subagent windowing) |
| Minimal memory overhead | Cannot pause/resume subagent state independently |
| Clean hook pipeline | All tool calls visible in one stream |

### Code Location
- `orchestrator.py:50–100` (main loop)
- `agents.py` (Planner/Executor/Tester/Reviewer definitions)
- `config.py` (AgentDefinition configuration)

---

## 2. Apple Containerization vs. Docker Desktop

### Decision
**Primary: Apple Containerization (Virtualization.framework)**
**Fallback: Docker Desktop for complex multi-container scenarios**

### Rationale

| Metric | Apple Container | Docker Desktop | Winner |
|--------|---|---|---|
| Cold start | 1.2s | 0.5s (warm) | Docker (cold); Container (warm) |
| Idle overhead | 0 MB (hibernates) | 500MB–2GB | Apple |
| Hardware isolation | Per-VM | Shared kernel | Apple (safer) |
| Per-container IP | 192.168.64.x (native) | Port mapping | Apple |
| I/O ops/sec | 31× baseline | Baseline | Apple |
| Licensing | Free (Apache 2.0) | $9–24/month | Apple |
| Maturity | v0.6.0 | Mature ecosystem | Docker |

### Implementation
- Launch per-repo workspace in isolated Apple Container VM
- Bind-mount workspace read-write for file sync
- SSH port forward for CLI access
- Network isolated within Virtualization.framework namespace

### Trade-offs
| Benefit | Cost |
|---------|------|
| Zero idle overhead on 24GB Mac | New-ish API (v0.6.0) |
| Hardware-level code isolation | No Docker Compose equivalent |
| Hardware acceleration | Requires Apple Silicon target |

### Code Location
- `container_tools.py` (API wrapper)
- `container_templates.py` (template definitions)
- `orchestrator.py:250–300` (lifecycle management)

---

## 3. SQLite with sqlite-vec vs. FAISS Vector DB

### Decision
**Use sqlite-vec (vector search in SQLite) for all persistence**

### Rationale

| Feature | sqlite-vec | FAISS | Winner |
|---------|---|---|---|
| Query latency | 75ms (disk) | 1–5ms (RAM) | FAISS (speed) |
| RAM overhead | ~30MB (vectors in WAL) | 293MB+ (resident) | sqlite-vec (memory) |
| ACID transactions | ✅ Yes | ❌ No | sqlite-vec |
| SQL JOINs | ✅ Relational queries | ❌ Vector-only | sqlite-vec |
| GPU acceleration | ❌ SQLite | ✅ Metal GPU (via wrapper) | FAISS |
| Operational complexity | Single file | Metadata + binary sidecar | sqlite-vec |

### Implementation
- Single SQLite database per repo: `knowledge.db`
- `sqlite-vec` plugin for vector operations (learnings similarity search)
- ACID consistency for execution_records + learnings
- Full-text search (FTS5) for decision traces

### Trade-offs
| Benefit | Cost |
|---------|------|
| All data in one file (backup/sync) | 75ms query latency (acceptable for learning retrieval) |
| Relational integrity | No real-time vector index rebalancing |
| No separate vector maintenance | Query planning for large tables needs tuning |

### Code Location
- `memory.py` (SQLite initialization)
- `schema.sql` (tables: learnings, knowledge, execution_records, skill_candidates, token_usage)
- `self_learning.py` (vector similarity search via sqlite-vec)

---

## 4. Three-Tier Intelligence Routing (Qwen3 / GLM / Foundation Models)

### Decision
**Route tasks dynamically across three model tiers based on latency, cost, and capability**

### Tier Design

```
Tier 1: Qwen3 4B (MLX, local)
├─ Latency: 80–120 t/s (80–100ms TTFT)
├─ Cost: Free
├─ Use: Simple classification, error triage, commit messages, file pre-filtering
└─ Fallback: Always available offline

Tier 2: GLM 4.7 (via Z.AI)
├─ Latency: 50–80 t/s (1–3s TTFT)
├─ Cost: $0.60/M input tokens
├─ Use: Multi-file generation, architecture analysis, skill generation
└─ Context: 200K tokens with interleaved thinking

Tier 3: Foundation Models (Apple, on-device)
├─ Latency: 70–100 t/s (<200ms TTFT)
├─ Cost: Free
├─ Use: Task classification, NL parsing (via @Generable)
└─ Context: 4K token limit (including input+output+instructions)
```

### Routing Logic

```python
if task_type == "classification" and input_tokens < 2000:
    route_to = "Foundation Models"  # Fastest, free
elif latency_requirement_ms < 500:
    route_to = "Qwen3 4B"  # Local, sub-100ms
elif online and budget_remaining > cost_estimate:
    route_to = "GLM 4.7"  # Powerful, relatively cheap
elif offline:
    route_to = "Qwen3 4B"  # Fallback
else:
    route_to = "Qwen3 4B"  # Budget exhausted
```

### Trade-offs
| Benefit | Cost |
|---------|------|
| 60–80% token savings via local Tier 1 | Complexity of 3 code paths |
| Zero-latency fast path for classification | Foundation Models 4K limit |
| Graceful offline degradation | Model selection quality crucial |

### Code Location
- `model_router.py` (decision logic, not yet implemented)
- `config.py` (model tier configuration)
- `QwenInferenceService.swift` (Tier 1 Swift wrapper, not yet implemented)
- `hooks.py` (PreToolUse hook for router integration)

---

## 5. Progressive Skill Disclosure (Metadata at Startup, Full on Selection)

### Decision
**Load skill descriptions (~100 tokens) at session start; full SKILL.md content only on selection**

### Rationale
- **Problem**: Accumulated skills inflate context; 10 skills × 500 tokens = 5000 token overhead per session
- **Solution**: SDK loads skill metadata (name + brief description) at initialization; Claude's reasoning selects the matching skill based on metadata; full content injected only then

### Architecture
```
Session Start:
  Load all skill metadata (100 tokens each) into system prompt
  Claude considers: "These skills are available: [metadata list]"

Task Execution:
  If Claude selects skill → Insert full SKILL.md (500 tokens)
  If Claude doesn't select → Skill never fetched

Result:
  Average overhead: (N skills × 100 tokens metadata) + (1 skill × 500 tokens full)
  Without optimization: (N skills × 500 tokens) = 5× larger
```

### Safeguards Against Bloat

1. **Hard Cap**: Maximum 3 full skills injected per session (SDK default)
2. **Ranking**: If 4+ skills match task description, use Qwen3 4B to rank by relevance
3. **Confidence Decay**: Stale skills (last_used > 30 days) deprioritized automatically

### Trade-offs
| Benefit | Cost |
|---------|------|
| Minimal context overhead (constant load) | Skill quality depends on metadata description |
| Skills accumulate without bloat | Requires precise frontmatter formatting |
| Automatic relevance ranking | Skill conflicts not auto-detected |

### Code Location
- `Agent Skills spec` (SDK loads via skill_sources config)
- `bootstrap/skills/coding/*.md` (SKILL.md templates)
- `skill_generator.py` (generates frontmatter + content)

---

## 6. Per-Project Knowledge Isolation vs. Cross-Repo Learning

### Decision
**Store knowledge per-repo by default; enable cross-repo with explicit confidence tiers**

### Rationale
- **Safety**: Repo-specific quirks don't contaminate unrelated projects
- **Flexibility**: Language-specific patterns (Jest retry) can be promoted to shared library after validation
- **Clarity**: Know which context is repo-wide vs. universal

### Scoping Tiers

```
Scope       Example                          Confidence  Source
────────────────────────────────────────────────────────────────
Repo        "This project needs RUST_BACKTRACE=1"   1.0    Automated learning
Language    "Jest needs --forceExit for hanging tests" 0.7  Auto-promoted after 2 uses
Universal   "Always migrate before integration tests" 0.5   Manual promotion
```

### Implementation
- `knowledge.db` per repo under `~/.jarvis/workspace/<owner>/<repo>/`
- `scope` column in knowledge/learnings tables (repo_specific, language, universal)
- Injection policy: repo > language > universal
- Transfer: suggestions first (confidence 0.5), auto-promote after confirmation

### Trade-offs
| Benefit | Cost |
|---------|------|
| No cross-contamination | More files to manage (10+ per project) |
| Auditability (know where knowledge comes from) | Duplication of universal patterns |
| Safe cross-repo transfer | Requires confidence tier management |

### Code Location
- `memory.py` (scope field in schema)
- `knowledge_transfer.py` (promotion logic, not yet implemented)
- `self_learning.py` (confidence scoring)

---

## 7. Dual-Store Architecture (Knowledge vs. Learnings)

### Decision
**Maintain separate tables for user-confirmed knowledge and system-discovered learnings**

### Rationale
- **Knowledge** = High-trust, user-validated (confidence 1.0)
  - "This repo follows REST naming convention"
  - "Integration tests require Docker running"
  - Directly injected into agent context

- **Learnings** = System-discovered patterns (confidence 0.5–0.9)
  - "When X error occurs, add flag Y to command"
  - "This test file needs setup before teardown"
  - Auto-captured by PostToolUse hook; promoted on success

### Workflow

```
Task Execution (PostToolUse Hook)
  ├─ Tool exit code ≠ 0 → Save as execution_record
  ├─ On error recovery: Hash error + solution
  ├─ Check: Does similar learning exist?
  │   ├─ Yes → Increment occurrence counter
  │   └─ No → Create new learning (confidence 0.7)
  └─ On success: Optionally promote learning → knowledge

Learning Promotion
  ├─ 3+ successful uses → Confidence 0.85 (skill candidate)
  ├─ User review → Confidence 0.95
  └─ Explicit approval → Knowledge (confidence 1.0)
```

### Trade-offs
| Benefit | Cost |
|---------|------|
| Confidence transparency | Extra table with similar structure |
| Gradual trust building | Manual review for promotion |
| Audit trail (learnings → knowledge history) | Need to decide promotion thresholds |

### Code Location
- `schema.sql` (learnings vs. knowledge tables)
- `self_learning.py` (learning creation + promotion logic)
- `memory.py` (confidence scoring)

---

## 8. Idle Mode: Background Optimization During User Inactivity

### Decision
**Detect 10+ minutes of HID idle; trigger background skill generation, context rebuild, learning re-verification**

### Rationale
- **Problem**: Knowledge system grows but isn't continuously optimized during active work
- **Solution**: Use idle Mac time (screen locked, no input) for non-blocking improvements
- **Safety**: All changes queued; only applied on explicit approval

### State Machine

```
ACTIVE
  ├─ User keyboard/trackpad input detected
  ├─ Run normal agent pipeline
  └─ Accumulate learnings, skill candidates

           ↓ (10 min no HID input)

IDLE
  ├─ IOKit detects inactivity
  ├─ Disable low-priority tasks (not urgent)
  ├─ Start background queue:
  │  ├─ HIGH: Re-verify learnings (validation)
  │  ├─ MEDIUM: Rebuild context layers (L1–L4)
  │  └─ LOW: Generate skills (GLM 4.7 batch)
  └─ Consume freed RAM (Qwen3, containers unloaded)

           ↓ (User returns / HID activity)

ACTIVE
  ├─ Pause background tasks
  ├─ Reload Qwen3 + containers
  └─ Show new skills + updated knowledge to user

HIBERNATED (Memory Pressure > 80%)
  ├─ Save all container state to disk
  ├─ Unload Qwen3 4B
  ├─ Minimal daemon (~300MB)
  └─ Resume on memory pressure drop
```

### Trade-offs
| Benefit | Cost |
|---------|------|
| 24/7 optimization without user slowdown | Idle detection adds system overhead |
| Better knowledge quality over time | Background tasks consume power |
| Graceful memory management | Requires state checkpoint/restore |

### Code Location
- `idle_mode.py` (state machine, background task queue)
- `JarvisApp.swift` (IOKit HID monitoring)
- `DispatchSource` integration for memory pressure

---

## 9. MCP Health Checks: Catch Silent Failures

### Decision
**Pre-session ping for every MCP server; quarantine failures with user notification**

### Rationale
- **Danger**: Unstable MCP servers silently return wrong data → Claude reasons on garbage
- **Example**: Outdated yfinance API returns empty results → Stock agent makes bad recommendations
- **Prevention**: 2-second health check before session; exclude failed servers

### Health Check Flow

```
Session Boot
  ├─ For each configured MCP server:
  │  ├─ Send: simple_ping() or list_tools()
  │  ├─ Timeout: 2 seconds
  │  └─ Result:
  │      ├─ Success → Log health_ok, include in session
  │      ├─ Timeout → Add to quarantine_list, notify user
  │      └─ Error → Add to quarantine_list, log reason
  └─ Excluded servers not registered with SDK

Notification (Slack + Notification Center)
  "⚠️ jarvis-browser MCP failed to respond.
   Excluding from this session. Check logs: ~/.jarvis/logs/"
```

### Trade-offs
| Benefit | Cost |
|---------|------|
| Prevents silent data corruption | 2s per server (parallelizable) |
| User visibility (failures don't go unnoticed) | May exclude good servers (transient failures) |
| Automatic quarantine prevents cascading | Requires per-server health commands |

### Code Location
- `mcp_health.py` (health_check() function)
- `daemon.py` (integration at boot)
- `notifications.py` (failure dispatch)

---

## 10. SDK as Black Box (No Modification)

### Decision
**Configure SDK via ClaudeAgentOptions but never modify SDK internals**

### Rationale
- **Benefit 1**: Automatically inherit SDK improvements (bug fixes, new features)
- **Benefit 2**: Stay compatible with official Claude Code updates
- **Benefit 3**: Simpler upgrades (no merge conflicts with SDK internals)

### Jarvis Responsibility

✅ **DO**:
- Configure via ClaudeAgentOptions (system prompt, MCP servers, tools, hooks, skills directory)
- Intercept via hooks (PreToolUse, PostToolUse, PreMessage, PostMessage)
- Provide data/context (knowledge system, token budgets, execution records)
- Add MCP servers (via mcp_servers/ directory)

❌ **DON'T**:
- Modify SDK source code
- Override agent loop orchestration
- Change SDK's tool execution
- Intervene in context compaction

### Trade-offs
| Benefit | Cost |
|---------|------|
| Auto-inherit SDK improvements | Cannot customize deep orchestration |
| Clean architectural boundary | Workarounds needed if SDK limitations exist |
| Future-proof upgrades | Some optimizations must work within SDK constraints |

### Code Location
- `orchestrator.py` (SDK initialization + hook setup)
- `hooks.py` (Pre/PostToolUse, Pre/PostMessage implementations)
- `config.py` (ClaudeAgentOptions configuration)

---

## Comparison Matrix: Key Decisions

| Decision | Primary Choice | Alternative | Why Chosen |
|----------|---|---|---|
| SDK Architecture | Single session + subagents | Multiple instances | 20–30s init overhead per instance |
| Container Runtime | Apple Containerization | Docker Desktop | Zero idle overhead, hardware isolation |
| Vector DB | sqlite-vec | FAISS | ACID transactions + relational queries |
| Model Routing | 3-tier (Qwen3/GLM/Foundation) | Single cloud model | 60–80% token savings |
| Skill Loading | Progressive (metadata→full) | All skills at startup | Prevent context bloat |
| Knowledge Scope | Per-repo + tiers | Global | Safety + auditability |
| Knowledge Store | Dual (learnings+knowledge) | Single unified | Confidence transparency + auditing |
| Idle Optimization | Active (background tasks) | Passive (none) | 24/7 knowledge improvement |
| MCP Health | Pre-session checks | None | Prevent silent data corruption |
| SDK Integration | Black box (configure only) | Modify internals | Future-proof upgrades |

---

## Decision Impacts on Implementation

### Weeks 1–2 (Foundation)
- Implement dual-store activation (learnings table)
- Integrate MCP health checks
- **Decision Impact**: Learning activation unblocks skill generation; health checks catch integration issues early

### Weeks 3–4 (Intelligence)
- Build model router (3-tier)
- Implement MLX Qwen3 wrapper
- **Decision Impact**: Model routing enables 60–80% token savings; complexity well-contained in one module

### Weeks 5–6 (Knowledge)
- Activate skill generation pipeline
- Implement FSEvents watching
- **Decision Impact**: Progressive skill loading prevents bloat; scope isolation enables safe learning

### Weeks 7–8 (Optimization)
- Complete idle mode state machine
- Implement background task queue
- **Decision Impact**: Idle mode drives continuous improvement without user impact

---

## Risk Mitigation via Decisions

| Design Decision | Prevents Risk |
|---|---|
| Apple Containerization | Code injection attacks (per-VM isolation) |
| MCP health checks | Silent data corruption from unstable APIs |
| Dual-store (learnings vs. knowledge) | Knowledge rot (stale patterns remain in context) |
| Progressive skill loading | Prompt bloat from accumulated skills |
| Pre-repo knowledge isolation | Cross-project contamination |
| Black-box SDK integration | Breaking changes on SDK updates |

---

## Future Extensions (Built into Design)

1. **Phase 2: Stock Agent** — Uses same dual-store + learning system; different MCP servers
2. **Phase 3: Research Agent** — Cross-domain pattern transfer via scope tiers
3. **Phase 4: Self-Extension** — Autonomous MCP discovery + skill generation (powered by learning system)

All architectural decisions support these extensions without modification.

---

## Appendix: Decision Timeline

- **January 2026**: PRD drafted; 10 decisions crystallized
- **February 2026**: Implementation analysis (this document)
- **Weeks 1–8**: Phase 1 implementation validates decisions
- **Weeks 9+**: Decisions inform Phase 2–4 extensions

---

**Document Version**: 1.0
**Date**: February 9, 2026
**Status**: Ready for Architecture Review

