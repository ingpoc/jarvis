# JARVIS

## Self-Extending Autonomous Development Agent

**Product Requirements Document**
**Version 2.0 • February 2026**

| Field | Value |
|-------|-------|
| **Author** | Gurusharan |
| **Status** | Production Architecture |
| **Foundation** | Claude Agent SDK (Python) |
| **Target Platform** | macOS 26 Tahoe • Apple Silicon |
| **Classification** | Internal — Engineering |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals and Non-Goals](#3-goals-and-non-goals)
4. [System Architecture](#4-system-architecture)
5. [Three-Tier Intelligence Layer](#5-three-tier-intelligence-layer)
6. [Self-Learning Knowledge System](#6-self-learning-knowledge-system)
7. [Self-Evolution Engine](#7-self-evolution-engine)
8. [Container Runtime](#8-container-runtime)
9. [macOS Native Integration](#9-macos-native-integration)
10. [Resource Management](#10-resource-management-24gb-mac-mini)
11. [Bootstrap and Cold Start Strategy](#11-bootstrap-and-cold-start-strategy)
12. [Multi-Domain Evolution Path](#12-multi-domain-evolution-path)
13. [Implementation Roadmap](#13-implementation-roadmap)
14. [Technical Stack Summary](#14-technical-stack-summary)
15. [Success Metrics](#15-success-metrics)
16. [Risks and Mitigations](#16-risks-and-mitigations)
17. [Appendix: Key Technical Decisions](#17-appendix-key-technical-decisions)

---

## 1. Executive Summary

Jarvis is a Mac-native, self-extending autonomous development agent built as a persistent knowledge and domain extension layer on top of the Claude Agent SDK. It does not replace Claude Code or compete with its orchestration capabilities. Instead, Jarvis wraps the SDK to add what it cannot provide on its own: persistent memory between sessions, self-learning from errors, autonomous skill and MCP server creation, container-isolated execution, and multi-domain extensibility.

The agent operates on a 24GB Apple Silicon Mac Mini running macOS 26 Tahoe, leveraging Apple-native frameworks for container isolation, on-device model inference, and system-level performance optimizations. It uses a three-tier intelligence routing strategy that balances speed, capability, and cost across local models (Qwen3 4B via MLX), cloud APIs (GLM 4.7 via Z.AI), and Apple's on-device Foundation Models framework.

Jarvis is designed to grow autonomously. Every error it fixes becomes a permanent learning. Every repeated task pattern triggers automatic skill generation. Every integration gap can be filled by discovering or writing new MCP servers. The compound effect of this self-improvement loop means the system becomes measurably more efficient with each week of use, reducing API token consumption by 60–80% for recurring workflows.

### Core Positioning

**Jarvis = Persistent Knowledge + Domain Extension Layer on Claude Agent SDK**

It adds knowledge persistence, multi-domain subagents, MCP health validation, bootstrap skill kits, a self-extension loop, and cross-domain learning.

The SDK provides agent loop orchestration, tool execution and routing, the hook pipeline, context management, MCP server communication, and built-in tools.

---

## 2. Problem Statement

### 2.1 The Stateless Agent Gap

Current AI coding agents, including Claude Code, operate statelessly. Each session starts fresh with zero knowledge of past interactions, resolved bugs, architectural decisions, or learned preferences. This creates three compounding problems:

- **Repeated debugging**: When an agent encounters an error it has already solved in a previous session, it must rediscover the fix from scratch. In codebases with non-obvious quirks (framework-specific workarounds, environment-specific configurations, undocumented API behaviors), this rediscovery can consume significant tokens and time.

- **Lost architectural context**: Agents cannot recall prior decisions about code structure, naming conventions, or design patterns established across sessions. Each new session risks introducing inconsistencies.

- **No skill accumulation**: Agents cannot learn from success. A task performed ten times will consume the same tokens on the tenth execution as the first. There is no mechanism for the agent to encode procedural knowledge into reusable workflows.

### 2.2 The Single-Domain Constraint

AI agents are typically confined to a single domain. A coding agent cannot assist with stock analysis. A research agent cannot generate code. As agent capabilities mature, users increasingly need unified orchestration across multiple domains, with the ability to transfer learnings between them. Testing patterns from software development, for example, map directly to backtesting strategies in financial analysis.

### 2.3 The Cold Start Problem

A new agent installation starts with zero accumulated intelligence. Without bootstrap knowledge, the first days of use deliver worse performance than the raw SDK alone, because the orchestration overhead (container boot, context loading, model routing) adds latency without any offsetting intelligence benefit. The system must be useful from day one, not day thirty.

---

## 3. Goals and Non-Goals

### 3.1 Goals

| ID | Goal | Description |
|----|------|-------------|
| **G1** | Persistent Learning | Never debug the same error twice. Every error-fix pattern is stored per-repo and retrieved automatically in future sessions. |
| **G2** | Autonomous Skill Creation | Detect repeated task patterns (3+ occurrences) and auto-generate reusable Agent Skills (SKILL.md files) during idle time. |
| **G3** | Container-Isolated SDLC | Full software development lifecycle (clone, develop, test, review, deploy) inside isolated Linux containers using Apple Containerization. |
| **G4** | Three-Tier Intelligence | Route tasks to the optimal model tier based on latency requirements, complexity, and cost: Qwen3 4B local, GLM 4.7 API, or Apple Foundation Models. |
| **G5** | Multi-Domain Extensibility | Architecture supports adding domain-specific subagents (coding, stocks, research) via the SDK's built-in subagent system. |
| **G6** | Day-One Usefulness | Ship with bootstrap skill kits, pre-seeded heuristics, and clone-time context indexing so the system delivers value immediately. |
| **G7** | Mac-Native Performance | Leverage macOS-native APIs (Containerization, Foundation Models, MLX, FSEvents, Core Spotlight, XPC) for zero-overhead integration. |
| **G8** | Self-Extension | Discover or auto-generate MCP servers when integration gaps are detected, with health validation and runtime quarantine. |

### 3.2 Non-Goals (Hard Boundaries)

| Non-Goal | Rationale |
|----------|-----------|
| **Competing orchestrator** | Jarvis does NOT replace the Claude Agent SDK's agent loop. The SDK handles all orchestration, tool execution, and context management. |
| **Custom skill selection logic** | Claude's LLM reasoning selects which skills to invoke. Jarvis does not implement algorithmic skill matching, embedding-based routing, or skill conflict detection graphs. |
| **Context window management** | The SDK's automatic context compaction handles conversation overflow. Jarvis does not implement custom summarization or token tracking. |
| **Meta-orchestration** | No agent-that-orchestrates-agents. Subagents communicate only with the parent via the SDK's Task tool. No peer-to-peer messaging or nested subagents. |
| **Custom tool execution** | All tool execution (Read, Write, Bash, Edit, Grep, Glob) is handled by the SDK. Jarvis provides data and configuration, never execution logic. |

---

## 4. System Architecture

### 4.1 Six-Layer Stack

Jarvis is organized into six distinct layers, each with a clear responsibility boundary. The critical architectural decision is the separation between Layers 2 and 3: **Jarvis Core provides data and configuration; the Claude Agent SDK provides orchestration and execution.**

| Layer | Name | Technology | Responsibility |
|-------|------|------------|----------------|
| **Layer 1** | macOS Shell | SwiftUI, XPC, ServiceManagement | UI, idle detection, file watching, daemon management, auto-start on login |
| **Layer 2** | Jarvis Core | Python 3.12+, SQLite + sqlite-vec | Knowledge persistence, MCP health validation, subagent coordination, model routing |
| **Layer 3** | Claude Agent SDK | claude-agent-sdk (Python) | Agent loop orchestration, tool execution, hook pipeline, context management, skill loading |
| **Layer 4** | Domain Subagents | SDK AgentDefinition + Task tool | Domain-specific specialists: coding, stocks, research (via SDK's built-in subagent system) |
| **Layer 5** | Container Runtime | Apple Containerization framework | Per-repo Linux VMs with hardware-level isolation, sub-second boot, zero idle overhead |
| **Layer 6** | MCP Ecosystem | Model Context Protocol servers | Domain tools (GitHub, yfinance), Mac-native tools (Spotlight, FSEvents), self-created tools |

#### Architectural Principle: Data vs. Orchestration

Jarvis touches Layers 1, 2, 4, 5, and 6. Layer 3 (Claude Agent SDK) is treated as a black box. Jarvis configures it via ClaudeAgentOptions (system prompt, MCP servers, tools, hooks, skills directory, permission mode) but never intervenes in the agent loop, tool execution, or context compaction. This separation ensures Jarvis benefits from every SDK improvement without modification.

### 4.2 Agent Core Implementation Pattern

Each domain agent wraps a ClaudeSDKClient session with domain-specific configuration. The pattern is identical across domains; only the system prompt, MCP servers, skills directory, and hooks change.

**Session lifecycle**: Build layered context from knowledge system → Validate MCP server health → Configure SDK options (system prompt, MCP servers, allowed tools, hooks, working directory, skill sources) → Create ClaudeSDKClient session → Stream responses → Capture execution records via PostToolUse hooks for self-learning loop.

**Hook pipeline**: The SDK's hook system provides lifecycle interception points. Jarvis uses:

- **PreToolUse** for safety and budget checks
- **PostToolUse** for execution record capture and learning extraction
- **PreMessage** for context injection from the knowledge system
- **PostMessage** for token accounting and pattern detection

### 4.3 Subagent Architecture

Jarvis uses the Claude Agent SDK's built-in subagent system (Task tool + AgentDefinition) rather than running multiple ClaudeSDKClient instances. This is a deliberate architectural decision based on two constraints discovered during technical research:

**Constraint 1**: Each ClaudeSDKClient instance spawns a Claude Code CLI subprocess that takes 20–30+ seconds to initialize and accumulates significant memory. The SDK is optimized for single-user CLI usage, not multi-tenant deployment.

**Constraint 2**: SDK subagents cannot spawn their own subagents (no nesting) and communicate only with the parent (no peer-to-peer messaging). This limits coordination patterns but simplifies the architecture.

Jarvis runs a single long-lived SDK session with domain-specific subagents registered via AgentDefinition. Claude autonomously decides when to delegate based on subagent descriptions. Multiple subagents can run in parallel, each with an isolated context window, restricted tool set, and optionally a different model.

---

## 5. Three-Tier Intelligence Layer

The intelligence layer routes tasks to the optimal model based on latency requirements, task complexity, cost sensitivity, and network availability. The three tiers are complementary, not competing: each serves a distinct performance envelope.

| Tier | Location | RAM | Speed | TTFT | Cost | Tasks |
|------|----------|-----|-------|------|------|-------|
| **Tier 1: Qwen3 4B** | Local (MLX) | ~3 GB | 80–120 t/s | <100ms | Free | Autocomplete, error triage, commit messages, inline docs, context pre-filtering |
| **Tier 2: GLM 4.7** | API (Z.AI) | 0 GB | 50–80 t/s | 1–3s | $0.60/M in | Multi-file generation, complex debugging, architecture analysis, test suites, skill/MCP creation |
| **Tier 3: Foundation Models** | System (Apple) | OS-managed | 70–100 t/s | <200ms | Free | NL command parsing (@Generable), classification, search query generation, task routing |

### 5.1 Router Decision Logic

| Condition | Route To | Rationale |
|-----------|----------|-----------|
| Latency < 200ms required? | Qwen3 4B (local) | API round-trip kills UX for latency-sensitive tasks |
| Classification or NL parsing? | Foundation Models | Zero cost, type-safe via @Generable macro; 4,096-token context limit |
| Multi-file reasoning or 1000+ LOC? | GLM 4.7 (thinking mode) | 200K context, interleaved thinking, 73.8% SWE-bench Verified |
| Idle mode batch task? | GLM 4.7 (queue, batch) | Background tasks tolerate API latency |
| Network offline? | Qwen3 4B (all tasks) | Graceful degradation to local-only mode |
| Token budget exhausted? | Qwen3 4B + smaller scope | Enforce leaner execution paths |
| Skill exists for pattern? | Skip API reasoning | Use skill directly, 60–80% token savings |

### 5.2 Token Budget Management

A token budget manager tracks API consumption by task type, learns which tasks are expensive versus cheap, and enforces optimization paths when skills or cached context exist. Three optimization strategies operate in concert:

1. **Context pre-filtering**: Before any API call, Qwen3 4B locally selects the relevant subset of files from the workspace. This reduces the context payload sent to GLM 4.7 by 60–80%, directly cutting API costs and improving reasoning quality by removing noise.

2. **Skill shortcutting**: When a skill exists for a detected pattern, the full API reasoning step is bypassed. The skill's procedural instructions are injected directly, and the agent executes without exploratory reasoning.

3. **Incremental context**: The knowledge system sends function signatures and module metadata first. Full implementations are fetched only when the agent explicitly requests them, reducing initial context load by 40–60%.

### 5.3 Apple Foundation Models: Design Constraints

Apple's Foundation Models framework provides a free, offline, OS-managed 3B parameter model with sub-200ms latency and guaranteed structured output via the @Generable macro. However, it has a critical constraint: a 4,096-token context window that includes input, output, instructions, and tool calls combined. This makes it unsuitable as a general routing or orchestration layer.

Jarvis uses Foundation Models exclusively as a narrow, fast first-pass classifier for task type detection, intent categorization, and simple entity extraction where the input fits within approximately 2,000 tokens. It is an optional fast path, not a required component. The framework is Swift-only, requiring XPC bridge communication from Jarvis's Python core.

---

## 6. Self-Learning Knowledge System

The knowledge system is Jarvis's compound interest engine: every error fixed, every pattern discovered, every architectural decision recorded makes the system permanently smarter. Inspired by OpenAI's Kepler architecture ("context gets you 80–90%, memory provides the final corrections") and Foundation Capital's context graph thesis (decision traces as systems of record).

### 6.1 Dual-Store Architecture

Each repository maintains two distinct knowledge stores in a single SQLite database with sqlite-vec for vector similarity search:

- **Knowledge (curated)**: Validated architectural decisions, business rules, and user-confirmed preferences. Created explicitly by the user or promoted from learnings after validation. High trust, directly injected into agent context.

- **Learnings (discovered)**: Error-fix patterns found through trial and error, automatically captured by PostToolUse hooks. Managed by the system: created on successful error resolution, demoted when stale, re-verified during idle mode.

### 6.2 Storage Schema

| Table | Key Columns |
|-------|-------------|
| **learnings** | id, pattern, solution, domain, success_rate, last_validated, files_referenced, created_at, access_count |
| **knowledge** | id, key, value, domain, source (user/promoted), confidence, created_at |
| **execution_records** | id, tool_name, inputs (JSON), exit_code, files_touched (JSON), led_to_success, domain, tokens_used |
| **skill_candidates** | id, pattern_hash, occurrence_count, first_seen, last_seen, promoted_to_skill |
| **token_usage** | id, task_type, model_tier, tokens_in, tokens_out, cost_usd, timestamp |

### 6.3 Six-Layer Context Architecture

Rather than sending raw source code to the agent, Jarvis builds a layered metadata representation that provides maximum context with minimum tokens. This follows the RAG-over-metadata pattern: retrieve structured metadata about the codebase, not the code itself.

| Layer | Name | Contents | Source | Volatility |
|-------|------|----------|--------|------------|
| **L1** | Repo Structure | Purpose, language, framework, architecture patterns | Inferred on clone + user annotation | Stable |
| **L2** | Module Graph | Package/module relationships, dependency flow | AST analysis, rebuilt on major changes | Semi-stable |
| **L3** | Interface Signatures | Function signatures, types, exports (NOT implementations) | AST extraction, indexed in Core Spotlight | Updated on file change |
| **L4** | Test & Quality | Coverage, recent failures, quality metrics | Parsed from test runner output | Updated per test run |
| **L5** | Learned Corrections | Per-repo quirks, error patterns, fixes | Accumulated from sessions | Growing |
| **L6** | Runtime State | Current branch, uncommitted changes, active errors | Live via FSEvents + git status | Ephemeral |

### 6.4 Self-Learning Loop

The self-learning loop operates automatically after every task execution. It is the mechanism by which Jarvis converts runtime experience into persistent intelligence.

- **Retrieve**: Load repo-specific knowledge, learnings, and applicable skills from SQLite + sqlite-vec.
- **Triage**: Qwen3 4B locally classifies task complexity and selects relevant context layers.
- **Execute**: Claude Agent SDK session runs inside the container with full tool access.
- **Capture**: PostToolUse hooks record execution records (tool, inputs, exit code, files touched, success).
- **Learn**: On error resolution, save the error-fix pattern as a learning. On success, optionally promote to knowledge.
- **Optimize**: Update token metrics, increment pattern counters, flag skill candidates, refresh context metadata.

### 6.5 Knowledge Pruning and Validation

Learnings decay without pruning. What was true last month may be wrong after a refactor. Three mechanisms prevent knowledge rot:

1. **Proactive invalidation**: FSEvents monitors the workspace. When files referenced by a learning undergo major changes (>30% of lines rewritten), the learning is flagged for re-validation automatically.

2. **Passive decay**: Each learning tracks `last_validated` and `access_count`. Learnings that haven't matched in N runs are auto-demoted in confidence score.

3. **Idle re-verification**: During idle mode, the top learnings by access frequency are re-verified against the current codebase state. Outdated learnings are marked stale.

### 6.6 Cross-Repo Learning Transfer

Knowledge is per-repo by default, which is safe. But some patterns are universal: Jest needs `--forceExit` for hanging tests, migrations must run before integration tests, Node processes benefit from specific memory flags. Jarvis implements tiered knowledge scoping to enable cross-repo learning without contaminating local context.

| Scope | Example | Injection Policy | Trust Level |
|-------|---------|------------------|-------------|
| **Repo-specific** | "This repo needs RUST_BACKTRACE=1" | Injected directly | Highest |
| **Language-specific** | "Jest tests are flaky — retry once" | Suggested, auto-promoted after 2 confirmations | Medium |
| **Universal** | "Always run migrations before integration tests" | Suggested, requires explicit promotion | Lowest |

---

## 7. Self-Evolution Engine

### 7.1 Autonomous Skill Creation

Skills are Agent Skills spec-compliant SKILL.md files containing YAML frontmatter and procedural instructions. The SDK loads skill metadata (name + description, approximately 100 tokens each) at session start and injects full skill content only when Claude's reasoning determines a match. This progressive disclosure architecture keeps the baseline context overhead low.

**Skill Lifecycle:**

1. **Discover**: PostMessage hooks detect repeated task patterns via pattern hashing.
2. **Detect**: When a pattern reaches 3+ occurrences, it is flagged as a skill candidate in the `skill_candidates` table.
3. **Generate**: During idle mode, GLM 4.7 generates a SKILL.md with trigger patterns, step-by-step instructions, and example code.
4. **Validate**: The generated skill is tested against past execution records to verify it produces correct outcomes.
5. **Register**: The skill is placed in the repo's `.claude/skills/` directory and becomes available for all future SDK sessions.

**Skill Injection Safeguards**

Skills accumulate and can cause prompt bloat or conflicting instructions. Three safeguards prevent this:

1. **Progressive disclosure**: Only skill metadata (name + description) is loaded at session start. Full content is loaded only when Claude selects the skill, following the Agent Skills spec's design.

2. **Hard cap**: Maximum 3 full skills injected per session. If more match, Qwen3 4B locally ranks by relevance to the specific task.

3. **Confidence decay**: Each skill tracks `success_rate`, `last_used`, and `average token savings`. Low-confidence or stale skills are deprioritized automatically.

### 7.2 Autonomous MCP Server Discovery and Creation

When a task requires an external integration (database, API, service) with no existing MCP server, Jarvis follows a three-stage process:

1. **Search**: Query the MCP Registry (GitHub/npm) for existing servers matching the integration requirement.
2. **Propose**: If found, present the server for user approval before installation. If not found, generate a declarative spec (inputs, outputs, permissions) for user review.
3. **Create**: On approval, GLM 4.7 generates the MCP server code. The server is installed in `~/.jarvis/mcp_servers/` and registered in the MCP registry.

#### MCP Health Validation

Every MCP server gets an automatic health check before first use in each session. A simple ping/validation call runs with a 2-second timeout. Servers that fail are silently excluded from the session and the user is notified. This catches the most dangerous failure mode: silent coupling to unstable APIs that return incorrect data, which Claude would then reason on. Health checks run inside the container's network namespace, so failures are contained.

### 7.3 Idle Mode Processing

When the Mac has been idle for 10+ minutes (no HID input detected via IOKit), Jarvis enters idle mode and performs background optimization tasks with the additional RAM freed by user application inactivity:

- Generate skills from accumulated pattern candidates
- Rebuild and refresh context metadata layers (L1–L4)
- Re-verify top learnings against current codebase state
- Process queued article learning pipeline entries
- Generate token optimization reports
- Run weekly capability assessment: analyze task distribution, identify coverage gaps, propose new skill or MCP creation

---

## 8. Container Runtime

### 8.1 Apple Containerization Framework

Jarvis uses Apple's Containerization framework (Apache 2.0, v0.6.0) instead of Docker Desktop. Each Linux container runs inside its own dedicated lightweight VM using Apple's Virtualization.framework, providing hardware-level isolation that Docker's shared-kernel model cannot match for running agent-generated code.

| Metric | Apple Containerization | Docker Desktop | Jarvis Impact |
|--------|------------------------|----------------|---------------|
| **Cold start** | ~1.2s (M1 Pro) <br> ~0.5s (warm VM) | ~5-10s | Acceptable; containers persist across tasks |
| **Idle overhead** | Zero (no background VM) | 500MB–2GB | Critical advantage for 24GB system |
| **Per-container isolation** | Hardware (dedicated VM) | Shared kernel | Safer for agent-generated code |
| **Networking** | Dedicated IP (192.168.64.x) | Port mapping | Simpler multi-container setup |
| **I/O performance** | 31× more ops (stress-ng) | Baseline | Faster test execution |
| **Licensing** | Free (Apache 2.0) | $9–24/user/month (org) | No licensing overhead |
| **Maturity** | v0.6.0, no Compose | Mature ecosystem | Docker as fallback for complex scenarios |

### 8.2 Per-Repo Workspace Structure

Each repository gets an isolated workspace with its own container configuration, knowledge database, context metadata, skills, and MCP servers. The workspace is bind-mounted read-write into the container VM.

`~/.jarvis/workspace/<owner>/<repo>/` contains:

- The cloned repository
- `.jarvis/` directory holding:
  - `container.toml` (container configuration)
  - `knowledge.db` (per-repo SQLite database)
  - `context/` (layered metadata cache)
  - `skills/` (repo-specific generated skills)
  - `mcp_servers/` (repo-specific MCP servers)

### 8.3 SDLC Pipeline

The container supports the full software development lifecycle:

| Stage | Operations |
|-------|------------|
| **Clone** | git clone, detect language/framework, build container image, generate initial context metadata, index signatures in Core Spotlight |
| **Develop** | Claude Agent SDK session in container, multi-file generation, FSEvents file watching, auto-format/lint, skill-assisted patterns |
| **Test** | Unit tests via container exec, integration tests with services, dev server for e2e (Playwright MCP), API testing, coverage reports |
| **Review** | Automated code review, security scanning via MCP, performance analysis, diff summary, PR description generation |
| **Learn** | Capture error-fix patterns, update knowledge.db, detect skill candidates, track token efficiency, refresh context layers |

---

## 9. macOS Native Integration

Each macOS-native API is chosen for a specific performance or capability advantage over cross-platform alternatives. The integration points are concentrated in the SwiftUI shell layer, with XPC bridging to the Python core where necessary.

| Framework | Usage in Jarvis | Advantage |
|-----------|-----------------|-----------|
| **Apple Containerization** | Per-repo Linux VMs, OCI images, bind-mount workspaces | 10× lighter than Docker, zero idle overhead, hardware isolation |
| **Foundation Models** | @Generable structured output, task classification | Zero cost, OS-managed RAM, <200ms latency, type-safe |
| **MLX Swift** | Run Qwen3 4B (4-bit quantized) locally | 80–120 t/s, unified memory, no CPU↔GPU copies |
| **FSEvents** | Monitor workspace for file changes, trigger context rebuild | Kernel-level, sub-ms notification, survives restarts |
| **Core Spotlight** | Index function signatures, module metadata | System-level search <10ms, integrates with macOS Spotlight |
| **XPC Services** | Process isolation between SwiftUI shell and Python daemon | Memory isolation, crash recovery, privilege separation |
| **Keychain Services** | Store API keys (GLM 4.7, GitHub tokens, MCP credentials) | Hardware-backed (Secure Enclave), never plaintext |
| **ServiceManagement** | Register Jarvis daemon as login item | Proper macOS citizen, survives logout/restart |
| **OSLog** | Structured logging with categories and levels | Zero-cost when not observed, integrates with Console.app |
| **DispatchSource** | Memory pressure monitoring, idle detection timers | Kernel-level event sources, emergency container hibernation |
| **Network.framework** | High-performance networking for GLM 4.7 API | Connection multiplexing, automatic TLS, native stack |

### 9.1 Mac-Native MCP Servers

Three custom MCP servers expose macOS capabilities to the Claude Agent SDK as tools:

- **mcp-spotlight**: Wraps Core Spotlight's NSMetadataQuery for sub-10ms code search across indexed function signatures, module metadata, and file purposes. Significantly faster than grep for structured queries.

- **mcp-fsevents**: Exposes FSEvents file watching as a tool. Enables proactive error detection: when a source file changes but its corresponding test file doesn't, the agent can flag potential test coverage gaps.

- **mcp-vision**: Wraps Apple's Vision framework for UI testing. Can analyze screenshots from the dev server to verify visual rendering, detect layout regressions, and compare against reference images.

---

## 10. Resource Management (24GB Mac Mini)

### 10.1 RAM Budget

#### Active Mode

| Component | RAM | Notes |
|-----------|-----|-------|
| macOS + User Apps | 9.5 GB | Baseline system + typical user workload |
| Qwen3 4B (MLX, 4-bit) | 3.0 GB | Persistent in unified memory |
| Active Container | 1.5 GB | Linux VM with runtime + tools |
| Jarvis Core + Knowledge | 0.5 GB | Python process + SQLite |
| **Free Headroom** | **9.5 GB** | Available for additional containers or burst |

#### Idle Mode

| Component | RAM | Notes |
|-----------|-----|-------|
| macOS + User Apps | 7.0 GB | Reduced without active user interaction |
| Qwen3 4B | 0 GB | Unloaded during idle processing |
| Containers | 0 GB | Hibernated; state saved to disk |
| Jarvis Core | 0.3 GB | Minimal daemon |
| **Free for Batch Ops** | **16.7 GB** | Available for idle mode tasks |

### 10.2 State Machine Transitions

Jarvis operates in three states:

1. **Active** (user is working, all systems live)
2. **Idle** (screen locked 10+ minutes, background processing)
3. **Hibernated** (memory pressure critical, all non-essential components suspended)

Transitions are triggered by HID input detection via IOKit, memory pressure via DispatchSource monitoring `kern.memorystatus`, and explicit user commands.

**Emergency hibernation**: When memory pressure reaches critical level, Jarvis immediately hibernates all containers (saving state to disk), unloads Qwen3 4B, and reduces to a minimal daemon footprint of approximately 300MB. Recovery is automatic when pressure subsides.

---

## 11. Bootstrap and Cold Start Strategy

The cold start problem is the biggest usability risk: a fresh Jarvis installation has zero skills, zero learnings, and zero context metadata. Without mitigation, the first week delivers worse performance than Claude Code alone because orchestration overhead is not yet offset by accumulated intelligence.

### 11.1 Bootstrap Skill Kits

Jarvis ships with pre-written Agent Skills for common development patterns, copied to the appropriate `.claude/skills/` directory on first run.

| Domain | Included Skills |
|--------|-----------------|
| **Coding Domain** | rest-endpoint-scaffold.md, test-setup.md, git-workflow.md, error-classification.md, dockerfile-generation.md, code-review-checklist.md |
| **Stock Domain (Phase 2)** | portfolio-analyzer.md, technical-indicators.md, backtest-strategy.md, risk-metrics.md |
| **Research Domain (Phase 3)** | paper-analyzer.md, citation-tracker.md, knowledge-graph-builder.md |

### 11.2 Clone-Time Initialization

When a repository is first cloned, Jarvis immediately runs a bootstrap sequence:

1. Detect language and framework from file patterns and package manifests
2. Generate initial context metadata layers L1 (repo structure) and L2 (module graph) via AST analysis
3. Extract and index function signatures (L3) into Core Spotlight
4. Run test suite if detected to populate L4 (test and quality)
5. Seed language-specific heuristics from the universal knowledge tier

### 11.3 Pre-Seeded Universal Heuristics

Jarvis ships with a read-only set of universal and language-specific heuristics derived from common development patterns. These are suggestions, not injections: they appear as recommendations during the first sessions and are promoted to repo-specific learnings only after user confirmation. Examples include Jest flaky test retry strategies, Node.js memory flags for large builds, migration-before-test ordering, and CI environment quirks.

---

## 12. Multi-Domain Evolution Path

Jarvis is designed to extend beyond software development into any domain that benefits from persistent knowledge, structured analysis, and tool integration. The extension mechanism uses the same subagent pattern for every domain.

| Phase | Name | Timeline | Objective |
|-------|------|----------|-----------|
| **Phase 1** | Autonomous Coding Agent (v2.0) | 6–8 weeks | Match Claude Code capabilities plus persistent learning, container isolation, and Mac-native performance |
| **Phase 2** | Stock Selection Agent (v2.1) | 4–6 weeks | Financial domain via StockAgent subagent with yfinance, SEC filings, and technical analysis MCP servers |
| **Phase 3** | Research Agent (v2.2) | 4 weeks | Multi-domain orchestration with ResearchAgent for paper analysis, cross-domain coordination |
| **Phase 4** | Self-Extension (v2.3) | Ongoing | Autonomous capability expansion: detect new domains, generate MCP servers and skills, self-register subagents |

### 12.1 Cross-Domain Knowledge Transfer

Some learnings transfer between domains with adaptation. Testing patterns from software development map to backtesting strategies in financial analysis. Error handling patterns map to risk management. The transfer mechanism uses lower confidence scores (0.6 vs 1.0 for native learnings) and requires confirmation before promotion. Transfer is always suggestion-based, never automatic injection.

### 12.2 Domain Self-Extension

In Phase 4, Jarvis can autonomously bootstrap new domains when it detects tasks that don't match existing subagent capabilities. The process follows a structured sequence:

1. Create a domain workspace
2. Research and discover or generate required MCP servers
3. Generate domain-specific bootstrap skills
4. Create a domain knowledge database
5. Register a new subagent

All MCP server creation requires explicit user approval before installation.

---

## 13. Implementation Roadmap

### Phase 1: Autonomous Coding Agent (Weeks 1–8)

**Weeks 1–2: Foundation**

- SwiftUI shell with XPC daemon communication
- Python core with SQLite + sqlite-vec storage
- Apple Containerization integration (with Docker fallback)
- Basic MCP health check infrastructure
- ServiceManagement auto-start registration

**Weeks 3–4: SDK Integration**

- ClaudeSDKClient wrapper with domain-specific configuration
- Hook pipeline implementation (PreToolUse, PostToolUse, PreMessage, PostMessage)
- Knowledge persistence layer with dual-store architecture
- Core Spotlight indexing for function signatures
- Subagent registration via AgentDefinition

**Weeks 5–6: Coding Domain**

- Bootstrap coding skill kit deployment
- Per-repo container provisioning and workspace management
- Test execution loop with result parsing and learning capture
- Git workflow integration (branch, commit, PR)
- Six-layer context architecture implementation

**Weeks 7–8: Polish and Hardening**

- Error handling and crash recovery via XPC
- OSLog structured logging and telemetry
- Idle mode processing (skill generation, context refresh, learning re-verification)
- Token budget manager with optimization reporting
- Documentation and internal testing

### Phase 2: Stock Selection Agent (Weeks 9–14)

**Weeks 9–10: Stock Domain Setup**

- StockAgent subagent registered via AgentDefinition
- Financial MCP servers: yfinance, SEC filings, technical analysis
- Bootstrap stock skill kit deployment
- Portfolio data model in domain-specific knowledge.db

**Weeks 11–12: Analysis Capabilities**

- Technical indicator calculation and visualization
- Backtesting framework with historical data
- Risk metrics and position sizing
- Performance reporting and portfolio analytics

**Weeks 13–14: Integration**

- Cross-domain learning transfer (testing patterns to backtesting)
- Multi-agent coordination via SDK subagent system
- Dashboard interface in SwiftUI shell

### Phase 3: Research Agent (Weeks 15–18)

- ResearchAgent subagent with arXiv MCP and citation tools
- Paper analysis skills and knowledge graph building
- Cross-domain coordination (research signals feeding stock agent)

### Phase 4: Self-Extension (Ongoing)

- Domain detection heuristics with user confirmation
- Autonomous MCP server generation with approval gate
- Autonomous skill generation from cross-domain patterns
- Self-registration of new subagents

---

## 14. Technical Stack Summary

| Category | Technology |
|----------|------------|
| **Languages** | Python 3.12+ (core, SDK), Swift 6+ (shell, native APIs) |
| **Agent Framework** | Claude Agent SDK (Python) — orchestration, tools, hooks, subagents, skills |
| **Local Inference** | MLX Swift — Qwen3 4B (4-bit quantized, 80–120 t/s) |
| **Cloud API** | GLM 4.7 via Z.AI — 200K context, interleaved thinking, $0.60/M input |
| **On-Device Classification** | Apple Foundation Models — @Generable structured output, 4K context |
| **Container Runtime** | Apple Containerization framework (primary), Docker Desktop (fallback) |
| **Storage** | SQLite + sqlite-vec (knowledge, learnings, vectors), Core Spotlight (search index) |
| **UI Framework** | SwiftUI (shell), XPC (IPC), ServiceManagement (daemon) |
| **File Monitoring** | FSEvents (kernel-level), DispatchSource (memory pressure) |
| **Security** | Keychain Services (Secure Enclave), per-container network isolation |
| **Logging** | OSLog (structured, zero-cost when unobserved) |
| **Networking** | Network.framework (multiplexed, TLS, native stack) |

### 14.1 Directory Structure

The Jarvis installation root at `~/.jarvis/` contains:

- `config.toml` — Global configuration
- `bootstrap/` — Pre-built skill kits organized by domain
- `mcp_servers/` — Organized by category: macos, coding, stocks, research
- `workspace/` — Organized by domain, containing per-repo workspaces with their own `.jarvis/` subdirectories
- `logs/` — Structured log output

---

## 15. Success Metrics

| Metric | Target | Timeline | Measurement |
|--------|--------|----------|-------------|
| **Token efficiency** | 60–80% reduction for recurring workflows vs raw SDK | Week 4+ | Measured by `token_usage` table |
| **Error re-resolution** | Zero repeat debugging for known patterns | Week 2+ | Learnings table hit rate |
| **Skill generation rate** | 5+ auto-generated skills per month of active use | Week 6+ | `skill_candidates` promotion rate |
| **Cold start time** | < 3 seconds from clone to first usable task | Week 1 | Clone-time initialization benchmark |
| **Container boot** | < 1.5 seconds cold, < 0.8 seconds warm | Week 1 | Apple Containerization perf |
| **MCP health check** | < 2 seconds per server, 100% coverage pre-session | Week 2 | Health check pass rate |
| **Knowledge freshness** | < 5% stale learnings at any time | Week 4+ | Pruning system effectiveness |
| **Day-one value** | Bootstrap skills enable productive use from first session | Day 1 | User task completion rate |

---

## 16. Risks and Mitigations

| Risk | Severity | Description | Mitigation |
|------|----------|-------------|------------|
| **SDK initialization latency** | High | ClaudeSDKClient takes 20–30s to initialize per instance | Single long-lived session with subagents; avoid multi-instance patterns |
| **Skill prompt bloat** | High | Accumulated skills inflate context, cause conflicts | Progressive disclosure (metadata first), hard cap (3 per session), confidence decay |
| **Knowledge rot** | Medium | Learnings become stale after refactors | FSEvents-triggered invalidation, passive decay, idle re-verification |
| **MCP silent failures** | Medium | Unstable APIs return wrong data silently | Pre-session health checks, automatic quarantine, user notification |
| **Apple Containerization maturity** | Medium | v0.6.0 lacks Compose-equivalent orchestration | Docker Desktop as fallback; socktainer project for API compatibility |
| **Foundation Models 4K limit** | Low | Context window too small for complex routing | Use only as narrow classifier; not a required component |
| **24GB RAM constraint** | Low | Multi-container scenarios may exceed budget | Priority-based hibernation, state machine transitions, emergency shutdown |

---

## 17. Appendix: Key Technical Decisions

This section documents the rationale behind six critical architectural decisions, supported by the technical research conducted during architecture synthesis.

### A. Apple Containerization over Docker Desktop

Apple Containerization provides hardware-level isolation (one VM per container), zero idle RAM overhead, dedicated per-container IP addresses, 31× I/O throughput advantage, and free Apache 2.0 licensing. Docker Desktop retains advantages in ecosystem maturity and Compose orchestration. Jarvis uses Apple Containerization as primary runtime with Docker as a fallback for complex multi-container scenarios. The socktainer project provides Docker-compatible REST API compatibility for the transition period.

### B. sqlite-vec over FAISS for Vector Search

At Jarvis's scale (10K–100K vectors), sqlite-vec delivers sub-75ms queries from disk with ACID transactions, automatic persistence, and SQL JOINs across vector and relational data in a single SQLite file. FAISS is faster in raw brute-force (1–5ms) but requires 293MB+ RAM residency, manual save/load, a separate metadata database, and has no Metal GPU acceleration. The unified data model and operational simplicity of sqlite-vec make it the clear choice.

### C. SDK Built-in Subagents over Multi-Instance

The Claude Agent SDK provides first-class subagent support via the Task tool and AgentDefinition API with isolated context windows, restricted tool sets, and parallel execution. Running multiple ClaudeSDKClient instances is technically possible but suffers from 20–30 second initialization per instance and significant memory accumulation. Jarvis uses a single long-lived session with aggressive subagent usage for domain-specific work.

### D. Delegating Skill Selection to Claude

The SDK's skill system delegates all selection to Claude's LLM reasoning rather than algorithmic matching. Skill metadata (approximately 100 tokens per skill) is loaded at startup; full content is injected only on selection. This means skill description quality directly determines selection accuracy. Jarvis invests in precise, distinctive SKILL.md frontmatter descriptions rather than building custom routing logic.

### E. Automatic Context Compaction

The SDK automatically summarizes prior history when context approaches the window limit (64–95% capacity), replacing it with a condensed summary. This is inherently lossy: full tool results, intermediate reasoning, and verbatim file contents may be compressed. Jarvis mitigates this by storing critical decisions in CLAUDE.md files (loaded via setting_sources, surviving compaction) and using subagents aggressively for context isolation during multi-step workflows.

### F. Foundation Models as Optional Fast Path

Apple's Foundation Models framework offers genuine value as a zero-cost, zero-latency classifier for simple task triage. However, its 4,096-token context window, 3B-parameter reasoning ceiling, and Swift-only API make it unsuitable as a primary routing layer. Jarvis architects it as an optional fast path for narrow classification tasks, not a required component. The system functions fully without it.

---

**End of Document**

**Jarvis v2.0 PRD • February 2026 • Gurusharan**
