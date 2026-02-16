# Jarvis Memory & Learning Repository

## Research-Based Improvements (Self-Improvement Cycle 2026-02-12)

### Key Findings from Research

#### 1. Boris Cherny's Claude Code Workflow (Source: Talent500)
- **5 AI agents running simultaneously** with specialized roles (testing, debugging, documentation, refactoring)
- **Human acts as "strategist commanding a fleet"** - oversight, not micromanagement
- **CLAUDE.md file as evolving error repository** - converts mistakes into permanent lessons
- **Verification loops improve output 2-3x** by continuous self-testing
- **Slower models (Opus 4.5) win** - higher quality reduces human correction effort

#### 2. OpenAI's Data Agent - 6 Context Layers (Source: OpenAI Blog)
1. Metadata grounding (schemas, types)
2. Query inference (historical patterns)
3. Curated descriptions (domain expert intent)
4. **Code-level understanding** (pipeline logic, business rules embedded in code) - "secret weapon"
5. Unstructured knowledge (Slack, Docs, Notion - embedded as RAG)
6. Runtime context (live inspection)

**Key insight**: Schemas + query history describe table shape, but true meaning lives in CODE that produces it.

#### 3. OpenAI's Lessons Learned (Source: OpenAI Blog)
- **Overlapping tools confused the agent** - consolidated and restricted certain tool calls
- **Highly prescriptive prompting degraded results** - better to use high-level guidance
- **Code-level understanding was critical** - pipeline logic captures assumptions and business intent
- **Evals run continuously** - like unit tests during development to catch regressions

#### 4. Anthropic's Long-Running Agent Research (Source: Anthropic Engineering)
- **Initializer agent** sets up environment on first run (init.sh, progress file, git commit)
- **Coding agent** makes incremental progress, leaves clean state for next session
- **Feature list in JSON** - tracks what's done vs. pending
- **Self-verification required** - agent tended to mark features complete prematurely
- **Multi-agent architecture question** - specialized agents (testing, QA, cleanup) may outperform generalist

---

## Jarvis-Specific Conventions

### Container Management
- **Always use Apple Containers** for code execution (isolated, safe)
- **Mount project source** with `--volume` flag for persistent changes
- **Clean up containers** after task completion with `container_stop`
- **Pattern**: `container_run` → `container_exec` (install) → work → `container_stop`

### Git Workflow
- **Never force-push** to main/master branch
- **Create new commits** (never amend) to preserve history
- **Use HEREDOC syntax** for commit messages to ensure proper formatting
- **Pre-commit hooks always run** - no `--no-verify` flag
- **Current git identity**: openclaw-gurusharan / gupta.huf.gurusharan@gmail.com

### Tool Usage Patterns
- **Token-efficient MCP tools** for large file processing (98%+ token savings)
- **Context7 MCP** for framework/library documentation
- **DeepWiki MCP** for GitHub repository docs and Q&A
- **Browser automation** via headless Playwright in containers (no Chrome extension needed)

### Security Boundaries
- **T2 Trust Level (DEVELOPER)**: Can write code, run tests, git commits
- **CANNOT without approval**: Production deploys, CI/CD modifications
- **NEVER**: Deploy to production, delete main branch, modify CI/CD without explicit approval

---

## Common Mistakes to Avoid

### From Research + Experience
1. **Trying to do too much in one session** - leads to half-implemented features
2. **Leaving environment in broken state** - always commit working code, not broken
3. **Insufficient self-verification** - must actively test, not assume code works
4. **Overlapping tool redundancy** - confuses agent, consolidate to single paths
5. **Prescriptive over-prompting** - restricts agent's problem-solving flexibility

### Error Recovery
- **Git is safety net** - can revert bad changes if committed properly
- **Containers are disposable** - if state corrupted, stop and recreate
- **Progress files are critical** - document what was done for next session

---

## Architecture Decisions

### Why Apple Containers?
- **Decision**: Use Apple Containers for all execution
- **Category**: architecture
- **Outcome**: success
- **Rationale**: Isolated environment, can install anything safely, full Linux toolchain

### Why Token-Efficient Tools?
- **Decision**: Prioritize MCP tools with on-server processing
- **Category**: performance
- **Outcome**: success
- **Rationale**: 98%+ token savings, faster processing, less context bloat

### Why Headless Browser Automation?
- **Decision**: Playwright in containers, not Chrome extensions
- **Category**: testing
- **Outcome**: success
- **Rationale**: No extension management overhead, works in isolated environment

---

## Verification Loops

### Self-Testing Checklist
After major operations, Jarvis should:
- [ ] Verify git commit succeeded (`git log -1`)
- [ ] Verify container is running/stopped as expected
- [ ] Verify tests pass (run test suite)
- [ ] Verify no breaking changes (check logs, error rates)
- [ ] Document what was done (update progress file)

### Quality Gates
Before declaring task complete:
1. Code must be tested (not just written)
2. Tests must pass (or fix until they do)
3. Git history must be clean (no messy WIP commits)
4. Environment must be in reusable state

---

## Multi-Agent Patterns

### Potential Future Enhancements
Based on Cherny's 5-agent pattern:
1. **Coding Agent** - Primary development work
2. **Testing Agent** - Runs test suites, fixes failures
3. **Documentation Agent** - Updates docs, README files
4. **Code Review Agent** - Independent quality checks (review_diff)
5. **Cleanup Agent** - Removes dead code, refactors

**Current Jarvis**: Single agent with tool access - effective but could specialize.

---

## Sources Referenced

This file aggregates insights from:
- [Boris Cherny Claude Code Workflow](https://talent500.com/blog/claude-code-workflow-redefining-software-development/) (Jan 2026)
- [OpenAI Data Agent Blog](https://openai.com/index/inside-our-in-house-data-agent/) (Jan 2026)
- [Anthropic Engineering - Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) (Nov 2025)
- [Foundation Capital - Context Graphs](https://foundationcapital.com/context-graphs-ais-trillion-dollar-opportunity/) (Dec 2025)
- [Claude Code Best Practices](https://code.claude.com/docs/en/best-practices)
