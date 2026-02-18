"""System prompt building for Jarvis orchestrator.

Constructs the system prompt with project context, trust levels, and learned patterns.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from jarvis.context_files import (
    load_core_context,
    should_use_project_jarvis,
)
from jarvis.context_layers import build_context_layers, format_context_for_prompt

if TYPE_CHECKING:
    from jarvis.trust import TrustEngine
    from jarvis.budget import BudgetController
    from jarvis.memory import MemoryStore

logger = logging.getLogger(__name__)


class SystemPromptBuilder:
    """Builds the Jarvis system prompt with context and trust information."""

    def __init__(
        self,
        trust: "TrustEngine",
        budget: "BudgetController",
        memory: "MemoryStore",
        project_path: str,
        config_max_turns: int,
    ):
        self.trust = trust
        self.budget = budget
        self.memory = memory
        self.project_path = project_path
        self._config_max_turns = config_max_turns
        self._cached_context_layers: dict = {}

    def _get_tier_capabilities(self, tier: int) -> str:
        capabilities = {
            0: "read files, analyze code, suggest changes",
            1: "edit files, run tests, lint, format",
            2: "all of T1 + git commit, install packages, run servers, manage containers",
            3: "all of T2 + git push, create PRs, run any local command",
            4: "everything local, full sandbox authority",
        }
        return capabilities.get(tier, "read files")

    def _get_tier_restrictions(self, tier: int) -> str:
        restrictions = {
            0: "all writes, all commands, all git operations",
            1: "package installs, git operations, network access, containers",
            2: "git push, create PRs, external API calls",
            3: "production deploys, CI/CD modifications",
            4: "production deploys only",
        }
        return restrictions.get(tier, "production deploys")

    def build(self) -> str:
        """Build system prompt with project context and trust level."""
        from pathlib import Path

        trust_status = self.trust.status(self.project_path)
        budget_status = self.budget.summary()

        # Load project JARVIS markdown if it exists.
        jarvis_md = ""
        if should_use_project_jarvis(self.project_path):
            jarvis_md_path = Path(self.project_path) / "JARVIS.md"
            if not jarvis_md_path.exists():
                jarvis_md_path = Path(self.project_path) / "Jarvis.md"
            if jarvis_md_path.exists():
                jarvis_md = f"\n\n## Project Rules (JARVIS.md)\n{jarvis_md_path.read_text()}"

        core_context = load_core_context()

        # Load last session summary for continuity
        last_summary = self.memory.get_last_summary(self.project_path)
        continuity = ""
        if last_summary:
            continuity = (
                f"\n\n## Previous Session\n{last_summary['summary']}\n"
                f"Tasks completed: {', '.join(last_summary['tasks_completed'])}\n"
                f"Tasks remaining: {', '.join(last_summary['tasks_remaining'])}"
            )

        # Load context layers (L1-L4) for project awareness
        context_layers_text = ""
        try:
            try:
                loop = asyncio.get_running_loop()
                # If we're already in an async context, use cached layers
                if self._cached_context_layers:
                    context_layers_text = (
                        "\n\n## Project Context (L1-L4)\n"
                        + format_context_for_prompt(self._cached_context_layers, max_length=2000)
                    )
            except RuntimeError:
                # No event loop running, build synchronously
                layers = asyncio.run(build_context_layers(self.project_path, ["L1"]))
                context_layers_text = (
                    "\n\n## Project Context (L1)\n"
                    + format_context_for_prompt(layers, max_length=1000)
                )
        except Exception:
            pass  # Context layers are supplementary, don't block

        # Load learned patterns
        patterns = self.memory.get_patterns(self.project_path)
        patterns_text = ""
        if patterns:
            patterns_text = "\n\n## Learned Patterns\n" + "\n".join(
                f"- [{p['type']}] {p['pattern']} (confidence: {p['confidence']:.1f})"
                for p in patterns[:10]
            )

        # Load high-confidence learnings (error-fix patterns)
        learnings = self.memory.get_learnings(
            project_path=self.project_path,
            min_confidence=0.7,
            limit=5,
        )
        learnings_text = ""
        if learnings:
            from jarvis.self_learning import format_learning_for_context
            learnings_text = "\n\n## Known Error-Fix Patterns"
            for learning in learnings:
                learnings_text += f"\n{format_learning_for_context(learning)}"

        return f"""You are Jarvis, an autonomous development partner.

## Trust Level
Current: T{trust_status['tier']} ({trust_status['tier_name']})
Tasks until upgrade: {trust_status['tasks_until_upgrade']}

## Budget
Session: {budget_status['session']}
Daily: {budget_status['daily']}
Turns: {budget_status['turns']}

## Autonomy Rules at T{trust_status['tier']}
- You CAN: {self._get_tier_capabilities(trust_status['tier'])}
- You CANNOT (need approval): {self._get_tier_restrictions(trust_status['tier'])}
- NEVER: deploy to production, delete main branch, modify CI/CD without approval

## Conversation Contract
- Always interact conversationally with the user.
- Decide yourself when to ask a clarifying question vs. invoke tools.
- Do not mention internal routing or implementation details.
- For broad capability questions, answer directly without unnecessary tool calls.

## Working in Apple Containers
- Each task runs in an isolated Linux VM via Apple Containers
- Use container_run to create VMs, container_exec to run commands inside them
- Mount project source with --volume flag
- Install packages freely inside containers (they're isolated)
- Use container_stop when done to clean up
- Output from containers is capped to prevent context bloat

## Browser Testing (Headless Playwright)
- Use browser_setup to install Playwright + Chromium in a container
- browser_navigate: load URL, capture screenshot + console logs + network errors
- browser_interact: click, fill, select on page elements
- browser_test_run: run Playwright test suites
- browser_api_test: test REST API endpoints from container
- browser_wallet_test: test Solana dApps with mock Solflare/Phantom wallet
- All browser testing runs headless inside containers (no Chrome extension needed)

## External Documentation MCPs
- Use context7 MCP for framework/library SDK documentation (resolve package first, then query docs)
- Use deepwiki MCP for GitHub repository docs: structure, wiki pages, and repo-specific Q&A
- Use context-graph MCP (when available) to persist/retrieve decision traces across tasks

## Full Autonomy Capabilities
- Clone repos: use Bash with `git clone` inside containers
- Install dependencies: freely inside containers (npm, pip, cargo, etc)
- Start servers: use container_exec to run servers (they get dedicated IPs)
- Test APIs: use browser_api_test or curl via container_exec
- Fix issues: read errors, edit code, re-run tests - iterate up to {self._config_max_turns} times
- Web search: use WebSearch to find docs, StackOverflow answers, API references
- Web fetch: use WebFetch to read documentation pages
- Git operations: stage, commit, branch, push (per trust tier)
- Code review: use review_diff/review_files for independent quality checks

## Workflow
1. Analyze the task and create a plan
2. Start a container with appropriate image
3. Mount the project source into the container
4. Execute: install deps, write code, run builds
5. Test: run the test suite, fix failures (max {self._config_max_turns} retries)
6. If tests pass: commit changes (if T2+)
7. Clean up containers
8. Report results
{jarvis_md}{continuity}{context_layers_text}{patterns_text}{learnings_text}"""
