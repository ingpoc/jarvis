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
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
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
)
from jarvis.container_tools import create_container_mcp_server, cleanup_containers
from jarvis.events import EventCollector, EVENT_TASK_START, EVENT_TASK_COMPLETE, EVENT_ERROR
from jarvis.git_tools import create_git_mcp_server
from jarvis.harness import BuildHarness
from jarvis.memory import MemoryStore
from jarvis.loop_detector import LoopDetector
from jarvis.notifications import (
    notify_approval_needed,
    notify_task_completed,
    notify_task_failed,
    notify_task_started,
)
from jarvis.review_tools import create_review_mcp_server
from jarvis.trust import TrustEngine
from jarvis.session_manager import SessionManager
from jarvis.agents import MultiAgentPipeline
from jarvis.model_router import get_model_router
from jarvis.self_learning import learn_from_task
from jarvis.universal_heuristics import auto_seed_project
# Subpackage modules
from jarvis.orchestrator.capabilities import DynamicCapabilitiesManager
from jarvis.orchestrator.mcp_loader import MCPConfigLoader
from jarvis.orchestrator.prompts import SystemPromptBuilder
from jarvis.orchestrator.hooks import OrchestratorHooks


def _safe_json_parse(text: str, default: Any = None) -> Any:
    """Safely parse JSON, returning default on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


logger = logging.getLogger(__name__)


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

        # Core components
        self.trust = TrustEngine()
        self.budget = BudgetController()
        self.memory = MemoryStore()
        self.tracer = DecisionTracer(memory=self.memory)

        # MCP servers
        self.container_server = create_container_mcp_server()
        self.git_server = create_git_mcp_server()
        self.review_server = create_review_mcp_server()
        self.browser_server = create_browser_mcp_server()

        # Use subpackage modules
        self._mcp_loader = MCPConfigLoader(self.project_path)
        self._capabilities = DynamicCapabilitiesManager()
        self._prompt_builder = SystemPromptBuilder(
            trust=self.trust,
            budget=self.budget,
            memory=self.memory,
            project_path=self.project_path,
            config_max_turns=self.config.budget.max_turns_per_subtask,
        )

        # Load configured MCP servers
        self._configured_mcp_servers = self._mcp_loader.load_configured_mcp_servers()

        # Session state
        self._session_id: str | None = None
        self._active_containers: list[str] = []
        self.loop_detector = LoopDetector(
            max_iterations=self.config.budget.max_turns_per_subtask
        )
        self.events = EventCollector(memory=self.memory)
        self._chat_lock = asyncio.Lock()
        self._chat_client: ClaudeSDKClient | None = None  # Deprecated: use SessionManager
        self._session_manager = SessionManager.get_instance()
        self._channel_id = "default"  # Default channel for this orchestrator

        # Code orchestrator
        self.code_orchestrator = CodeOrchestrator(
            mcp_servers={
                "jarvis-container": self.container_server,
                "jarvis-git": self.git_server,
            },
            project_path=self.project_path,
        )

        # Hooks (initialized after notifications module is available)
        self._hooks: OrchestratorHooks | None = None

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

    def _init_hooks(self) -> None:
        """Initialize hooks lazily (after notifications module is imported)."""
        if self._hooks is None:
            import jarvis.notifications as notifications
            self._hooks = OrchestratorHooks(
                trust=self.trust,
                budget=self.budget,
                memory=self.memory,
                loop_detector=self.loop_detector,
                events=self.events,
                project_path=self.project_path,
                notifications_module=notifications,
            )

    def _build_mcp_servers(self) -> dict:
        """Build static + dynamic MCP server map."""
        return self._mcp_loader.build_mcp_servers_map(
            container_server=self.container_server,
            git_server=self.git_server,
            review_server=self.review_server,
            browser_server=self.browser_server,
            configured_servers=self._configured_mcp_servers,
            dynamic_servers=self._capabilities.mcp_servers,
        )

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

    def _build_system_prompt(self) -> str:
        """Build system prompt with project context and trust level."""
        return self._prompt_builder.build()

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
        self._init_hooks()
        return await self._hooks.pre_tool_hook(input_data, tool_use_id, context)

    async def _post_tool_hook(self, input_data: dict, tool_use_id: str | None, context: dict) -> dict:
        """Hook: track container lifecycle, emit events, detect loops, capture execution records."""
        self._init_hooks()
        result = await self._hooks.post_tool_hook(input_data, tool_use_id, context)
        # Track active containers locally (not in hooks module)
        tool_name = input_data.get("tool_name", "")
        tool_response = input_data.get("tool_response", "")
        if "container_run" in tool_name and isinstance(tool_response, str):
            try:
                data = json.loads(tool_response)
                if data.get("status") == "running":
                    container_id = data.get("container_id")
                    if container_id:
                        self._active_containers.append(container_id)
            except (json.JSONDecodeError, TypeError):
                pass
        return result

    async def _post_message_hook(self, input_data: dict, context: dict) -> dict:
        """Hook: track token usage and costs from ResultMessage events."""
        self._init_hooks()
        context["session_id"] = self._session_id
        context["model"] = self.config.models.executor
        return await self._hooks.post_message_hook(input_data, context)

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
                "PostMessage": [
                    HookMatcher(hooks=[self._post_message_hook]),
                ],
            },
            agents=self._capabilities.agents or None,
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
        return self._capabilities.register_mcp_server(name, command, args, env)

    def register_agent(
        self,
        name: str,
        description: str,
        prompt: str,
        tools: list[str] | None = None,
        model: str | None = None,
    ) -> dict:
        """Register a dynamic SDK sub-agent."""
        return self._capabilities.register_agent(name, description, prompt, tools, model)

    def register_skill(self, name: str, description: str, content: str) -> dict:
        """Register a dynamic skill instruction block visible to Jarvis."""
        return self._capabilities.register_skill(name, description, content)

    def get_capabilities(self) -> dict:
        """Return capability inventory for UI/diagnostics."""
        dynamic_names = sorted(self._capabilities.mcp_servers.keys())
        static_names = [
            "jarvis-container",
            "jarvis-git",
            "jarvis-review",
            "jarvis-browser",
            *sorted(self._configured_mcp_servers.keys()),
        ]
        dynamic_agents = sorted(self._capabilities.agents.keys())
        dynamic_skills = sorted(self._capabilities.skills.keys())
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
        channel_id: str | None = None,
    ) -> dict:
        """Execute a task autonomously.

        Args:
            task_description: Natural language task description
            callback: Optional callback(event_type, data) for progress reporting
            origin: Origin identifier (user, slack, a2a, etc.)
            emit_notifications: Whether to emit notifications
            channel_id: Optional channel ID for session isolation

        Returns:
            Task result dict with status, cost, session_id
        """
        # Note: channel_id is passed through to _ensure_chat_client() for session isolation.
        # We do NOT call set_channel() here to avoid mutating shared _channel_id state
        # which would cause race conditions with concurrent A2A tasks.
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

        # Seed universal heuristics on first task (idempotent)
        try:
            seed_result = await auto_seed_project(self.memory, self.project_path)
            if seed_result.get("seeded", 0) > 0:
                self.events.emit(
                    "heuristics_seeded",
                    f"Seeded {seed_result['seeded']} universal heuristics for {seed_result.get('languages', [])}",
                    task_id=task_id,
                    metadata=seed_result,
                )
        except Exception:
            pass  # Seeding is best-effort

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

        # Model routing: log routing decision for observability
        try:
            router = get_model_router()
            routing = await router.route_task(
                task_description=task_description,
                budget_remaining_usd=self.config.budget.max_per_session_usd - self.budget._session_spent,
            )
            self.events.emit(
                "model_routing",
                f"Routed to {routing.tier.value}: {routing.reason}",
                task_id=task_id,
                metadata={
                    "tier": routing.tier.value,
                    "model": routing.model,
                    "reason": routing.reason,
                    "estimated_cost": routing.estimated_cost_usd,
                },
            )
        except Exception:
            pass  # Don't block task on routing failure

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

        # Self-learning: extract patterns from execution records
        try:
            learning_stats = await learn_from_task(
                task_id=task_id,
                project_path=self.project_path,
                memory=self.memory,
            )
            if learning_stats["learnings_saved"] > 0:
                self.events.emit(
                    "learning_captured",
                    f"Learned {learning_stats['learnings_saved']} patterns from task",
                    task_id=task_id,
                    metadata=learning_stats,
                )
        except Exception as e:
            # Don't block task completion on learning failure
            self.events.emit(EVENT_ERROR, f"Learning extraction failed: {e}", task_id=task_id)

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

    async def _ensure_chat_client(self, channel_id: str | None = None) -> ClaudeSDKClient:
        """Get or create a ClaudeSDKClient for the given channel.

        Args:
            channel_id: Channel identifier for session isolation.
                       If None, uses the orchestrator's default channel.
        """
        channel = channel_id or self._channel_id
        return await self._session_manager.get_client(channel, self._build_options())

    def set_channel(self, channel_id: str) -> None:
        """Set the default channel for this orchestrator instance."""
        self._channel_id = channel_id

    async def _reset_chat_client(self, channel_id: str | None = None) -> None:
        """Reset clients for session cleanup.

        Args:
            channel_id: If provided, reset only this channel's client.
                       If None, reset the legacy single client only.
        """
        # Reset the legacy single client (deprecated)
        if self._chat_client is not None:
            try:
                await self._chat_client.disconnect()
            except Exception:
                pass
            self._chat_client = None

        # Reset SessionManager channel client if specified
        if channel_id:
            await self._session_manager.close_client(channel_id)

    async def close(self) -> None:
        """Graceful shutdown for long-lived SDK clients."""
        await self._reset_chat_client()
        # Note: SessionManager manages its own client lifecycle

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
        """Conversational entrypoint (single-pass).

        Every user message goes directly to the chat model. The model itself
        decides when to ask questions vs. invoke tools. This removes the extra
        router model call and cuts latency for normal chat interactions.
        """
        self._ingest_research_urls_from_text(user_message, source=f"chat:{origin}")
        chat_result = await self.chat(user_message)
        reply = (chat_result.get("reply") or "").strip()
        status = "completed" if (chat_result.get("status") == "completed" and reply) else "failed"
        # Keep decision payload for API backward compatibility with existing clients.
        decision = {
            "mode": "chat",
            "confidence": 1.0 if status == "completed" else 0.0,
            "reason": "direct_chat_model",
        }
        self.events.emit(
            "chat_route",
            f"mode=chat conf={decision['confidence']}",
            metadata={"decision": decision, "origin": origin},
        )
        self.memory.save_channel_turn(origin, self.project_path, user_message, reply)
        return {
            "status": status,
            "route": "chat",
            "reply": reply,
            "decision": decision,
        }

    async def _cleanup_containers(self) -> None:
        """Stop and remove all active containers."""
        await cleanup_containers(self._active_containers)
        self._active_containers.clear()

    async def get_status(self) -> dict:
        """Get current Jarvis status.

        Returns a dict compatible with the SwiftUI JarvisStatusResponse.
        """
        trust_status = self.trust.status(self.project_path)
        budget_status = self.budget.summary()
        active_tasks = self.memory.list_tasks(self.project_path, status="in_progress")
        recent_tasks = self.memory.list_tasks(self.project_path)[:5]

        # Derive overall status for SwiftUI
        if active_tasks:
            overall_status = "building"
        elif any(True for _ in self.memory.list_tasks(self.project_path, status="failed")):
            overall_status = "error"
        else:
            overall_status = "idle"

        return {
            "status": overall_status,
            "project": self.project_path,
            "trust": {
                "tier": trust_status["tier"],
                "tier_name": trust_status["tier_name"],
                "successful_tasks": trust_status["successful_tasks"],
                "total_tasks": trust_status["total_tasks"],
                "rollbacks": trust_status["rollbacks"],
                "tasks_until_upgrade": trust_status["tasks_until_upgrade"],
            },
            "budget": {
                "session": budget_status["session"],
                "daily": budget_status["daily"],
                "turns": budget_status["turns"],
            },
            "current_session": self._session_id,
            "current_feature": active_tasks[0].description if active_tasks else None,
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
