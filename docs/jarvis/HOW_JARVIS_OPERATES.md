# How Jarvis Operates

A comprehensive guide to understanding when Jarvis does what.

---

## Overview

Jarvis has **two execution modes** that serve different purposes:

1. **Single-Agent Mode** (Default) - Conversational, fast, direct execution
2. **Multi-Agent Pipeline** - Structured, complex tasks with planning/testing/review

Both modes share the same infrastructure (hooks, MCP servers, learning loop) but differ in how they orchestrate work.

---

## Entry Points: Where Tasks Come From

Jarvis accepts tasks from multiple interfaces:

| Interface | Entry Point | Default Mode | Can Override? |
|-----------|-------------|--------------|---------------|
| **CLI** | `jarvis run "task"` | Auto-selects | `-p` (pipeline) or `-s` (single) |
| **WebSocket** | Menu bar app / Full app | Single-agent | `mode="pipeline"` in request |
| **Voice (WebSocket)** | `send_voice` action | Single-agent, direct reply | No (always immediate conversational path) |
| **A2A Protocol** | External agents (OpenClaw) | Single-agent | Via orchestrator config |
| **Slack Bot** | Slack channel | Single-agent | Not configurable |
| **Chat Mode** | WebSocket `chat` action | Single-agent | N/A (conversational) |

### OpenClaw -> Jarvis A2A Bridge

Jarvis exposes A2A on `http://127.0.0.1:9848` and requires Bearer auth from `~/.jarvis/a2a_token`.

Use these CLI wrappers when wiring OpenClaw plugin methods:

```bash
jarvis a2a health -j
jarvis a2a card -j
jarvis a2a send "review this repo" --non-blocking -j
jarvis a2a get <task-id> -j
jarvis a2a wait <task-id> --timeout 300 -j
jarvis a2a cancel <task-id> -j
```

Environment overrides:

```bash
export JARVIS_A2A_URL=http://127.0.0.1:9848
export JARVIS_A2A_TOKEN="$(cat ~/.jarvis/a2a_token)"
```

---

## Decision Flow: Single-Agent vs Pipeline

### Auto-Selection Logic (`should_use_pipeline()`)

When mode is `"auto"` (CLI default), Jarvis decides based on:

**1. Trust Tier Check**
```python
if trust_tier < 2:
    return False  # Pipeline requires T2+ (container access)
```

**2. Complexity Signals**
Pipeline is used if task description contains:
- `"build"`, `"implement"`, `"create"`, `"refactor"`, `"migrate"`
- `"add feature"`, `"full stack"`, `"end to end"`, `"e2e"`
- `"rewrite"`, `"redesign"`, `"architecture"`

**Examples:**
- ✅ `"build a REST API"` → Pipeline (has "build")
- ✅ `"implement user authentication"` → Pipeline (has "implement")
- ❌ `"fix the failing tests"` → Single-agent (no complexity signal)
- ❌ `"explain this code"` → Single-agent (conversational)

### Manual Override

Users can force a mode:
- CLI: `jarvis run -p "simple task"` (force pipeline)
- CLI: `jarvis run -s "complex task"` (force single)
- WebSocket: `{"action": "run_task", "data": {"description": "...", "mode": "pipeline"}}`

---

## Single-Agent Mode: How It Works

### Architecture

```
User Task
    ↓
JarvisOrchestrator.run_task()
    ↓
ClaudeSDKClient (single agent)
    ├─→ System Prompt (project context + trust level)
    ├─→ Allowed Tools (based on trust tier)
    ├─→ MCP Servers (container, git, browser, review)
    └─→ Hooks (PreToolUse, PostToolUse, PostMessage)
         ├─→ Budget enforcement
         ├─→ Trust checks
         ├─→ Execution record saving
         └─→ Loop detection
    ↓
Task Completes
    ├─→ Learning loop extracts patterns
    ├─→ Events emitted
    └─→ Notifications sent
```

### Characteristics

- **Speed**: Fast, direct execution
- **Cost**: Lower (single agent, fewer turns)
- **Use Case**: 
  - Quick fixes
  - Code explanations
  - Simple edits
  - Research queries
  - Conversational tasks
- **Tools Available**: Based on trust tier (T0-T4)
- **Session**: Maintains conversation context

### Voice Path (Current)

Voice in the app uses this path:

1. macOS recorder captures audio.
2. Local Whisper transcription backend transcribes speech.
3. Client sends `send_voice` with `data.text` over WS.
4. Server calls `JarvisOrchestrator.handle_message(...)` directly.
5. Reply is returned in the same WS response and spoken in-app.

### Example Flow

```
User: "Fix the typo in README.md"

1. Orchestrator creates task_id
2. Single ClaudeSDKClient session starts
3. Agent reads README.md
4. Agent edits file (fixes typo)
5. Agent reports completion
6. Learning loop: No errors → No learnings saved
7. Task marked "completed"
```

---

## Multi-Agent Pipeline: How It Works

### Architecture

```
User Task
    ↓
MultiAgentPipeline.run()
    ↓
Main Agent (orchestrator)
    ├─→ Planner Agent (Opus)
    │   ├─→ Analyzes task
    │   ├─→ Reads codebase
    │   └─→ Creates structured plan (JSON)
    │
    ├─→ Executor Agent (Sonnet)
    │   ├─→ Creates Apple Container
    │   ├─→ Implements changes
    │   └─→ Verifies compilation
    │
    ├─→ Tester Agent (Sonnet)
    │   ├─→ Writes tests
    │   ├─→ Runs test suite
    │   └─→ Fixes failing tests (up to 5 retries)
    │
    └─→ Reviewer Agent (Opus)
        ├─→ Reviews all changes
        ├─→ Checks quality/security
        └─→ Approves or requests fixes
    ↓
Pipeline Completes
    ├─→ Learning loop extracts patterns
    ├─→ Git commit (if approved)
    └─→ Container cleanup
```

### Agent Roles

| Agent | Model | Purpose | Tools |
|-------|-------|---------|-------|
| **Planner** | Opus | Architecture & planning | Read, Glob, Grep, WebSearch |
| **Executor** | Sonnet | Implementation | Edit, Write, Bash, Container tools |
| **Tester** | Sonnet | Testing & QA | Edit, Write, Bash, Browser tools |
| **Reviewer** | Opus | Code review | Read, Review tools |

### Characteristics

- **Speed**: Slower (multiple agents, structured flow)
- **Cost**: Higher (multiple agents, more turns)
- **Use Case**:
  - Feature implementation
  - Refactoring
  - Full-stack development
  - Complex migrations
  - End-to-end builds
- **Isolation**: Always uses Apple Containers
- **Quality**: Built-in testing and review gates

### Example Flow

```
User: "Build a REST API with authentication"

1. Pipeline creates task_id
2. Planner Agent:
   - Reads codebase structure
   - Plans: routes, auth middleware, database schema
   - Outputs JSON plan
3. Executor Agent:
   - Creates Node.js container
   - Implements routes (Express.js)
   - Implements auth (JWT)
   - Verifies compilation
4. Tester Agent:
   - Writes unit tests
   - Writes integration tests
   - Runs test suite
   - Fixes 2 failing tests
5. Reviewer Agent:
   - Reviews all changes
   - Checks security (JWT implementation)
   - Approves changes
6. Git commit created
7. Learning loop: Extracts patterns from errors/fixes
8. Container cleaned up
9. Task marked "completed"
```

---

## Trust Tiers: What Controls Access

Jarvis uses a **5-tier trust system** that controls tool access:

| Tier | Name | Tools Available | Pipeline Access |
|------|------|-----------------|-----------------|
| **T0** | Guest | Read, Glob, Grep, WebSearch | ❌ |
| **T1** | Assistant | + Edit, Write, Bash, Task | ❌ |
| **T2** | Developer | + Containers, Git commit | ✅ |
| **T3** | Trusted Dev | + Git push, PR creation | ✅ |
| **T4** | Autonomous | All tools, bypass permissions | ✅ |

**Trust Progression:**
- Starts at T1 (Assistant)
- Upgrades on successful tasks
- Downgrades on failures
- Per-project tracking

**Pipeline Requirement:**
- Pipeline mode requires **T2+** (needs container access)
- Single-agent works at **T1+**

---

## Shared Infrastructure

Both modes share:

### 1. Hooks System
- **PreToolUse**: Budget/trust checks before tool execution
- **PostToolUse**: Execution record saving, loop detection
- **PostMessage**: Cost tracking, token usage

### 2. MCP Servers
- `jarvis-container`: Apple Container lifecycle
- `jarvis-git`: Git operations
- `jarvis-review`: Code review tools
- `jarvis-browser`: Browser automation/testing

### 3. Learning Loop
- Both modes save execution records
- Both modes extract patterns after completion
- Learnings are shared across modes

### 4. Memory & State
- Same `MemoryStore` (SQLite)
- Same task tracking
- Same trust/budget state

---

## When to Use Which Mode

### Use Single-Agent When:
- ✅ Quick fixes or edits
- ✅ Code explanations or research
- ✅ Simple tasks (< 5 minutes expected)
- ✅ Conversational queries
- ✅ Trust tier < T2
- ✅ Cost-sensitive (lower cost)

### Use Pipeline When:
- ✅ Feature implementation
- ✅ Complex refactoring
- ✅ Full-stack development
- ✅ Need testing + review
- ✅ Trust tier T2+
- ✅ Quality > speed

---

## Task Lifecycle (Both Modes)

```
1. Task Created
   ├─→ Task ID generated
   ├─→ Task record in database
   └─→ Status: "pending"

2. Task Started
   ├─→ Status: "in_progress"
   ├─→ Notification sent
   └─→ Event emitted

3. Execution
   ├─→ Tools used (execution records saved)
   ├─→ Budget tracked
   ├─→ Trust updated
   └─→ Hooks enforce policy

4. Task Completes
   ├─→ Status: "completed" | "failed"
   ├─→ Learning loop extracts patterns
   ├─→ Events emitted
   └─→ Notifications sent

5. Post-Task
   ├─→ Cost recorded
   ├─→ Trust tier updated
   └─→ Learnings available for future tasks
```

---

## Real-World Examples

### Example 1: Quick Fix (Single-Agent)

```bash
$ jarvis run "Fix typo in line 42 of src/utils.py"
```

**Flow:**
1. Auto-selects single-agent (no complexity signal)
2. Agent reads file, fixes typo, saves
3. Completes in ~10 seconds
4. Cost: ~$0.01

### Example 2: Feature Build (Pipeline)

```bash
$ jarvis run "Build user authentication with JWT"
```

**Flow:**
1. Auto-selects pipeline ("build" signal)
2. Planner creates plan (routes, middleware, DB schema)
3. Executor implements in container
4. Tester writes + runs tests
5. Reviewer approves
6. Git commit created
7. Completes in ~5-10 minutes
8. Cost: ~$0.50-1.00

### Example 3: Forced Mode

```bash
$ jarvis run -s "Build a complex API"  # Force single-agent
```

**Flow:**
1. User forces single-agent despite "build" signal
2. Single agent attempts entire task
3. May take longer, but lower cost
4. No structured testing/review

---

## Configuration

### Enable/Disable Learning

```python
# config.json
{
  "knowledge": {
    "enable_learning": true  # Default: true
  }
}
```

### Force Pipeline Mode

```python
# CLI
jarvis run -p "task"

# WebSocket
{"action": "run_task", "data": {"description": "task", "mode": "pipeline"}}
```

### Trust Tier Override

```python
# config.json
{
  "trust_tier": 2  # Start at T2 instead of T1
}
```

---

## Summary

**Jarvis operates in two modes:**

1. **Single-Agent**: Fast, conversational, direct execution
   - Default for most tasks
   - Works at T1+
   - Lower cost

2. **Multi-Agent Pipeline**: Structured, quality-focused, complex tasks
   - Auto-selected for complex tasks
   - Requires T2+
   - Higher cost, better quality

**Both modes:**
- Share hooks, MCP servers, learning loop
- Save execution records
- Extract patterns for continuous improvement
- Respect trust tiers and budget limits

**The key difference:** Pipeline adds structured planning, testing, and review phases for complex work, while single-agent is optimized for speed and simplicity.
