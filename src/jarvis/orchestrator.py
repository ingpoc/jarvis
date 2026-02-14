"""Core orchestrator: wires Claude Agent SDK with Apple Containers.

Supports two modes:
- Single-agent (Phase 1): Direct task execution with one agent
- Multi-agent (Phase 2): Planner -> Executor(s) -> Tester -> Reviewer pipeline

Uses the Python Agent SDK with:
- Custom MCP tools for Apple Container lifecycle, Git, and Review
- Hooks for budget enforcement and trust checks
- Session resume for continuity
- macOS native notifications
"""

import asyncio
import json
import logging
import os
import re
import shutil
import time
import traceback
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
)

from jarvis.budget import BudgetController
from jarvis.code_orchestrator import CodeOrchestrator
from jarvis.config import JARVIS_HOME, JarvisConfig
from jarvis.decision_tracer import DecisionTracer, TraceCategory
from jarvis.browser_tools import create_browser_mcp_server
from jarvis.context_files import (
    append_project_turn,
    ensure_core_context_files,
    ensure_project_jarvis_file,
    load_core_context,
    should_use_project_jarvis,
)
from jarvis.container_tools import create_container_mcp_server
from jarvis.events import EventCollector, EVENT_TOOL_USE, EVENT_TASK_START, EVENT_TASK_COMPLETE, EVENT_ERROR
from jarvis.git_tools import create_git_mcp_server
from jarvis.harness import BuildHarness
from typing import Literal, TypedDict, cast
from jarvis.memory import MemoryStore
from jarvis.loop_detector import LoopDetector, LoopAction, build_intervention_message
from jarvis.notifications import (
    notify_approval_needed,
    notify_task_completed,
    notify_task_failed,
    notify_task_started,
)
from jarvis.review_tools import create_review_mcp_server
from jarvis.trust import TrustEngine
from jarvis.agents import MultiAgentPipeline

logger = logging.getLogger(__name__)
_DYNAMIC_CAPS_FILE = JARVIS_HOME / "dynamic_capabilities.json"
REPO_ROOT = Path(__file__).resolve().parents[2]

class MessageRouteDecision(TypedDict, total=False):
    mode: Literal["reply", "ask", "execute"]
    reply: str
    question: str
    choices: list[str]
    task_description: str
    confidence: float
    reason: str


class JarvisOrchestrator:
    """Main Jarvis orchestration engine."""

    def __init__(self, project_path: str | None = None):
        self.config = JarvisConfig.load()
        default_workspace = (
            os.environ.get("JARVIS_WORKSPACE")
            or self.config.workspace_root
            or os.getcwd()
        )
        self.project_path = str(Path(project_path or default_workspace).expanduser().resolve())
        Path(self.project_path).mkdir(parents=True, exist_ok=True)
        ensure_core_context_files()
        ensure_project_jarvis_file(self.project_path)
        self.trust = TrustEngine()
        self.budget = BudgetController()
        self.memory = MemoryStore()
        self.tracer = DecisionTracer(memory=self.memory)
        self.container_server = create_container_mcp_server()
        self.git_server = create_git_mcp_server()
        self.review_server = create_review_mcp_server()
        self.browser_server = create_browser_mcp_server()
        self._configured_mcp_servers = self._load_configured_mcp_servers()
        self._dynamic_mcp_servers: dict[str, dict] = {}
        self._dynamic_agents: dict[str, AgentDefinition] = {}
        self._dynamic_skills: dict[str, dict] = {}
        self._load_dynamic_capabilities()
        self._session_id: str | None = None
        self._active_containers: list[str] = []
        self.loop_detector = LoopDetector(
            max_iterations=self.config.budget.max_turns_per_subtask
        )
        self.events = EventCollector(memory=self.memory)
        self._chat_lock = asyncio.Lock()
        self._chat_client: ClaudeSDKClient | None = None
        self._router_lock = asyncio.Lock()
        self.code_orchestrator = CodeOrchestrator(
            mcp_servers={
                "jarvis-container": self.container_server,
                "jarvis-git": self.git_server,
            },
            project_path=self.project_path,
        )
        self._preflight_status: dict = {
            "ready": False,
            "checked_at": None,
            "live_check": False,
            "errors": ["preflight_not_run"],
            "warnings": [],
            "provider": {
                "base_url": os.environ.get("ANTHROPIC_BASE_URL", ""),
                "token_present": bool(
                    os.environ.get("ANTHROPIC_AUTH_TOKEN")
                    or os.environ.get("ANTHROPIC_API_KEY")
                ),
            },
            "models": {
                "planner": self.config.models.planner,
                "executor": self.config.models.executor,
                "reviewer": self.config.models.reviewer,
                "quick": self.config.models.quick,
            },
        }

    def _build_mcp_servers(self) -> dict:
        """Build static + dynamic MCP server map."""
        servers: dict[str, dict] = {
            "jarvis-container": self.container_server,
            "jarvis-git": self.git_server,
            "jarvis-review": self.review_server,
            "jarvis-browser": self.browser_server,
        }
        servers.update(self._configured_mcp_servers)
        servers.update(self._dynamic_mcp_servers)
        return servers

    def _extract_urls_from_text(self, text: str) -> list[str]:
        """Extract and normalize HTTP(S) URLs from free-form text."""
        if not text:
            return []
        matches = re.findall(r"https?://[^\s<>()\"']+", text, flags=re.IGNORECASE)
        urls: list[str] = []
        seen: set[str] = set()
        for raw in matches:
            cleaned = raw.rstrip(".,;:!?)]}")
            try:
                parts = urlsplit(cleaned)
            except Exception:
                continue
            if parts.scheme not in ("http", "https") or not parts.netloc:
                continue
            normalized = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
            if normalized not in seen:
                seen.add(normalized)
                urls.append(normalized)
        return urls

    def _ingest_research_urls_from_text(self, text: str, source: str) -> int:
        urls = self._extract_urls_from_text(text)
        if not urls:
            return 0
        added = self.memory.add_research_sources(urls, source=source)
        if added:
            self.events.emit(
                "research_sources_added",
                f"Added {added} research source(s) from {source}",
                metadata={"source": source, "count": added, "urls": urls[:20]},
            )
        return added

    def _load_dynamic_capabilities(self) -> None:
        """Load dynamic MCP servers/agents/skills persisted across restarts."""
        if not _DYNAMIC_CAPS_FILE.exists():
            return
        try:
            data = json.loads(_DYNAMIC_CAPS_FILE.read_text())
        except Exception as exc:
            logger.warning("Failed to load dynamic capabilities: %s", exc)
            return

        for name, server in (data.get("mcp_servers", {}) or {}).items():
            if isinstance(server, dict):
                self._dynamic_mcp_servers[str(name)] = server

        for name, skill in (data.get("skills", {}) or {}).items():
            if not isinstance(skill, dict):
                continue
            desc = str(skill.get("description", "")).strip()
            content = str(skill.get("content", "")).strip()
            if desc and content:
                self._dynamic_skills[str(name)] = {"description": desc, "content": content}

        for name, raw_agent in (data.get("agents", {}) or {}).items():
            if not isinstance(raw_agent, dict):
                continue
            description = str(raw_agent.get("description", "")).strip()
            prompt = str(raw_agent.get("prompt", "")).strip()
            if not description or not prompt:
                continue
            tools = raw_agent.get("tools")
            model = raw_agent.get("model")
            safe_model = model if model in ("sonnet", "opus", "haiku", "inherit", None) else "inherit"
            self._dynamic_agents[str(name)] = AgentDefinition(
                description=description,
                prompt=prompt,
                tools=tools if isinstance(tools, list) else None,
                model=safe_model,
            )

    def _persist_dynamic_capabilities(self) -> None:
        """Persist dynamic capabilities so they survive daemon restart."""
        try:
            JARVIS_HOME.mkdir(parents=True, exist_ok=True)
            agents_payload: dict[str, dict] = {}
            for name, agent in self._dynamic_agents.items():
                agents_payload[name] = {
                    "description": agent.description,
                    "prompt": agent.prompt,
                    "tools": list(agent.tools) if agent.tools else [],
                    "model": agent.model,
                }
            payload = {
                "mcp_servers": self._dynamic_mcp_servers,
                "agents": agents_payload,
                "skills": self._dynamic_skills,
            }
            _DYNAMIC_CAPS_FILE.write_text(json.dumps(payload, indent=2))
        except Exception as exc:
            logger.warning("Failed to persist dynamic capabilities: %s", exc)

    def _load_configured_mcp_servers(self) -> dict[str, dict]:
        """Load MCP servers from project config and built-in documentation defaults."""
        configured: dict[str, dict] = {}

        # Load .mcp.json from workspace first, then fallback to Jarvis core repo.
        mcp_candidates = [
            Path(self.project_path) / ".mcp.json",
            REPO_ROOT / ".mcp.json",
        ]
        for mcp_json_path in mcp_candidates:
            if not mcp_json_path.exists():
                continue
            try:
                data = json.loads(mcp_json_path.read_text())
                server_map = data.get("mcpServers", {})
                if isinstance(server_map, dict):
                    for name, raw in server_map.items():
                        parsed = self._parse_project_mcp_server(name, raw)
                        if parsed and name not in configured:
                            configured[name] = parsed
            except Exception as exc:
                logger.warning("Failed to parse .mcp.json (%s): %s", mcp_json_path, exc)

        # Ensure doc/repo lookup MCPs are available by default.
        if "context7" not in configured and shutil.which("npx"):
            context7_args = ["-y", "@upstash/context7-mcp"]
            api_key = os.environ.get("CONTEXT7_API_KEY") or os.environ.get("CTX7_API_KEY")
            if api_key:
                context7_args.extend(["--api-key", api_key])
            configured["context7"] = {
                "type": "stdio",
                "command": "npx",
                "args": context7_args,
            }
        if "deepwiki" not in configured:
            configured["deepwiki"] = {
                "type": "http",
                "url": "https://mcp.deepwiki.com/mcp",
            }

        return configured

    def _parse_project_mcp_server(self, name: str, raw: object) -> dict | None:
        """Parse one .mcp.json server entry into Claude Agent SDK format."""
        if not isinstance(raw, dict):
            return None
        if "url" in raw and raw.get("url"):
            return {
                "type": "http",
                "url": str(raw["url"]),
                "headers": raw.get("headers", {}) or {},
            }

        command = str(raw.get("command", "")).strip()
        args = [str(a) for a in (raw.get("args", []) or [])]
        env = {str(k): str(v) for k, v in (raw.get("env", {}) or {}).items()}
        if not command:
            return None

        if name == "context-graph":
            command, args, env = self._resolve_context_graph(command, args, env)
        elif name == "token-efficient":
            command, args = self._resolve_token_efficient(command, args)

        return {
            "type": "stdio",
            "command": command,
            "args": args,
            "env": env,
        }

    def _resolve_context_graph(
        self,
        command: str,
        args: list[str],
        env: dict[str, str],
    ) -> tuple[str, list[str], dict[str, str]]:
        """Normalize context-graph config to a valid path + cache dir."""
        candidate_dirs = [
            Path(self.project_path) / "mcp" / "context-graph-mcp",
            REPO_ROOT / "mcp" / "context-graph-mcp",
            Path(self.project_path).parents[1] / "mcp-servers" / "context-graph-mcp",
            Path(self.project_path).parents[2] / "mcp-servers" / "context-graph-mcp",
        ]
        selected = next((p for p in candidate_dirs if (p / "server.py").exists()), None)
        if selected:
            command = "uv"
            args = ["--directory", str(selected), "run", "python", "server.py"]
            env.setdefault("UV_CACHE_DIR", "/tmp/uv-cache-codex")
        return command, args, env

    def _resolve_token_efficient(self, command: str, args: list[str]) -> tuple[str, list[str]]:
        """Normalize token-efficient config to direct stdio node launch."""
        candidate_files = [
            Path(self.project_path) / "mcp" / "token-efficient-mcp" / "dist" / "index.js",
            REPO_ROOT / "mcp" / "token-efficient-mcp" / "dist" / "index.js",
            Path(self.project_path).parents[1] / "mcp-servers" / "token-efficient-mcp" / "dist" / "index.js",
            Path(self.project_path).parents[2] / "mcp-servers" / "token-efficient-mcp" / "dist" / "index.js",
        ]
        selected = next((p for p in candidate_files if p.exists()), None)
        if selected:
            return "node", [str(selected)]

        # If .mcp.json used srt wrapper, fall back to plain node invocation.
        if command == "srt" and args and args[0] == "node":
            return "node", args[1:]
        return command, args

    def _build_system_prompt(self) -> str:
        """Build system prompt with project context and trust level."""
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

        # Load learned patterns
        patterns = self.memory.get_patterns(self.project_path)
        patterns_text = ""
        if patterns:
            patterns_text = "\n\n## Learned Patterns\n" + "\n".join(
                f"- [{p['type']}] {p['pattern']} (confidence: {p['confidence']:.1f})"
                for p in patterns[:10]
            )

        # Decision traces section
        traces_text = ""
        # (traces injected at run_task time via context)

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
- Fix issues: read errors, edit code, re-run tests - iterate up to {self.config.budget.max_turns_per_subtask} times
- Web search: use WebSearch to find docs, StackOverflow answers, API references
- Web fetch: use WebFetch to read documentation pages
- Git operations: stage, commit, branch, push (per trust tier)
- Code review: use review_diff/review_files for independent quality checks

## Workflow
1. Analyze the task and create a plan
2. Start a container with appropriate image
3. Mount the project source into the container
4. Execute: install deps, write code, run builds
5. Test: run the test suite, fix failures (max {self.config.budget.max_turns_per_subtask} retries)
6. If tests pass: commit changes (if T2+)
7. Clean up containers
8. Report results
{self._build_dynamic_capabilities_prompt()}\n\n## Core Context\n{core_context}{jarvis_md}{continuity}{patterns_text}"""

    def _build_dynamic_capabilities_prompt(self) -> str:
        sections: list[str] = []
        if self._dynamic_agents:
            agent_lines = [
                f"- {name}: {agent.description}"
                for name, agent in sorted(self._dynamic_agents.items())
            ]
            sections.append("## Dynamic Agents\n" + "\n".join(agent_lines))
        if self._dynamic_skills:
            skill_lines = [
                f"- {name}: {entry.get('description', '')}"
                for name, entry in sorted(self._dynamic_skills.items())
            ]
            sections.append("## Dynamic Skills\n" + "\n".join(skill_lines))
            skill_details = [
                f"[{name}]\n{entry.get('content', '')}"
                for name, entry in sorted(self._dynamic_skills.items())
            ]
            sections.append("## Skill Definitions\n" + "\n\n".join(skill_details))
        if not sections:
            return ""
        return "\n\n" + "\n\n".join(sections)

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

    def _build_allowed_tools(self) -> list[str]:
        """Build tool list based on trust tier."""
        trust_status = self.trust.status(self.project_path)
        tier = trust_status["tier"]

        # Base tools everyone gets (T0+)
        tools = [
            "Read",
            "Glob",
            "Grep",
            "WebSearch",
            "WebFetch",
            "mcp__context7__resolve-library-id",
            "mcp__context7__query-docs",
            "mcp__deepwiki__read_wiki_structure",
            "mcp__deepwiki__read_wiki_contents",
            "mcp__deepwiki__ask_question",
            "mcp__context-graph__context_get_trace",
            "mcp__context-graph__context_list_categories",
            "mcp__context-graph__context_list_traces",
            "mcp__context-graph__context_query_traces",
            "mcp__context-graph__context_store_trace",
            "mcp__context-graph__context_update_outcome",
            "mcp__token-efficient__batch_process_csv",
            "mcp__token-efficient__execute_code",
            "mcp__token-efficient__get_token_savings_report",
            "mcp__token-efficient__list_token_efficient_tools",
            "mcp__token-efficient__process_csv",
            "mcp__token-efficient__process_logs",
            "mcp__token-efficient__search_tools",
            "mcp__comet-bridge__comet_ask",
            "mcp__comet-bridge__comet_connect",
            "mcp__comet-bridge__comet_mode",
            "mcp__comet-bridge__comet_poll",
            "mcp__comet-bridge__comet_screenshot",
            "mcp__comet-bridge__comet_stop",
            "mcp__jarvis-x-bookmarks__x_health",
            "mcp__jarvis-x-bookmarks__x_get_me",
            "mcp__jarvis-x-bookmarks__x_list_bookmarks",
            "mcp__jarvis-x-bookmarks__x_list_bookmark_folders",
            "mcp__jarvis-x-bookmarks__x_list_folder_bookmarks",
        ]

        if tier >= 1:  # Assistant: edit, test, search
            tools.extend(["Edit", "Write", "Bash", "Task", "Skill", "NotebookEdit"])
            tools.extend([
                "mcp__jarvis-git__git_clone",
                "mcp__jarvis-git__git_status",
                "mcp__jarvis-git__git_diff",
                "mcp__jarvis-git__git_log",
                "mcp__jarvis-git__git_branch",
            ])

        if tier >= 2:  # Developer: containers, packages, git commit
            tools.extend([
                "mcp__jarvis-container__container_run",
                "mcp__jarvis-container__container_exec",
                "mcp__jarvis-container__container_stop",
                "mcp__jarvis-container__container_list",
                "mcp__jarvis-container__container_logs",
                "mcp__jarvis-container__container_inspect",
                "mcp__jarvis-container__container_stats",
                "mcp__jarvis-git__git_add",
                "mcp__jarvis-git__git_commit",
                "mcp__jarvis-git__git_create_branch",
                "mcp__jarvis-git__git_stash",
                "mcp__jarvis-review__review_diff",
                "mcp__jarvis-review__review_files",
                "mcp__jarvis-browser__browser_setup",
                "mcp__jarvis-browser__browser_test_run",
                "mcp__jarvis-browser__browser_navigate",
                "mcp__jarvis-browser__browser_interact",
                "mcp__jarvis-browser__browser_api_test",
                "mcp__jarvis-browser__browser_wallet_test",
            ])

        if tier >= 3:  # Trusted Dev: push, PRs
            tools.extend([
                "mcp__jarvis-git__git_push",
                "mcp__jarvis-git__git_create_pr",
                "mcp__jarvis-review__review_pr",
            ])

        return tools

    async def _pre_tool_hook(self, input_data: dict, tool_use_id: str | None, context: dict) -> dict:
        """Hook: enforce trust and budget before tool execution."""
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Budget check
        can_continue, reason = self.budget.enforce()
        if not can_continue:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Budget limit: {reason}",
                }
            }

        # Trust check for container operations
        if "container" in tool_name.lower():
            action = tool_name.split("__")[-1] if "__" in tool_name else tool_name
            allowed, reason = self.trust.can_perform(self.project_path, action)
            if not allowed:
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    }
                }

        # Trust check for git push
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if "git push" in command:
                allowed, reason = self.trust.can_perform(self.project_path, "git_push")
                if not allowed:
                    return {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": reason,
                        }
                    }

        return {}

    async def _post_tool_hook(self, input_data: dict, tool_use_id: str | None, context: dict) -> dict:
        """Hook: track container lifecycle, emit events, detect loops."""
        tool_name = input_data.get("tool_name", "")
        tool_response = input_data.get("tool_response", "")

        # Emit tool use event
        self.events.emit(
            EVENT_TOOL_USE,
            f"{tool_name}",
            task_id=context.get("task_id"),
            metadata={"tool": tool_name},
        )

        # Track active containers
        if "container_run" in tool_name and isinstance(tool_response, str):
            try:
                data = json.loads(tool_response)
                if data.get("status") == "running":
                    container_id = data.get("container_id")
                    if container_id:
                        self._active_containers.append(container_id)
            except (json.JSONDecodeError, TypeError):
                pass

        # Loop detection
        tool_input_str = json.dumps(input_data.get("tool_input", {}))
        tool_output_str = str(tool_response)[:5120]
        error = None
        if isinstance(tool_response, str) and "error" in tool_response.lower():
            error = tool_response[:1024]

        # Use task ID from context or default
        subtask_id = context.get("task_id", "default")
        action = self.loop_detector.record_iteration(
            subtask_id, tool_name, tool_input_str, tool_output_str, error
        )

        if action != LoopAction.CONTINUE:
            tracker = self.loop_detector.get_tracker(subtask_id)
            message = build_intervention_message(action, tracker)

            if action == LoopAction.ESCALATE:
                asyncio.create_task(notify_approval_needed(subtask_id, "loop_escalation"))

            return {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "message": message,
                }
            }

        return {}

    def _build_options(self) -> ClaudeAgentOptions:
        """Build Agent SDK options with all Jarvis integrations."""
        options = ClaudeAgentOptions(
            system_prompt=self._build_system_prompt(),
            allowed_tools=self._build_allowed_tools(),
            permission_mode="acceptEdits",
            max_turns=self.config.budget.max_turns_per_task,
            max_budget_usd=self.config.budget.max_per_session_usd,
            model=self.config.models.executor,
            cwd=self.project_path,
            mcp_servers=self._build_mcp_servers(),
            hooks={
                "PreToolUse": [
                    HookMatcher(hooks=[self._pre_tool_hook]),
                ],
                "PostToolUse": [
                    HookMatcher(hooks=[self._post_tool_hook]),
                ],
            },
            agents=self._dynamic_agents or None,
        )

        # Resume previous session if available
        if self._session_id:
            options.resume = self._session_id

        return options

    def register_mcp_server(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> dict:
        """Register a dynamic stdio MCP server for future task/chat turns."""
        if not name.strip():
            return {"success": False, "error": "MCP server name is required"}
        if not command.strip():
            return {"success": False, "error": "MCP server command is required"}
        if name.startswith("jarvis-"):
            return {"success": False, "error": "Reserved MCP server prefix: jarvis-"}

        self._dynamic_mcp_servers[name] = {
            "type": "stdio",
            "command": command,
            "args": args or [],
            "env": env or {},
        }
        self._persist_dynamic_capabilities()
        return {
            "success": True,
            "name": name,
            "server_count": len(self._dynamic_mcp_servers),
        }

    def register_agent(
        self,
        name: str,
        description: str,
        prompt: str,
        tools: list[str] | None = None,
        model: str | None = None,
    ) -> dict:
        """Register a dynamic SDK sub-agent."""
        if not name.strip():
            return {"success": False, "error": "Agent name is required"}
        if not description.strip() or not prompt.strip():
            return {"success": False, "error": "Agent description and prompt are required"}
        safe_model = model if model in ("sonnet", "opus", "haiku", "inherit", None) else "inherit"
        self._dynamic_agents[name] = AgentDefinition(
            description=description,
            prompt=prompt,
            tools=tools or None,
            model=safe_model,
        )
        self._persist_dynamic_capabilities()
        return {"success": True, "name": name, "agent_count": len(self._dynamic_agents)}

    def register_skill(self, name: str, description: str, content: str) -> dict:
        """Register a dynamic skill instruction block visible to Jarvis."""
        if not name.strip():
            return {"success": False, "error": "Skill name is required"}
        if not description.strip() or not content.strip():
            return {"success": False, "error": "Skill description and content are required"}
        self._dynamic_skills[name] = {
            "description": description.strip(),
            "content": content.strip(),
        }
        self._persist_dynamic_capabilities()
        return {"success": True, "name": name, "skill_count": len(self._dynamic_skills)}

    def get_capabilities(self) -> dict:
        """Return capability inventory for UI/diagnostics."""
        dynamic_names = sorted(self._dynamic_mcp_servers.keys())
        static_names = [
            "jarvis-container",
            "jarvis-git",
            "jarvis-review",
            "jarvis-browser",
            *sorted(self._configured_mcp_servers.keys()),
        ]
        dynamic_agents = sorted(self._dynamic_agents.keys())
        dynamic_skills = sorted(self._dynamic_skills.keys())
        tools = sorted(set(self._build_options().allowed_tools or self._build_allowed_tools()))
        capability_tools = tools + [f"mcp://{n}" for n in (static_names + dynamic_names)]
        capability_tools += ["hook://PreToolUse", "hook://PostToolUse"]
        capability_tools += ["agent://planner", "agent://executor", "agent://tester", "agent://reviewer"]
        capability_tools += [f"agent://{name}" for name in dynamic_agents]
        capability_tools += ["skill://Skill"]
        capability_tools += [f"skill://{name}" for name in dynamic_skills]
        capability_tools += ["code_orchestrator://execute"]
        return {
            "tools": sorted(set(capability_tools)),
            "mcp_servers": {
                "static": static_names,
                "dynamic": dynamic_names,
            },
            "hooks": ["PreToolUse", "PostToolUse"],
            "agents": ["planner", "executor", "tester", "reviewer", *dynamic_agents],
            "skills_enabled": True,
            "skills": dynamic_skills,
        }

    def run_code_orchestration(self, code: str, timeout: int = 30) -> dict:
        """Execute batched tool script via CodeOrchestrator."""
        result = self.code_orchestrator.execute(code, timeout=timeout)
        summary = (
            f"status={result.get('status')} "
            f"tool_calls={result.get('tool_calls', 0)} "
            f"saved~{result.get('cost_saved_estimate', 0)} tokens"
        )
        self.events.emit(
            EVENT_TOOL_USE,
            "code_orchestrator.execute",
            metadata={
                "summary": summary,
                "status": result.get("status"),
                "tool_calls": result.get("tool_calls", 0),
                "error": result.get("error"),
            },
        )
        return result

    async def run_task(
        self,
        task_description: str,
        callback=None,
        *,
        origin: str = "user",
        emit_notifications: bool = True,
    ) -> dict:
        """Execute a task autonomously.

        Args:
            task_description: Natural language task description
            callback: Optional callback(event_type, data) for progress reporting

        Returns:
            Task result dict with status, cost, session_id
        """
        if origin != "idle_research":
            self._ingest_research_urls_from_text(task_description, source=f"task:{origin}")

        # Create task record
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        self.memory.create_task(task_id, task_description, self.project_path)
        self.memory.transition_task(task_id, "in_progress")

        ensure_project_jarvis_file(self.project_path)
        if emit_notifications:
            await notify_task_started(task_id, task_description)
        self.events.emit(
            EVENT_TASK_START,
            task_description,
            task_id=task_id,
            metadata={"origin": origin, "slack_notify": emit_notifications},
        )
        if callback:
            callback("task_started", {"id": task_id, "description": task_description})

        # Query decision traces for precedents
        try:
            precedents = await self.tracer.query_precedents(
                task_description,
                category=TraceCategory.TASK_EXECUTION,
                limit=3,
            )
            recommendation = DecisionTracer.get_recommendation(precedents)
            if recommendation["action"] != "new_decision" and recommendation["trace"]:
                trace = recommendation["trace"]
                task_description = (
                    f"{task_description}\n\n"
                    f"[Decision Trace] Previous similar task ({recommendation['action']}): "
                    f"{trace.description} → {trace.decision} (outcome: {trace.outcome})"
                )
        except Exception:
            pass  # Don't block task on trace failure

        options = self._build_options()
        result = {
            "task_id": task_id,
            "status": "unknown",
            "cost_usd": 0.0,
            "turns": 0,
            "session_id": None,
            "output": "",
        }

        try:
            async def _run_query() -> None:
                async with ClaudeSDKClient(options=options) as client:
                    await client.query(task_description)

                    async for message in client.receive_response():
                        # Extract session ID
                        if isinstance(message, SystemMessage):
                            if message.subtype == "init":
                                self._session_id = message.data.get("session_id")
                                result["session_id"] = self._session_id

                        # Track assistant output
                        elif isinstance(message, AssistantMessage):
                            for block in message.content:
                                if isinstance(block, TextBlock):
                                    if callback:
                                        callback("assistant_text", {"text": block.text})
                                    result["output"] += block.text + "\n"
                                elif isinstance(block, ToolUseBlock):
                                    if callback:
                                        callback("tool_use", {
                                            "tool": block.name,
                                            "input": block.input,
                                        })

                        # Final result
                        elif isinstance(message, ResultMessage):
                            cost = message.total_cost_usd or 0.0
                            result["cost_usd"] = cost
                            result["turns"] = message.num_turns
                            result["status"] = "completed" if not message.is_error else "failed"

                            # Record cost
                            self.budget.record_cost(cost, message.num_turns, task_description)

                            # Update trust
                            if not message.is_error:
                                upgrade_msg = self.trust.record_success(self.project_path)
                                if upgrade_msg and callback:
                                    callback("trust_upgrade", {"message": upgrade_msg})
                            else:
                                self.trust.record_failure(self.project_path)

            # Task runtime watchdog:
            # - unset/empty: unbounded (no timeout)
            # - <= 0: unbounded (no timeout)
            # - > 0: seconds
            raw_timeout = os.environ.get("JARVIS_TASK_TIMEOUT_SECS", "").strip()
            max_runtime_seconds = int(raw_timeout) if raw_timeout else 0

            if max_runtime_seconds <= 0:
                await _run_query()
            else:
                await asyncio.wait_for(_run_query(), timeout=max_runtime_seconds)
        except asyncio.TimeoutError:
            result["status"] = "error"
            timeout_display = os.environ.get("JARVIS_TASK_TIMEOUT_SECS", "").strip() or "unbounded"
            result["output"] = (
                f"Task timed out after {timeout_display} seconds.\n"
                "Execution was terminated to avoid indefinite in_progress state."
            )
            self.trust.record_failure(self.project_path)
        except Exception as e:
            tb = traceback.format_exc()
            logger.error("run_task failed: %s\n%s", e, tb)
            result["status"] = "error"
            result["output"] = f"{e}\n\nTraceback:\n{tb}"
            self.trust.record_failure(self.project_path)

        finally:
            # Clean up containers
            await self._cleanup_containers()

        # Update task record
        final_status = result["status"]
        if final_status not in ("completed", "failed", "cancelled"):
            final_status = "failed"
        self.memory.transition_task(
            task_id,
            final_status,
            cost_usd=result["cost_usd"],
            turns=result["turns"],
            session_id=result["session_id"],
            result=result["output"][:5000],
        )

        # Store decision trace
        try:
            trace_outcome = "success" if result["status"] == "completed" else "failure"
            await self.tracer.store_trace(
                category=TraceCategory.TASK_EXECUTION,
                description=task_description[:500],
                decision=f"Executed as single-agent task",
                context={"turns": result["turns"], "cost": result["cost_usd"]},
                outcome=trace_outcome,
                project_path=self.project_path,
            )
        except Exception:
            pass

        # Events + macOS notifications
        if result["status"] == "completed":
            self.events.emit(
                EVENT_TASK_COMPLETE, task_description,
                task_id=task_id, cost_usd=result["cost_usd"],
                metadata={"origin": origin, "slack_notify": emit_notifications},
            )
            if emit_notifications:
                await notify_task_completed(task_id, task_description, result["cost_usd"])
        elif result["status"] in ("failed", "error"):
            self.events.emit(
                EVENT_ERROR, result["output"][:200],
                task_id=task_id,
                metadata={
                    "error": result["output"][:5000],
                    "origin": origin,
                    "slack_notify": emit_notifications,
                },
            )
            if emit_notifications:
                await notify_task_failed(task_id, task_description, result["output"][:100])

        append_project_turn(
            self.project_path,
            actor=f"task:{origin}",
            message=task_description,
            outcome=f"status={result['status']} turns={result['turns']} cost=${result['cost_usd']:.2f}",
        )

        if callback:
            callback("task_completed", result)

        return result

    async def _ensure_chat_client(self) -> ClaudeSDKClient:
        if self._chat_client is None:
            self._chat_client = ClaudeSDKClient(options=self._build_options())
            await self._chat_client.connect()
        return self._chat_client

    async def _reset_chat_client(self) -> None:
        if self._chat_client is not None:
            try:
                await self._chat_client.disconnect()
            except Exception:
                pass
            self._chat_client = None

    def _build_router_options(self) -> ClaudeAgentOptions:
        """Build a tool-less routing call.

        This is the "conversation control plane": decide whether to reply, ask, or execute.
        Tool execution happens only after an explicit router decision of mode=execute.
        """
        # NOTE: We intentionally do not use SDK structured-output / json-schema here.
        # Some Anthropic-compatible proxies do not support the CLI `--json-schema` flag,
        # which results in `ResultMessage.result=None`. Instead we require JSON in text
        # and parse it ourselves, surfacing any failures explicitly.
        return ClaudeAgentOptions(
            # Do not duplicate the whole system prompt; keep it routing-specific.
            system_prompt=(
                "You are Jarvis (autonomous coding agent).\n"
                "You are doing internal routing: decide what to do with the user's message.\n"
                "Never mention routing, control planes, or that you are a router.\n\n"
                "You MUST return a single JSON object (no markdown, no prose).\n"
                "Keys allowed: mode, reply, question, choices, task_description, confidence, reason.\n"
                "mode must be one of: reply | ask | execute.\n"
                "confidence must be a number 0..1.\n\n"
                "Modes:\n"
                "- reply: user is asking a question or chatting; produce a direct helpful reply.\n"
                "- ask: you are unsure or need a missing detail; ask a single concise question.\n"
                "- execute: user is asking you to do work; produce an executable task_description.\n\n"
                "Rules:\n"
                "- Prefer execute when the user clearly requests work.\n"
                "- Prefer ask when multiple interpretations exist or critical details are missing.\n"
                "- Keep reply/ask conversational and concise.\n"
                "- If execute, task_description must be specific and include success criteria.\n"
                "- This system uses Apple 'container' CLI (command: container), not Docker.\n"
            ),
            # Disable base tools completely for routing.
            tools=[],
            allowed_tools=[],
            permission_mode="default",
            max_turns=1,
            max_budget_usd=1.0,
            model=self.config.models.planner,
            cwd=self.project_path,
        )

    @staticmethod
    def _extract_json_object(text: str) -> str:
        """Extract a JSON object from model text.

        Some models wrap JSON in markdown fences like ```json ... ```.
        We still require the output to contain a single JSON object, but
        we parse defensively so the router remains usable.
        """
        raw = (text or "").strip()
        if not raw:
            return ""

        # Handle fenced blocks.
        fence_prefixes = ("```json", "```JSON", "```")
        if raw.startswith(fence_prefixes):
            # Best-effort: drop the first fence line and the trailing fence.
            lines = raw.splitlines()
            if lines and lines[0].lstrip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].rstrip().endswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines).strip()

        # If there's still surrounding prose, slice the first {...} object.
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return raw[start : end + 1].strip()
        return raw

    async def _route_message(self, *, user_message: str, origin: str) -> MessageRouteDecision:
        """Model-driven routing: reply vs ask vs execute (no heuristics)."""
        # Include minimal continuity from last turn in this channel/session (Slack or WS).
        prior = self.memory.get_channel_turn(origin) if origin else None
        context_lines: list[str] = []
        if prior:
            context_lines.append("Prior turn (most recent):")
            context_lines.append(f"- user: {(prior.get('last_user_message') or '')[:600]}")
            context_lines.append(f"- assistant: {(prior.get('last_assistant_reply') or '')[:900]}")
        context_lines.append("Current user message:")
        context_lines.append(user_message)
        prompt = "\n".join(context_lines).strip()

        async with self._router_lock:
            options = self._build_router_options()
            try:
                async with ClaudeSDKClient(options=options) as client:
                    await client.query(prompt)
                    text_buf: list[str] = []
                    async for message in client.receive_response():
                        if isinstance(message, AssistantMessage):
                            for block in message.content:
                                if isinstance(block, TextBlock):
                                    text_buf.append(block.text)
                        if isinstance(message, ResultMessage):
                            if message.is_error:
                                # Fail loudly with whatever diagnostics the SDK provides.
                                # Some Anthropic-compatible proxies return an error ResultMessage
                                # with empty assistant text; treat that as a hard router failure.
                                err = message.result or message.structured_output or "unknown_router_error"
                                raise RuntimeError(f"Router model error: {err}")

                            # Prefer structured output when present.
                            if message.structured_output:
                                return cast(MessageRouteDecision, message.structured_output)
                            if isinstance(message.result, dict):
                                return cast(MessageRouteDecision, message.result)

                            raw = "".join(text_buf).strip()
                            if not raw and message.result is not None:
                                raw = str(message.result).strip()
                            if not raw:
                                raise RuntimeError("Router returned empty output.")
                            try:
                                parsed = json.loads(self._extract_json_object(raw))
                            except Exception as exc:
                                raise RuntimeError(f"Router returned non-JSON text: {raw[:500]}") from exc
                            if not isinstance(parsed, dict):
                                raise RuntimeError(f"Router JSON was not an object: {type(parsed).__name__}")
                            return cast(MessageRouteDecision, parsed)
            except Exception as exc:
                tb = traceback.format_exc()
                logger.error("router failed: %s\n%s", exc, tb)
                return {
                    "mode": "reply",
                    "confidence": 0.0,
                    "reply": f"Router error: {exc}",
                    "reason": "router_exception",
                }

        return {
            "mode": "reply",
            "confidence": 0.0,
            "reply": "Router produced no result.",
            "reason": "router_no_result",
        }

    async def close(self) -> None:
        """Graceful shutdown for long-lived SDK clients."""
        await self._reset_chat_client()

    def get_preflight_status(self) -> dict:
        """Return last known model/provider preflight result."""
        return dict(self._preflight_status)

    async def run_model_preflight(self, *, live_check: bool = False, timeout_seconds: int = 25) -> dict:
        """Validate provider+models before serving requests."""
        errors: list[str] = []
        warnings: list[str] = []
        provider = {
            "base_url": os.environ.get("ANTHROPIC_BASE_URL", ""),
            "token_present": bool(
                os.environ.get("ANTHROPIC_AUTH_TOKEN")
                or os.environ.get("ANTHROPIC_API_KEY")
            ),
        }
        models = {
            "planner": self.config.models.planner,
            "executor": self.config.models.executor,
            "reviewer": self.config.models.reviewer,
            "quick": self.config.models.quick,
        }

        if not provider["token_present"]:
            warnings.append("missing_anthropic_token_env_using_cli_auth_if_available")
        for key, value in models.items():
            if not str(value).strip():
                errors.append(f"missing_model:{key}")
        if provider["base_url"] and "api.z.ai" in provider["base_url"]:
            # z.ai Anthropic-compatible proxy typically expects glm model IDs.
            non_glm = [k for k, v in models.items() if not str(v).strip().lower().startswith("glm")]
            if non_glm:
                warnings.append(f"z_ai_non_glm_models:{','.join(non_glm)}")

        live_probe = {"attempted": bool(live_check), "ok": False, "error": ""}
        if live_check and not errors:
            try:
                async def _probe() -> None:
                    async with ClaudeSDKClient(options=self._build_options()) as client:
                        await client.query("Respond with exactly: JARVIS_PREFLIGHT_OK")
                        async for msg in client.receive_response():
                            if isinstance(msg, ResultMessage) and msg.is_error:
                                raise RuntimeError(str(msg.result or "live_probe_failed"))
                await asyncio.wait_for(_probe(), timeout=max(5, timeout_seconds))
                live_probe["ok"] = True
            except Exception as exc:
                live_probe["error"] = str(exc)
                errors.append("live_probe_failed")

        status = {
            "ready": len(errors) == 0,
            "checked_at": time.time(),
            "live_check": bool(live_check),
            "errors": errors,
            "warnings": warnings,
            "provider": provider,
            "models": models,
            "live_probe": live_probe,
        }
        self._preflight_status = status
        return dict(status)

    async def chat(self, user_message: str) -> dict:
        """Run a conversational turn and return assistant text."""
        result = {
            "status": "unknown",
            "reply": "",
            "cost_usd": 0.0,
            "turns": 0,
            "session_id": None,
            "tools": [],
            "diagnostics": {},
        }
        tools_used: set[str] = set()

        ensure_project_jarvis_file(self.project_path)
        self.events.emit(
            "chat_user",
            user_message[:200],
            metadata={"message": user_message[:5000]},
        )

        async with self._chat_lock:
            try:
                client = await self._ensure_chat_client()
                await client.query(user_message)

                result["reply"] = ""
                async for message in client.receive_response():
                    if isinstance(message, SystemMessage):
                        if message.subtype == "init":
                            self._session_id = message.data.get("session_id")
                            result["session_id"] = self._session_id
                    elif isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                result["reply"] += block.text + "\n"
                            elif isinstance(block, ToolUseBlock):
                                tools_used.add(block.name)
                    elif isinstance(message, ResultMessage):
                        result["cost_usd"] = message.total_cost_usd or 0.0
                        result["turns"] = message.num_turns
                        result["status"] = "completed" if not message.is_error else "failed"
                        result["diagnostics"] = {
                            "sdk_result": message.result,
                            "structured_output": message.structured_output,
                            "usage": message.usage,
                        } if message.is_error else {}
                        if message.result and not result["reply"].strip():
                            result["reply"] = str(message.result).strip()
                        self.budget.record_cost(
                            result["cost_usd"], result["turns"], f"chat:{user_message[:120]}"
                        )

                result["reply"] = result["reply"].strip()
                result["tools"] = sorted(tools_used)
                if result["status"] != "completed" and not result["reply"]:
                    try:
                        diag_text = json.dumps(result["diagnostics"], default=str)[:3000]
                    except Exception:
                        diag_text = str(result["diagnostics"])[:3000]
                    result["reply"] = (
                        "Chat request failed without a textual error from the model runtime.\n"
                        f"Diagnostics: {diag_text}"
                    )
            except Exception as e:
                tb = traceback.format_exc()
                logger.error("chat failed: %s\n%s", e, tb)
                await self._reset_chat_client()
                result["status"] = "error"
                result["reply"] = f"{e}\n\nTraceback:\n{tb}"
                result["tools"] = sorted(tools_used)
                result["diagnostics"] = {"exception": str(e)}

        if result["status"] == "completed" and result["reply"]:
            self.events.emit(
                "chat_assistant",
                result["reply"][:200],
                cost_usd=result["cost_usd"],
                metadata={"reply": result["reply"][:5000], "tools": result["tools"]},
            )
        else:
            self.events.emit(
                EVENT_ERROR,
                (result["reply"] or "Chat failed")[:200],
                metadata={
                    "error": (result["reply"] or "Chat failed")[:5000],
                    "diagnostics": result.get("diagnostics") or {},
                },
            )

        append_project_turn(
            self.project_path,
            actor="chat",
            message=user_message,
            outcome=(result["reply"] or result["status"])[:500],
        )

        return result

    async def handle_message(
        self,
        user_message: str,
        *,
        origin: str = "message",
    ) -> dict:
        """Conversational entrypoint: model decides whether to reply, ask, or execute."""
        self._ingest_research_urls_from_text(user_message, source=f"chat:{origin}")

        decision = await self._route_message(user_message=user_message, origin=origin)
        mode = (decision.get("mode") or "reply").strip()

        # Emit routing decision for UI visibility/debugging.
        self.events.emit(
            "chat_route",
            f"mode={mode} conf={decision.get('confidence')}",
            metadata={"decision": decision, "origin": origin},
        )

        if decision.get("reason") in ("router_exception", "router_no_result"):
            # Router failures should be visible, but should not prevent a normal chat reply.
            self.events.emit(
                EVENT_ERROR,
                (decision.get("reply") or "Router failed")[:200],
                metadata={
                    "error": (decision.get("reply") or "Router failed")[:5000],
                    "origin": origin,
                    "stage": "router",
                },
            )
            chat_result = await self.chat(user_message)
            reply = (chat_result.get("reply") or "").strip()
            self.memory.save_channel_turn(origin, self.project_path, user_message, reply)
            return {
                "status": "completed" if reply else "failed",
                "route": "chat",
                "reply": reply or (decision.get("reply") or "Router failed"),
                "decision": decision,
            }

        if mode == "execute":
            task_desc = (decision.get("task_description") or "").strip()
            if not task_desc:
                # Router said execute but didn't give a task description: treat as ask.
                reply = (decision.get("reply") or "").strip() or "What exactly should I do?"
                self.memory.save_channel_turn(origin, self.project_path, user_message, reply)
                return {
                    "status": "needs_input",
                    "route": "ask",
                    "reply": reply,
                    "decision": decision,
                }

            asyncio.create_task(self.run_task(task_desc, origin=origin))
            reply = (decision.get("reply") or "").strip() or "Starting now."
            self.memory.save_channel_turn(origin, self.project_path, user_message, reply)
            return {
                "status": "queued",
                "route": "task",
                "queued": task_desc[:200],
                "reply": reply,
                "decision": decision,
            }

        if mode == "ask":
            reply = (decision.get("reply") or "").strip()
            if not reply:
                q = (decision.get("question") or "").strip()
                reply = q or "I need one detail to proceed. What should I assume?"
            self.memory.save_channel_turn(origin, self.project_path, user_message, reply)
            return {
                "status": "needs_input",
                "route": "ask",
                "reply": reply,
                "choices": decision.get("choices") or [],
                "decision": decision,
            }

        # reply
        reply = (decision.get("reply") or "").strip()
        if not reply:
            # If router failed to produce a reply, fall back to the normal chat model.
            chat_result = await self.chat(user_message)
            reply = (chat_result.get("reply") or "").strip()
        self.memory.save_channel_turn(origin, self.project_path, user_message, reply)
        return {
            "status": "completed",
            "route": "chat",
            "reply": reply,
            "decision": decision,
        }

    async def _cleanup_containers(self) -> None:
        """Stop and remove all active containers."""
        for container_id in self._active_containers:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "container", "stop", container_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=10)
                proc = await asyncio.create_subprocess_exec(
                    "container", "delete", container_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=10)
            except Exception:
                pass
        self._active_containers.clear()

    async def get_status(self) -> dict:
        """Get current Jarvis status."""
        trust_status = self.trust.status(self.project_path)
        budget_status = self.budget.summary()
        active_tasks = self.memory.list_tasks(self.project_path, status="in_progress")
        recent_tasks = self.memory.list_tasks(self.project_path)[:5]

        return {
            "project": self.project_path,
            "trust": trust_status,
            "budget": budget_status,
            "active_tasks": [{"id": t.id, "description": t.description} for t in active_tasks],
            "recent_tasks": [
                {
                    "id": t.id,
                    "description": t.description,
                    "status": t.status,
                    "cost": f"${t.cost_usd:.2f}",
                }
                for t in recent_tasks
            ],
            "containers": len(self._active_containers),
            "session_id": self._session_id,
            "preflight": self.get_preflight_status(),
        }

    def should_use_pipeline(self, task_description: str) -> bool:
        """Heuristic: use multi-agent pipeline for complex tasks."""
        trust_status = self.trust.status(self.project_path)
        if trust_status["tier"] < 2:
            return False  # Pipeline needs container access (T2+)

        complexity_signals = [
            "build", "implement", "create", "refactor", "migrate",
            "add feature", "full stack", "end to end", "e2e",
            "rewrite", "redesign", "architecture",
        ]
        task_lower = task_description.lower()
        return any(signal in task_lower for signal in complexity_signals)

    async def run_pipeline(self, task_description: str, callback=None) -> dict:
        """Execute a task using the multi-agent pipeline.

        Uses Planner -> Executor -> Tester -> Reviewer flow.
        Falls back to single-agent mode on error.
        """
        pipeline = MultiAgentPipeline(self.project_path)
        result = await pipeline.run(task_description, callback=callback)

        # Convert PipelineResult to dict for CLI compatibility
        return {
            "task_id": result.task_id,
            "status": result.status,
            "cost_usd": result.total_cost_usd,
            "turns": result.total_turns,
            "session_id": None,
            "plan": result.plan,
            "review": result.review,
            "subtask_count": len(result.subtask_results),
            "subtasks": [
                {
                    "id": s.subtask_id,
                    "status": s.status,
                    "output": s.output[:240],
                    "files_changed": s.files_changed[:20],
                }
                for s in result.subtask_results[:100]
            ],
            "output": f"Pipeline {result.status}. "
                      f"Subtasks: {len(result.subtask_results)}. "
                      f"Cost: ${result.total_cost_usd:.2f}",
        }

    async def run_autonomous(self, description: str, callback=None, resume: bool = False) -> dict:
        """Run the autonomous build harness for a project.

        Creates a BuildHarness that loops through features:
        init → implement → test → commit → next feature.

        Args:
            description: Project/task description for planning
            callback: Optional progress callback
            resume: If True, resume from saved state

        Returns:
            Dict with build results
        """
        harness = BuildHarness(
            project_path=self.project_path,
            orchestrator=self,
        )

        if resume:
            harness._load_state()

        self.events.emit(
            "build_start",
            f"Autonomous build: {description[:100]}",
            metadata={"description": description, "resume": resume},
        )

        try:
            await harness.run(callback=callback)
            status = harness._context.state.value
            self.events.emit(
                "build_complete",
                f"Build finished in state: {status}",
                metadata={"final_state": status},
            )
            return {
                "status": status,
                "state": harness._context.state.value,
                "history": harness._context.history,
            }
        except Exception as e:
            self.events.emit(EVENT_ERROR, f"Build failed: {e}")
            return {"status": "error", "error": str(e)}

    async def save_session(self) -> None:
        """Save session summary for cross-session continuity."""
        if not self._session_id:
            return

        completed = self.memory.list_tasks(self.project_path, status="completed")
        pending = self.memory.list_tasks(self.project_path, status="pending")

        summary_parts = []
        for task in completed[-5:]:
            summary_parts.append(f"- Completed: {task.description}")
        for task in pending[:5]:
            summary_parts.append(f"- Pending: {task.description}")

        self.memory.save_session_summary(
            session_id=self._session_id,
            project_path=self.project_path,
            summary="\n".join(summary_parts) or "No tasks recorded",
            tasks_completed=[t.id for t in completed[-5:]],
            tasks_remaining=[t.id for t in pending[:5]],
        )
