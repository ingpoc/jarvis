"""Apple Container MCP tools for Jarvis sandbox management.

Wraps the `container` CLI to provide VM-per-task isolation.
Each task gets its own lightweight Linux VM with dedicated networking.
"""

import asyncio
import json
import uuid

from claude_agent_sdk import create_sdk_mcp_server, tool

from jarvis.config import JarvisConfig
from jarvis.container_templates import detect_template, get_template, build_setup_script


async def _run_container_cmd(*args: str, timeout: int = 60) -> dict:
    """Execute a container CLI command and return parsed output."""
    cmd = ["container", *args]
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

    cmd_args = [
        "run", "-d",
        "--name", name,
        "--cpus", str(cpus),
        "--memory", memory,
        "--network", config.container.network,
    ]

    for vol in args.get("volumes", []):
        cmd_args.extend(["--volume", vol])

    for port in args.get("ports", []):
        cmd_args.extend(["--publish", port])

    for env_var in args.get("env", []):
        cmd_args.extend(["--env", env_var])

    if args.get("ssh_forward", False):
        cmd_args.append("--ssh")

    cmd_args.append(image)

    result = await _run_container_cmd(*cmd_args, timeout=120)

    if result["exit_code"] == 0:
        # Resolve and apply container template
        template_name = args.get("template", "auto")
        template = None
        if template_name and template_name != "auto":
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

        response = {
            "status": "running",
            "container_id": name,
            "image": image,
            "message": result["stdout"],
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
