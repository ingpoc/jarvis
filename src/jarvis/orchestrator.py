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
import os
import uuid
from pathlib import Path

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
from jarvis.container_tools import create_container_mcp_server
from jarvis.events import EventCollector, EVENT_TOOL_USE, EVENT_TASK_START, EVENT_TASK_COMPLETE, EVENT_ERROR
from jarvis.git_tools import create_git_mcp_server
from jarvis.harness import BuildHarness
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
from jarvis.self_learning import learn_from_task, get_relevant_learnings, format_learning_for_context


class JarvisOrchestrator:
    """Main Jarvis orchestration engine."""

    def __init__(self, project_path: str | None = None):
        self.project_path = project_path or os.getcwd()
        self.config = JarvisConfig.load()
        self.trust = TrustEngine()
        self.budget = BudgetController()
        self.memory = MemoryStore()
        self.tracer = DecisionTracer(memory=self.memory)
        self.container_server = create_container_mcp_server()
        self.git_server = create_git_mcp_server()
        self.review_server = create_review_mcp_server()
        self.browser_server = create_browser_mcp_server()
        self._session_id: str | None = None
        self._active_containers: list[str] = []
        self.loop_detector = LoopDetector(
            max_iterations=self.config.budget.max_turns_per_subtask
        )
        self.events = EventCollector(memory=self.memory)
        self.code_orchestrator = CodeOrchestrator(
            mcp_servers={
                "jarvis-container": self.container_server,
                "jarvis-git": self.git_server,
            },
            project_path=self.project_path,
        )

    def _build_system_prompt(self) -> str:
        """Build system prompt with project context and trust level."""
        trust_status = self.trust.status(self.project_path)
        budget_status = self.budget.summary()

        # Load JARVIS.md if it exists
        jarvis_md = ""
        jarvis_md_path = Path(self.project_path) / "JARVIS.md"
        if jarvis_md_path.exists():
            jarvis_md = f"\n\n## Project Rules (JARVIS.md)\n{jarvis_md_path.read_text()}"

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

        # Load high-confidence learnings (error-fix patterns)
        learnings = self.memory.get_learnings(
            project_path=self.project_path,
            min_confidence=0.7,
            limit=5,
        )
        learnings_text = ""
        if learnings:
            learnings_text = "\n\n## Known Error-Fix Patterns"
            for learning in learnings:
                learnings_text += f"\n{format_learning_for_context(learning)}"

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
{jarvis_md}{continuity}{patterns_text}{learnings_text}"""

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
        tools = ["Read", "Glob", "Grep", "WebSearch", "WebFetch"]

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
        """Hook: track container lifecycle, emit events, detect loops, capture execution records."""
        tool_name = input_data.get("tool_name", "")
        tool_response = input_data.get("tool_response", "")
        tool_input = input_data.get("tool_input", {})

        # Emit tool use event
        self.events.emit(
            EVENT_TOOL_USE,
            f"{tool_name}",
            task_id=context.get("task_id"),
            metadata={"tool": tool_name},
        )

        # Capture execution record for learning
        task_id = context.get("task_id", "unknown")
        session_id = self._session_id or "unknown"

        # Extract error information
        error_message = None
        exit_code = 0
        if isinstance(tool_response, str):
            if "error" in tool_response.lower() or "exception" in tool_response.lower():
                error_message = tool_response[:500]
                exit_code = 1

        # Extract files touched (for Edit/Write tools)
        files_touched = []
        if tool_name in ["Edit", "Write"]:
            if isinstance(tool_input, dict) and "file_path" in tool_input:
                files_touched.append(tool_input["file_path"])

        # Record execution
        try:
            self.memory.record_execution(
                task_id=task_id,
                session_id=session_id,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_response,
                exit_code=exit_code,
                files_touched=files_touched if files_touched else None,
                error_message=error_message,
                duration_ms=0.0,  # Could be enhanced with actual timing
                project_path=self.project_path,
            )
        except Exception:
            # Don't block on execution record failure
            pass

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
            mcp_servers={
                "jarvis-container": self.container_server,
                "jarvis-git": self.git_server,
                "jarvis-review": self.review_server,
                "jarvis-browser": self.browser_server,
            },
            hooks={
                "PreToolUse": [
                    HookMatcher(hooks=[self._pre_tool_hook]),
                ],
                "PostToolUse": [
                    HookMatcher(hooks=[self._post_tool_hook]),
                ],
            },
        )

        # Resume previous session if available
        if self._session_id:
            options.resume = self._session_id

        return options

    async def run_task(self, task_description: str, callback=None) -> dict:
        """Execute a task autonomously.

        Args:
            task_description: Natural language task description
            callback: Optional callback(event_type, data) for progress reporting

        Returns:
            Task result dict with status, cost, session_id
        """
        # Create task record
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = self.memory.create_task(task_id, task_description, self.project_path)
        self.memory.update_task(task_id, status="in_progress")

        await notify_task_started(task_id, task_description)
        self.events.emit(EVENT_TASK_START, task_description, task_id=task_id)
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

        except Exception as e:
            result["status"] = "error"
            result["output"] = str(e)
            self.trust.record_failure(self.project_path)

        finally:
            # Clean up containers
            await self._cleanup_containers()

        # Update task record
        self.memory.update_task(
            task_id,
            status=result["status"],
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
            )
            await notify_task_completed(task_id, task_description, result["cost_usd"])
        elif result["status"] in ("failed", "error"):
            self.events.emit(
                EVENT_ERROR, result["output"][:200],
                task_id=task_id,
            )
            await notify_task_failed(task_id, task_description, result["output"][:100])

        if callback:
            callback("task_completed", result)

        return result

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
