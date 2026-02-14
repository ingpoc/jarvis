"""Jarvis CLI: natural language delegation to an autonomous dev partner.

Usage:
    jarvis run "add dark mode to settings"   # Delegate task
    jarvis run -p "build REST API"           # Force pipeline mode
    jarvis build "task management API"       # Autonomous build loop
    jarvis build --resume                    # Resume interrupted build
    jarvis features                          # Show feature progress
    jarvis timeline                          # Show event timeline
    jarvis timeline --today                  # Today's events only
    jarvis status                            # Show status
    jarvis log <task-id>                     # View task log
    jarvis trust                             # Show trust level
    jarvis trust raise                       # Request trust upgrade
    jarvis trust set <tier>                  # Set trust tier (0-4)
    jarvis budget                            # Show budget status
    jarvis tasks                             # List all tasks
    jarvis init                              # Initialize project
    jarvis config <key>=<value>              # Set configuration
    jarvis test <url>                        # Browser test
    jarvis test <url> -w                     # Wallet test (Solflare mock)
    jarvis daemon                            # Run daemon (foreground)
    jarvis daemon --install                  # Install as launchd service
    jarvis daemon --uninstall                # Remove launchd service
"""

import asyncio
import datetime
import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jarvis.budget import BudgetController
from jarvis.config import JARVIS_HOME, JarvisConfig, ensure_jarvis_home
from jarvis.context_files import should_use_project_jarvis
from jarvis.memory import MemoryStore, generate_jarvis_md
from jarvis.orchestrator import JarvisOrchestrator
from jarvis.container_templates import detect_template, list_templates as list_all_templates, get_template
from jarvis.trust import TrustEngine, TrustTier

console = Console()


def _run_async(coro):
    """Run async function from sync context."""
    return asyncio.run(coro)


class JarvisCLI(click.Group):
    """Custom group that routes unknown commands as task descriptions."""

    def parse_args(self, ctx, args):
        """If first arg isn't a known command, treat all args as a 'run' task."""
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            # Unknown first arg = task delegation, prepend 'run'
            args = ["run"] + args
        return super().parse_args(ctx, args)


@click.group(cls=JarvisCLI)
def cli():
    """Jarvis: Autonomous Mac-native development partner.

    Delegate tasks in natural language:
        jarvis "fix the failing tests"
        jarvis run -p "build a REST API"
    """
    pass


# --- Task execution ---


@cli.command()
@click.argument("task", nargs=-1, required=True)
@click.option("--pipeline", "-p", is_flag=True, help="Force multi-agent pipeline mode")
@click.option("--single", "-s", is_flag=True, help="Force single-agent mode")
def run(task, pipeline, single):
    """Delegate a task to Jarvis.

    Examples:
        jarvis run "fix the failing tests"
        jarvis run -p "build a REST API with auth"
        jarvis "add dark mode"  # shorthand (auto-routes to run)
    """
    task_text = " ".join(task)
    mode = "pipeline" if pipeline else ("single" if single else "auto")
    _run_task(task_text, mode=mode)


def _run_task(task_text: str, mode: str = "auto"):
    """Execute a task via the orchestrator."""
    ensure_jarvis_home()
    orchestrator = JarvisOrchestrator()

    # Budget pre-check
    budget = BudgetController()
    can_continue, reason = budget.enforce()
    if not can_continue:
        console.print(f"[bold red]Budget limit reached:[/] {reason}")
        sys.exit(1)

    # Trust info
    trust = TrustEngine()
    trust_status = trust.status(os.getcwd())

    # Determine execution mode
    use_pipeline = False
    if mode == "pipeline":
        use_pipeline = True
    elif mode == "auto":
        use_pipeline = orchestrator.should_use_pipeline(task_text)

    mode_label = "[magenta]pipeline[/]" if use_pipeline else "[cyan]single-agent[/]"
    console.print(f"\n[bold blue]Jarvis[/] {mode_label}: [italic]{task_text}[/]")
    console.print(
        f"Trust: T{trust_status['tier']} ({trust_status['tier_name']}) | "
        f"Budget: {budget.summary()['session']}\n"
    )

    def progress_callback(event_type: str, data: dict):
        if event_type == "task_started":
            console.print(f"[dim]Task {data['id']} started[/]")
        elif event_type in ("assistant_text", "agent_text"):
            text = data["text"]
            if len(text) > 200:
                text = text[:200] + "..."
            console.print(f"[green]{text}[/]")
        elif event_type in ("tool_use", "agent_tool"):
            tool = data.get("tool", "unknown")
            console.print(f"[dim]  -> {tool}[/]")
        elif event_type == "trust_upgrade":
            console.print(f"\n[bold yellow]{data['message']}[/]\n")
        elif event_type == "pipeline_started":
            console.print(f"[dim]Pipeline {data['task_id']} started[/]")
        elif event_type == "session_started":
            console.print(f"[dim]Session: {data['session_id'][:12]}...[/]")
        elif event_type in ("task_completed", "pipeline_completed"):
            status = data.get("status", "unknown")
            cost = data.get("cost_usd", data.get("cost", 0.0))
            turns = data.get("turns", 0)
            color = "green" if status == "completed" else "red"
            console.print(f"\n[bold {color}]Task {status}[/] | "
                          f"Cost: ${cost:.2f} | Turns: {turns}")

    if use_pipeline:
        result = _run_async(orchestrator.run_pipeline(task_text, callback=progress_callback))
    else:
        result = _run_async(orchestrator.run_task(task_text, callback=progress_callback))

    # Save session for continuity
    _run_async(orchestrator.save_session())

    if result["status"] != "completed":
        sys.exit(1)


# --- Status commands ---


@cli.command()
def status():
    """Show Jarvis status: trust, budget, active tasks."""
    ensure_jarvis_home()
    orchestrator = JarvisOrchestrator()
    _run_async(orchestrator.run_model_preflight(live_check=False))
    status_data = _run_async(orchestrator.get_status())

    # Trust panel
    trust = status_data["trust"]
    trust_table = Table(show_header=False, box=None)
    trust_table.add_row("Tier", f"T{trust['tier']} ({trust['tier_name']})")
    trust_table.add_row("Successful tasks", str(trust["successful_tasks"]))
    trust_table.add_row("Total tasks", str(trust["total_tasks"]))
    trust_table.add_row("Rollbacks", str(trust["rollbacks"]))
    trust_table.add_row("Until upgrade", str(trust["tasks_until_upgrade"]))
    console.print(Panel(trust_table, title="Trust", border_style="blue"))

    # Budget panel
    budget = status_data["budget"]
    budget_table = Table(show_header=False, box=None)
    budget_table.add_row("Session", budget["session"])
    budget_table.add_row("Daily", budget["daily"])
    budget_table.add_row("Turns", budget["turns"])
    console.print(Panel(budget_table, title="Budget", border_style="green"))

    # Preflight panel
    preflight = status_data.get("preflight", {}) or {}
    ready = bool(preflight.get("ready", False))
    errors = preflight.get("errors", []) or []
    warnings = preflight.get("warnings", []) or []
    provider = preflight.get("provider", {}) or {}
    preflight_table = Table(show_header=False, box=None)
    preflight_table.add_row("Ready", "[green]yes[/]" if ready else "[red]no[/]")
    preflight_table.add_row("Token present", "yes" if provider.get("token_present") else "no")
    preflight_table.add_row("Base URL", provider.get("base_url") or "(default)")
    preflight_table.add_row("Errors", ", ".join(errors) if errors else "-")
    preflight_table.add_row("Warnings", ", ".join(warnings) if warnings else "-")
    console.print(Panel(preflight_table, title="Preflight", border_style=("green" if ready else "red")))

    # Recent tasks
    if status_data["recent_tasks"]:
        task_table = Table(title="Recent Tasks")
        task_table.add_column("ID", style="dim")
        task_table.add_column("Description")
        task_table.add_column("Status")
        task_table.add_column("Cost")
        for t in status_data["recent_tasks"]:
            color = {"completed": "green", "failed": "red", "cancelled": "yellow", "in_progress": "blue"}.get(
                t["status"], "white"
            )
            task_table.add_row(t["id"], t["description"][:60], f"[{color}]{t['status']}[/]", t["cost"])
        console.print(task_table)
    else:
        console.print("[dim]No tasks yet. Run: jarvis \"your task here\"[/]")


@cli.command()
@click.argument("task_id", required=False)
def log(task_id):
    """View task log and output."""
    memory = MemoryStore()
    if task_id:
        task = memory.get_task(task_id)
        if task:
            console.print(Panel(
                f"[bold]{task.description}[/]\n\n"
                f"Status: {task.status}\n"
                f"Cost: ${task.cost_usd:.2f}\n"
                f"Turns: {task.turns}\n\n"
                f"Output:\n{task.result or 'No output recorded'}",
                title=f"Task {task.id}",
            ))
        else:
            console.print(f"[red]Task {task_id} not found[/]")
    else:
        tasks = memory.list_tasks(os.getcwd())
        if tasks:
            task = tasks[0]
            console.print(Panel(
                f"[bold]{task.description}[/]\n\n"
                f"Status: {task.status}\n"
                f"Result: {(task.result or 'No output')[:500]}",
                title=f"Latest: {task.id}",
            ))
        else:
            console.print("[dim]No tasks yet[/]")


@cli.command()
def tasks():
    """List all tracked tasks."""
    memory = MemoryStore()
    all_tasks = memory.list_tasks(os.getcwd())

    if not all_tasks:
        console.print("[dim]No tasks yet[/]")
        return

    table = Table(title="All Tasks")
    table.add_column("ID", style="dim")
    table.add_column("Description")
    table.add_column("Status")
    table.add_column("Cost")
    table.add_column("Turns")

    for t in all_tasks:
        color = {"completed": "green", "failed": "red", "in_progress": "blue",
                 "pending": "yellow", "paused": "dim"}.get(t.status, "white")
        table.add_row(
            t.id,
            t.description[:50],
            f"[{color}]{t.status}[/]",
            f"${t.cost_usd:.2f}",
            str(t.turns),
        )

    console.print(table)


# --- Trust management ---


@cli.group(invoke_without_command=True)
@click.pass_context
def trust(ctx):
    """Show or manage trust level."""
    if ctx.invoked_subcommand is None:
        engine = TrustEngine()
        status = engine.status(os.getcwd())
        console.print(f"\nTrust: [bold]T{status['tier']} ({status['tier_name']})[/]")
        console.print(f"Successful: {status['successful_tasks']} / {status['total_tasks']}")
        console.print(f"Rollbacks: {status['rollbacks']}")
        console.print(f"Tasks until upgrade: {status['tasks_until_upgrade']}\n")

        table = Table(title="Trust Tiers")
        table.add_column("Tier")
        table.add_column("Name")
        table.add_column("Can Do")
        table.add_column("")

        for t in TrustTier:
            marker = " <-- YOU" if t.value == status["tier"] else ""
            table.add_row(
                f"T{t.value}",
                t.name,
                {
                    0: "Read, analyze",
                    1: "Edit, test, lint",
                    2: "+ commit, install, servers, containers",
                    3: "+ push, PRs, any command",
                    4: "Everything local",
                }[t.value],
                f"[bold green]{marker}[/]",
            )

        console.print(table)


@trust.command("raise")
def trust_raise():
    """Request trust tier upgrade."""
    engine = TrustEngine()
    status = engine.status(os.getcwd())

    if status["tier"] >= 4:
        console.print("[yellow]Already at maximum trust (T4 Autonomous)[/]")
        return

    if status["tasks_until_upgrade"] > 0:
        console.print(
            f"[yellow]Need {status['tasks_until_upgrade']} more successful tasks "
            f"to auto-upgrade from T{status['tier']} to T{status['tier'] + 1}[/]"
        )
        if click.confirm("Force upgrade now?"):
            msg = engine.set_tier(os.getcwd(), status["tier"] + 1)
            console.print(f"[green]{msg}[/]")
    else:
        msg = engine.set_tier(os.getcwd(), status["tier"] + 1)
        console.print(f"[green]{msg}[/]")


@trust.command("set")
@click.argument("tier", type=int)
def trust_set(tier):
    """Manually set trust tier (0-4)."""
    if tier == 4:
        console.print(
            "[bold yellow]Warning:[/] T4 (Autonomous) gives Jarvis full local authority.\n"
            "It can run any command, modify any file, and push to git.\n"
            "Production deployments still require approval."
        )
        if not click.confirm("Continue?"):
            return

    engine = TrustEngine()
    msg = engine.set_tier(os.getcwd(), tier)
    console.print(f"[green]{msg}[/]")


# --- Budget & Config ---


@cli.command()
def budget():
    """Show budget status and spending history."""
    controller = BudgetController()
    summary = controller.summary()

    table = Table(title="Budget Status", show_header=False)
    table.add_row("Session spent", summary["session"])
    table.add_row("Daily spent", summary["daily"])
    table.add_row("Turns used", summary["turns"])

    status_color = "green" if summary["can_continue"] else "red"
    table.add_row("Can continue", f"[{status_color}]{summary['can_continue']}[/]")

    console.print(table)


@cli.command()
@click.argument("key_value", nargs=-1)
def config(key_value):
    """View or set Jarvis configuration.

    Examples:
        jarvis config                          # show all
        jarvis config budget.session=100       # set session budget to $100
        jarvis config models.executor=glm-4.7  # use GLM 4.7
    """
    cfg = JarvisConfig.load()
    if not key_value:
        console.print_json(json.dumps({
            "container": {
                "image": cfg.container.default_image,
                "cpus": cfg.container.default_cpus,
                "memory": cfg.container.default_memory,
                "template": cfg.container.default_template,
            },
            "budget": {
                "session_limit": f"${cfg.budget.max_per_session_usd}",
                "daily_limit": f"${cfg.budget.max_per_day_usd}",
                "max_turns": cfg.budget.max_turns_per_task,
            },
            "models": {
                "planner": cfg.models.planner,
                "executor": cfg.models.executor,
                "reviewer": cfg.models.reviewer,
                "quick": cfg.models.quick,
            },
            "trust_tier": cfg.trust_tier,
        }))
        return

    kv = " ".join(key_value)
    if "=" in kv:
        key, value = kv.split("=", 1)
        key = key.strip()
        value = value.strip()

        if key == "budget.session":
            cfg.budget.max_per_session_usd = float(value)
        elif key == "budget.daily":
            cfg.budget.max_per_day_usd = float(value)
        elif key == "budget.max_turns":
            cfg.budget.max_turns_per_task = int(value)
        elif key == "container.image":
            cfg.container.default_image = value
        elif key == "container.cpus":
            cfg.container.default_cpus = int(value)
        elif key == "container.memory":
            cfg.container.default_memory = value
        elif key == "container.template":
            cfg.container.default_template = value
        elif key.startswith("models."):
            model_key = key.split(".", 1)[1]
            if hasattr(cfg.models, model_key):
                setattr(cfg.models, model_key, value)
            else:
                console.print(f"[red]Unknown model key: {model_key}[/]")
                return
        else:
            console.print(f"[red]Unknown config key: {key}[/]")
            return

        cfg.save()
        console.print(f"[green]Set {key} = {value}[/]")
    else:
        console.print("[yellow]Usage: jarvis config key=value[/]")


@cli.command()
@click.argument("name", required=False)
def templates(name):
    """List container templates or show details for one."""
    if name:
        tmpl = get_template(name)
        if not tmpl:
            console.print(f"[red]Unknown template: {name}[/]")
            console.print(f"Available: {', '.join(t.name for t in list_all_templates())}")
            return
        table = Table(title=f"Template: {tmpl.display_name}", show_header=False)
        table.add_row("Name", tmpl.name)
        table.add_row("Image", tmpl.base_image)
        table.add_row("Description", tmpl.description)
        table.add_row("Setup", "\n".join(tmpl.setup_commands) or "none")
        table.add_row("Env", ", ".join(f"{k}={v}" for k, v in tmpl.env.items()) or "none")
        table.add_row("Detection", ", ".join(tmpl.detection_files) or "none")
        console.print(table)
    else:
        table = Table(title="Container Templates")
        table.add_column("Name", style="cyan")
        table.add_column("Image")
        table.add_column("Description")
        for tmpl in list_all_templates():
            table.add_row(tmpl.name, tmpl.base_image, tmpl.description)
        console.print(table)


# --- Project init ---


@cli.command()
def init():
    """Initialize Jarvis for the current project."""
    ensure_jarvis_home()
    project_path = Path(os.getcwd())
    project_name = project_path.name

    console.print(f"\n[bold blue]Jarvis[/] initializing for [bold]{project_name}[/]\n")

    # Detect project type via template
    from jarvis.container_templates import detect_template as _detect
    template = _detect(project_path)

    # Derive project info from template
    project_type = template.name.replace("-dev", "").replace("-", " ")
    container_image = template.base_image

    # Still detect package manager and test runner from files
    test_runner = "unknown"
    package_manager = "unknown"

    if (project_path / "package.json").exists():
        package_manager = "npm"
        pkg = json.loads((project_path / "package.json").read_text())
        scripts = pkg.get("scripts", {})
        if "test" in scripts:
            test_cmd = scripts["test"]
            if "vitest" in test_cmd:
                test_runner = "vitest"
            elif "jest" in test_cmd:
                test_runner = "jest"
            elif "mocha" in test_cmd:
                test_runner = "mocha"
            else:
                test_runner = "npm test"
        if (project_path / "pnpm-lock.yaml").exists():
            package_manager = "pnpm"
        elif (project_path / "yarn.lock").exists():
            package_manager = "yarn"
        elif (project_path / "bun.lockb").exists():
            package_manager = "bun"
    elif (project_path / "pyproject.toml").exists():
        package_manager = "pip"
        content = (project_path / "pyproject.toml").read_text()
        if "pytest" in content:
            test_runner = "pytest"
        if "uv" in content or (project_path / "uv.lock").exists():
            package_manager = "uv"
    elif (project_path / "Cargo.toml").exists():
        package_manager = "cargo"
        test_runner = "cargo test"
    elif (project_path / "go.mod").exists():
        package_manager = "go"
        test_runner = "go test"

    console.print(f"  Template: [cyan]{template.display_name}[/]")
    console.print(f"  Project type: [cyan]{project_type}[/]")
    console.print(f"  Package manager: [cyan]{package_manager}[/]")
    console.print(f"  Test runner: [cyan]{test_runner}[/]")
    console.print(f"  Container image: [cyan]{container_image}[/]")

    cfg = JarvisConfig.load()
    cfg.container.default_image = container_image
    cfg.save()

    trust_status = TrustEngine().status(str(project_path))
    if should_use_project_jarvis(project_path):
        jarvis_md_path = project_path / "JARVIS.md"
        legacy_path = project_path / "Jarvis.md"
        if not jarvis_md_path.exists() and legacy_path.exists():
            jarvis_md_path = legacy_path
        if not jarvis_md_path.exists():
            content = generate_jarvis_md(project_path, {
                "project_name": project_name,
                "project_type": project_type,
                "project_path": str(project_path),
                "test_runner": test_runner,
                "package_manager": package_manager,
                "container_image": container_image,
                "cpus": cfg.container.default_cpus,
                "memory": cfg.container.default_memory,
                "trust_tier": trust_status["tier"],
                "trust_tier_name": trust_status["tier_name"],
            })
            jarvis_md_path.write_text(content)
            console.print(f"\n  Created [bold]{jarvis_md_path.name}[/]")
        else:
            console.print(f"\n  [dim]{jarvis_md_path.name} already exists[/]")
    else:
        console.print("\n  [dim]Skipping project JARVIS.md for Jarvis core repo[/]")

    console.print(f"\n[bold green]Ready.[/] Trust: T{trust_status['tier']}. "
                  f"Try: jarvis \"describe this codebase\"\n")


# --- Browser/API testing ---


@cli.command()
@click.argument("url")
@click.option("--wallet", "-w", is_flag=True, help="Test with mock Solflare wallet")
@click.option("--wallet-address", default=None, help="Solana wallet address for mock")
@click.option("--api", "-a", is_flag=True, help="Test as API endpoint (curl)")
@click.option("--method", "-m", default="GET", help="HTTP method for API test")
def test(url, wallet, wallet_address, api, method):
    """Quick browser or API test via Apple Container.

    Examples:
        jarvis test http://localhost:3000           # navigate + screenshot
        jarvis test http://localhost:3000 -w        # test with mock Solflare wallet
        jarvis test http://localhost:8000/api -a    # API endpoint test
    """
    ensure_jarvis_home()

    if wallet:
        addr = wallet_address or "11111111111111111111111111111111"
        task = (
            f"Test this Solana dApp with a mock Solflare wallet: {url}\n"
            f"Use browser_wallet_test with wallet address {addr}.\n"
            f"First start a container, install Playwright with browser_setup, "
            f"then run browser_wallet_test. Report what the page shows and any console errors."
        )
    elif api:
        task = (
            f"Test this API endpoint from inside an Apple Container:\n"
            f"{method} {url}\n"
            f"Use browser_api_test. Report status code and response body."
        )
    else:
        task = (
            f"Test this web page in a headless browser: {url}\n"
            f"Use browser_setup to install Playwright in a container, then "
            f"browser_navigate to load the page. Report: page title, console errors, "
            f"network errors, and save a screenshot."
        )

    _run_task(task, mode="single")


# --- Autonomous build ---


@cli.command()
@click.argument("description", nargs=-1, required=False)
@click.option("--resume", "-r", is_flag=True, help="Resume from saved state")
def build(description, resume):
    """Autonomous build loop: init -> implement -> test -> commit -> repeat.

    Examples:
        jarvis build "task management API"
        jarvis build --resume
    """
    ensure_jarvis_home()
    desc = " ".join(description) if description else ""
    if not desc and not resume:
        console.print("[red]Provide a description or use --resume[/]")
        sys.exit(1)

    orchestrator = JarvisOrchestrator()

    budget = BudgetController()
    can_continue, reason = budget.enforce()
    if not can_continue:
        console.print(f"[bold red]Budget limit reached:[/] {reason}")
        sys.exit(1)

    trust_status = TrustEngine().status(os.getcwd())
    mode_label = "[magenta]autonomous build[/]"
    if resume:
        mode_label += " [dim](resuming)[/]"
    console.print(f"\n[bold blue]Jarvis[/] {mode_label}: [italic]{desc or 'resuming...'}[/]")
    console.print(
        f"Trust: T{trust_status['tier']} ({trust_status['tier_name']}) | "
        f"Budget: {budget.summary()['session']}\n"
    )

    def progress_callback(event_type: str, data: dict):
        if event_type == "state_change":
            console.print(f"[yellow]State: {data.get('to', '?')}[/]")
        elif event_type == "feature_start":
            console.print(f"\n[bold cyan]Feature:[/] {data.get('description', '?')}")
        elif event_type == "feature_complete":
            console.print(f"[bold green]Feature done:[/] {data.get('id', '?')}")
        elif event_type in ("assistant_text", "agent_text"):
            text = data.get("text", "")
            if len(text) > 200:
                text = text[:200] + "..."
            console.print(f"[green]{text}[/]")
        elif event_type in ("tool_use", "agent_tool"):
            console.print(f"[dim]  -> {data.get('tool', '?')}[/]")
        elif event_type == "task_completed":
            status = data.get("status", "unknown")
            cost = data.get("cost_usd", 0.0)
            color = "green" if status == "completed" else "red"
            console.print(f"[{color}]Task {status}[/] (${cost:.2f})")

    result = _run_async(orchestrator.run_autonomous(
        desc or "resume build",
        callback=progress_callback,
        resume=resume,
    ))

    _run_async(orchestrator.save_session())

    final_state = result.get("state", "unknown")
    console.print(f"\n[bold]Build finished:[/] {final_state}")
    if result.get("status") == "error":
        console.print(f"[red]Error: {result.get('error', 'unknown')}[/]")
        sys.exit(1)


@cli.command()
def features():
    """Show feature list progress."""
    from jarvis.feature_manager import FeatureManager

    fm = FeatureManager(os.getcwd())
    try:
        fm.load()
    except FileNotFoundError:
        console.print("[dim]No feature list yet. Run: jarvis build \"your project\"[/]")
        return

    progress = fm.progress()
    console.print(
        f"\n[bold]Features:[/] {progress['tested']}/{progress['total']} tested, "
        f"{progress['implemented']} implemented, "
        f"{progress['in_progress']} in progress, "
        f"{progress['blocked']} blocked\n"
    )

    table = Table(title="Feature List")
    table.add_column("ID", style="dim")
    table.add_column("Description")
    table.add_column("Phase")
    table.add_column("Status")
    table.add_column("Priority")
    table.add_column("Cost")

    status_colors = {
        "pending": "white",
        "in_progress": "blue",
        "implemented": "yellow",
        "tested": "green",
        "blocked": "red",
    }

    for f in fm._features:
        color = status_colors.get(f.status, "white")
        table.add_row(
            f.id,
            f.description[:50],
            f.phase,
            f"[{color}]{f.status}[/]",
            str(f.priority),
            f"${f.cost_usd:.2f}",
        )

    console.print(table)


@cli.command()
@click.option("--limit", "-n", default=20, help="Number of events to show")
@click.option("--today", "-t", is_flag=True, help="Show today's events only")
@click.option("--type", "-T", "event_type", default=None, help="Filter by event type")
def timeline(limit, today, event_type):
    """Show recent timeline events.

    Examples:
        jarvis timeline                    # last 20 events
        jarvis timeline --today            # today only
        jarvis timeline -n 50 -T error     # last 50 errors
    """
    memory = MemoryStore()

    date_range = None
    if today:
        now = datetime.datetime.now()
        day_start = datetime.datetime(now.year, now.month, now.day).timestamp()
        date_range = (day_start, day_start + 86400)

    events = memory.get_timeline(
        limit=limit,
        event_type=event_type,
        date_range=date_range,
    )

    if not events:
        console.print("[dim]No timeline events yet.[/]")
        return

    if today:
        summary = memory.get_day_summary()
        console.print(
            f"\n[bold]Today ({summary['date']}):[/] "
            f"{summary['total_events']} events, ${summary['total_cost']:.2f} spent\n"
        )

    table = Table(title="Timeline")
    table.add_column("Time", style="dim")
    table.add_column("Type", style="cyan")
    table.add_column("Summary")
    table.add_column("Task", style="dim")
    table.add_column("Cost", style="dim")

    type_colors = {
        "tool_use": "dim",
        "state_change": "yellow",
        "feature_start": "cyan",
        "feature_complete": "green",
        "error": "red",
        "approval_needed": "bold yellow",
        "task_start": "blue",
        "task_complete": "green",
    }

    for e in events:
        ts = datetime.datetime.fromtimestamp(e["timestamp"]).strftime("%H:%M:%S")
        etype = e["event_type"]
        color = type_colors.get(etype, "white")
        cost_str = f"${e['cost_usd']:.2f}" if e["cost_usd"] else ""
        table.add_row(
            ts,
            f"[{color}]{etype}[/]",
            e["summary"][:60],
            e.get("task_id") or "",
            cost_str,
        )

    console.print(table)


# --- Daemon management ---


@cli.command()
@click.option("--install", is_flag=True, help="Install as launchd service")
@click.option("--uninstall", is_flag=True, help="Remove launchd service")
def daemon(install, uninstall):
    """Run Jarvis daemon (foreground), or manage launchd service.

    Examples:
        jarvis daemon              # run in foreground
        jarvis daemon --install    # install as launchd service
        jarvis daemon --uninstall  # remove launchd service
    """
    plist_name = "com.jarvis.daemon"
    plist_dest = Path.home() / "Library" / "LaunchAgents" / f"{plist_name}.plist"
    plist_source = Path(__file__).parent.parent.parent / f"{plist_name}.plist"

    if install:
        import shutil
        if not plist_source.exists():
            console.print(f"[red]Plist not found: {plist_source}[/]")
            sys.exit(1)
        plist_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(plist_source, plist_dest)
        os.system(f"launchctl load {plist_dest}")
        console.print(f"[green]Installed and loaded {plist_name}[/]")
        return

    if uninstall:
        if plist_dest.exists():
            os.system(f"launchctl unload {plist_dest}")
            plist_dest.unlink()
            console.print(f"[green]Unloaded and removed {plist_name}[/]")
        else:
            console.print(f"[yellow]Not installed: {plist_dest}[/]")
        return

    # Foreground mode
    console.print("[bold blue]Jarvis daemon[/] starting in foreground...\n")
    from jarvis.daemon import JarvisDaemon
    d = JarvisDaemon()
    _run_async(d.start())


def main():
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()
