"""Apple Container MCP tools for Jarvis sandbox management.

Wraps the `container` CLI to provide VM-per-task isolation.
Each task gets its own lightweight Linux VM with dedicated networking.
"""

import asyncio
import json
import os
import shutil
import uuid

from claude_agent_sdk import create_sdk_mcp_server, tool

from jarvis.config import JarvisConfig
from jarvis.container_templates import detect_template, get_template, build_setup_script

KEEPALIVE_CMD = "trap : TERM INT; while true; do sleep 86400; done"


async def _run_container_cmd(*args: str, timeout: int = 60) -> dict:
    """Execute a container CLI command and return parsed output."""
    container_bin = (
        os.environ.get("CONTAINER_BIN")
        or shutil.which("container")
        or next(
            (
                p for p in (
                    "/opt/homebrew/bin/container",
                    "/usr/local/bin/container",
                    "/usr/bin/container",
                )
                if os.path.exists(p)
            ),
            None,
        )
    )
    if not container_bin:
        raise FileNotFoundError(
            "container CLI not found. Checked CONTAINER_BIN, PATH, "
            "/opt/homebrew/bin/container, /usr/local/bin/container, /usr/bin/container"
        )

    cmd = [container_bin, *args]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    return {
        "exit_code": proc.returncode,
        "stdout": stdout.decode().strip(),
        "stderr": stderr.decode().strip(),
    }


def _normalize_string_list(value) -> list[str]:
    """Normalize list-like tool inputs.

    Accepts:
    - list[str]
    - comma-separated string
    - empty string / None => []
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        return [part.strip() for part in stripped.split(",") if part.strip()]
    raise ValueError(f"Expected list or string, got {type(value).__name__}")


async def _get_container_status(container_id: str) -> str:
    """Return normalized status for a container ID."""
    result = await _run_container_cmd("list", "--all", "--format", "json", timeout=15)
    if result["exit_code"] != 0 or not result["stdout"]:
        return "unknown"
    try:
        containers = json.loads(result["stdout"])
    except json.JSONDecodeError:
        return "unknown"

    for container in containers:
        config = container.get("configuration", {}) or {}
        if config.get("id") == container_id:
            status = container.get("status", "unknown")
            return status.lower() if isinstance(status, str) else "unknown"
    return "not_found"


async def _collect_container_diagnostics(container_id: str) -> dict:
    """Collect status + recent logs for better error payloads."""
    status = await _get_container_status(container_id)
    logs_result = await _run_container_cmd("logs", "-n", "80", container_id, timeout=15)
    logs_text = logs_result["stdout"] or logs_result["stderr"]
    return {"container_status": status, "logs_tail": logs_text[:4000]}


# --- MCP Tools ---


@tool(
    "container_run",
    "Create and start a new Apple Container VM for a task. Returns container ID.",
    {
        "image": str,
        "name": str,
        "volumes": list,  # ["host_path:container_path", ...]
        "ports": list,  # ["host:container", ...]
        "env": list,  # ["KEY=VALUE", ...]
        "cpus": int,
        "memory": str,
        "ssh_forward": bool,
        "keep_alive": bool,
        "command": str,
        "template": str,
    },
)
async def container_run(args: dict) -> dict:
    """Start a new container VM."""
    config = JarvisConfig.load()
    image = args.get("image", config.container.default_image)
    name = args.get("name", f"jarvis-{uuid.uuid4().hex[:8]}")
    cpus = args.get("cpus", config.container.default_cpus)
    memory = args.get("memory", config.container.default_memory)

    try:
        volumes = _normalize_string_list(args.get("volumes", []))
        ports = _normalize_string_list(args.get("ports", []))
        env_vars = _normalize_string_list(args.get("env", []))
    except ValueError as e:
        return {"content": [{"type": "text", "text": json.dumps({
            "status": "error",
            "error": f"Invalid container_run input: {e}",
        })}]}

    cmd_args = [
        "run", "-d",
        "--name", name,
        "--cpus", str(cpus),
        "--memory", memory,
        "--network", config.container.network,
    ]

    for vol in volumes:
        cmd_args.extend(["--volume", vol])

    for port in ports:
        cmd_args.extend(["--publish", port])

    for env_var in env_vars:
        cmd_args.extend(["--env", env_var])

    if args.get("ssh_forward", False):
        cmd_args.append("--ssh")

    cmd_args.append(image)
    explicit_command = str(args.get("command", "")).strip()
    keep_alive = bool(args.get("keep_alive", True))
    if explicit_command:
        cmd_args.extend(["sh", "-lc", explicit_command])
    elif keep_alive:
        # Keep containers alive for interactive development workflows.
        cmd_args.extend(["sh", "-lc", KEEPALIVE_CMD])

    result = await _run_container_cmd(*cmd_args, timeout=120)

    if result["exit_code"] == 0:
        status = await _get_container_status(name)
        if status not in ("running", "starting"):
            diagnostics = await _collect_container_diagnostics(name)
            return {"content": [{"type": "text", "text": json.dumps({
                "status": "error",
                "container_id": name,
                "error": "Container exited immediately after start",
                "start_output": result["stdout"] or result["stderr"],
                **diagnostics,
            })}]}

        # Resolve and apply container template
        template_name = args.get("template", "auto")
        template = None
        # Empty template means "no template"; omitted means "auto".
        if template_name == "":
            template = None
        elif template_name and template_name != "auto":
            template = get_template(template_name)
        else:
            import os
            template = detect_template(os.getcwd())

        setup_info = None
        if template:
            setup_script = build_setup_script(template)
            setup_result = await _run_container_cmd(
                "exec", name, "sh", "-c", setup_script,
                timeout=300,
            )
            setup_info = {
                "template": template.name,
                "setup_exit_code": setup_result["exit_code"],
            }
            if setup_result["exit_code"] != 0:
                diagnostics = await _collect_container_diagnostics(name)
                return {"content": [{"type": "text", "text": json.dumps({
                    "status": "error",
                    "container_id": name,
                    "error": "Template setup failed",
                    "template": template.name,
                    "setup_exit_code": setup_result["exit_code"],
                    "setup_stdout": setup_result["stdout"][:2000],
                    "setup_stderr": setup_result["stderr"][:2000],
                    **diagnostics,
                })}]}

        status = await _get_container_status(name)
        if status != "running":
            diagnostics = await _collect_container_diagnostics(name)
            return {"content": [{"type": "text", "text": json.dumps({
                "status": "error",
                "container_id": name,
                "error": "Container not running after initialization",
                "template": setup_info["template"] if setup_info else None,
                "setup_exit_code": setup_info["setup_exit_code"] if setup_info else None,
                **diagnostics,
            })}]}

        response = {
            "status": "running",
            "container_id": name,
            "image": image,
            "message": result["stdout"],
            "keep_alive": keep_alive and not explicit_command,
        }
        if setup_info:
            response["template"] = setup_info["template"]
            response["setup_exit_code"] = setup_info["setup_exit_code"]

        return {"content": [{"type": "text", "text": json.dumps(response)}]}

    return {"content": [{"type": "text", "text": json.dumps({
        "status": "error",
        "error": result["stderr"] or result["stdout"],
    })}]}


@tool(
    "container_exec",
    "Execute a command inside a running Apple Container VM. Use for installing packages, running builds, tests, servers.",
    {
        "container_id": str,
        "command": str,
        "workdir": str,
        "env": list,
        "timeout": int,
    },
)
async def container_exec(args: dict) -> dict:
    """Execute command in container."""
    container_id = args["container_id"]
    command = args["command"]
    timeout = args.get("timeout", 300)
    status = await _get_container_status(container_id)
    if status != "running":
        diagnostics = await _collect_container_diagnostics(container_id)
        return {"content": [{"type": "text", "text": json.dumps({
            "exit_code": 125,
            "stdout": "",
            "stderr": f"container is not running (status={status})",
            **diagnostics,
        })}]}

    cmd_args = ["exec"]

    workdir = args.get("workdir")
    if workdir:
        cmd_args.extend(["--workdir", workdir])

    for env_var in args.get("env", []):
        cmd_args.extend(["--env", env_var])

    cmd_args.extend([container_id, "sh", "-c", command])

    result = await _run_container_cmd(*cmd_args, timeout=timeout)

    return {"content": [{"type": "text", "text": json.dumps({
        "exit_code": result["exit_code"],
        "stdout": result["stdout"][:10000],  # Cap output to prevent context bloat
        "stderr": result["stderr"][:5000],
    })}]}


@tool(
    "container_stop",
    "Stop and optionally remove a container VM. Use after task completion.",
    {"container_id": str, "remove": bool, "force": bool},
)
async def container_stop(args: dict) -> dict:
    """Stop a container."""
    container_id = args["container_id"]
    force = args.get("force", False)

    # Stop
    stop_args = ["stop"]
    if force:
        stop_args = ["kill"]
    stop_args.append(container_id)
    result = await _run_container_cmd(*stop_args)

    # Remove if requested
    if args.get("remove", True):
        await _run_container_cmd("delete", container_id)

    return {"content": [{"type": "text", "text": json.dumps({
        "status": "stopped",
        "container_id": container_id,
        "removed": args.get("remove", True),
    })}]}


@tool(
    "container_list",
    "List all running Jarvis containers with status, image, and network info.",
    {"all": bool},
)
async def container_list(args: dict) -> dict:
    """List containers."""
    cmd_args = ["list", "--format", "json"]
    if args.get("all", False):
        cmd_args.append("--all")

    result = await _run_container_cmd(*cmd_args)

    if result["exit_code"] == 0 and result["stdout"]:
        try:
            containers = json.loads(result["stdout"])
            # Filter to jarvis containers
            jarvis_containers = [
                c for c in containers
                if c.get("configuration", {}).get("id", "").startswith("jarvis-")
            ]
            return {"content": [{"type": "text", "text": json.dumps(jarvis_containers)}]}
        except json.JSONDecodeError:
            pass

    return {"content": [{"type": "text", "text": result["stdout"] or "No containers found"}]}


@tool(
    "container_logs",
    "Get logs from a container. Useful for debugging failed commands or server output.",
    {"container_id": str, "lines": int, "boot": bool},
)
async def container_logs(args: dict) -> dict:
    """Get container logs."""
    container_id = args["container_id"]
    cmd_args = ["logs"]

    lines = args.get("lines")
    if lines:
        cmd_args.extend(["-n", str(lines)])

    if args.get("boot", False):
        cmd_args.append("--boot")

    cmd_args.append(container_id)

    result = await _run_container_cmd(*cmd_args)

    output = result["stdout"][:10000]  # Cap to prevent context bloat
    return {"content": [{"type": "text", "text": output}]}


@tool(
    "container_inspect",
    "Get detailed info about a container: status, networks, mounts, resources.",
    {"container_id": str},
)
async def container_inspect(args: dict) -> dict:
    """Inspect container details."""
    result = await _run_container_cmd("inspect", args["container_id"])

    if result["exit_code"] == 0:
        return {"content": [{"type": "text", "text": result["stdout"][:5000]}]}

    return {"content": [{"type": "text", "text": f"Error: {result['stderr']}"}]}


@tool(
    "container_stats",
    "Get resource usage stats (CPU, memory, network, disk) for containers.",
    {"container_id": str},
)
async def container_stats(args: dict) -> dict:
    """Get container resource stats."""
    cmd_args = ["stats", "--no-stream", "--format", "json"]
    container_id = args.get("container_id")
    if container_id:
        cmd_args.append(container_id)

    result = await _run_container_cmd(*cmd_args, timeout=10)

    return {"content": [{"type": "text", "text": result["stdout"] or "No stats available"}]}


# --- Server factory ---


ALL_CONTAINER_TOOLS = [
    container_run,
    container_exec,
    container_stop,
    container_list,
    container_logs,
    container_inspect,
    container_stats,
]


def create_container_mcp_server():
    """Create the Apple Container MCP server with all tools."""
    return create_sdk_mcp_server(
        name="jarvis-container",
        version="0.1.0",
        tools=ALL_CONTAINER_TOOLS,
    )
