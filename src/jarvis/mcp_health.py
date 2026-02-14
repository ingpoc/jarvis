"""MCP server health validation.

Performs pre-session health checks on all configured MCP servers to ensure
they're responsive before starting agent sessions.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def ping_mcp_server(server_name: str, server_config: dict, timeout: float = 2.0) -> dict[str, Any]:
    """Ping an MCP server to check if it's responsive.

    For MCP server objects with a callable interface, attempts to call list_tools()
    within the timeout. For servers with a command config, verifies the command exists.

    Args:
        server_name: Name of the MCP server
        server_config: Server configuration dict or MCP server object
        timeout: Timeout in seconds (default 2.0)

    Returns:
        dict with status, response_time, error
    """
    import time
    start_time = time.time()

    try:
        # If the server object has a list_tools method, call it as a real health check
        if hasattr(server_config, "list_tools"):
            try:
                await asyncio.wait_for(
                    _check_server_tools(server_config),
                    timeout=timeout,
                )
                return {
                    "status": "healthy",
                    "server": server_name,
                    "response_time_ms": (time.time() - start_time) * 1000,
                    "error": None,
                }
            except asyncio.TimeoutError:
                return {
                    "status": "unhealthy",
                    "server": server_name,
                    "response_time_ms": timeout * 1000,
                    "error": f"Health check timed out after {timeout}s",
                }

        # For command-based servers, verify the command binary exists
        if isinstance(server_config, dict) and "command" in server_config:
            import shutil
            cmd = server_config["command"]
            cmd_name = cmd.split()[0] if isinstance(cmd, str) else cmd[0]
            if shutil.which(cmd_name):
                return {
                    "status": "healthy",
                    "server": server_name,
                    "response_time_ms": (time.time() - start_time) * 1000,
                    "error": None,
                }
            else:
                return {
                    "status": "unhealthy",
                    "server": server_name,
                    "response_time_ms": (time.time() - start_time) * 1000,
                    "error": f"Command not found: {cmd_name}",
                }

        return {
            "status": "unknown",
            "server": server_name,
            "response_time_ms": (time.time() - start_time) * 1000,
            "error": "Unrecognized server config type",
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "server": server_name,
            "response_time_ms": (time.time() - start_time) * 1000,
            "error": str(e),
        }


async def _check_server_tools(server) -> None:
    """Attempt to call list_tools() on an MCP server object as a liveness check."""
    if asyncio.iscoroutinefunction(getattr(server, "list_tools", None)):
        await server.list_tools()
    elif callable(getattr(server, "list_tools", None)):
        server.list_tools()
    else:
        # Server exists but has no list_tools — consider it alive
        pass


async def health_check_all_servers(mcp_servers: dict[str, Any], timeout: float = 2.0) -> dict[str, Any]:
    """Check health of all configured MCP servers.

    Args:
        mcp_servers: Dict of server_name -> server_config
        timeout: Timeout per server in seconds

    Returns:
        dict with overall status and per-server results
    """
    if not mcp_servers:
        return {
            "overall_status": "no_servers",
            "healthy_count": 0,
            "unhealthy_count": 0,
            "servers": {},
        }

    # Run health checks in parallel
    tasks = []
    server_names = []
    for name, config in mcp_servers.items():
        tasks.append(ping_mcp_server(name, config, timeout))
        server_names.append(name)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Aggregate results
    server_results = {}
    healthy_count = 0
    unhealthy_count = 0

    for name, result in zip(server_names, results):
        if isinstance(result, Exception):
            result = {
                "status": "error",
                "server": name,
                "response_time_ms": 0,
                "error": str(result),
            }

        server_results[name] = result
        if result["status"] == "healthy":
            healthy_count += 1
        else:
            unhealthy_count += 1

    overall_status = "healthy" if unhealthy_count == 0 else "degraded"

    return {
        "overall_status": overall_status,
        "healthy_count": healthy_count,
        "unhealthy_count": unhealthy_count,
        "total_count": len(server_names),
        "servers": server_results,
    }


def get_quarantined_servers(health_results: dict[str, Any]) -> list[str]:
    """Get list of unhealthy servers that should be quarantined.

    Args:
        health_results: Results from health_check_all_servers

    Returns:
        list of server names to exclude from session
    """
    quarantined = []
    for name, result in health_results.get("servers", {}).items():
        if result["status"] in ("unhealthy", "error"):
            quarantined.append(name)
            logger.warning(f"Quarantining MCP server '{name}': {result.get('error', 'unhealthy')}")

    return quarantined


async def notify_health_failures(health_results: dict[str, Any]) -> None:
    """Send notifications about failed health checks.

    Args:
        health_results: Results from health_check_all_servers
    """
    unhealthy = []
    for name, result in health_results.get("servers", {}).items():
        if result["status"] in ("unhealthy", "error"):
            unhealthy.append(f"- {name}: {result.get('error', 'timeout')}")

    if not unhealthy:
        return

    # Always log failures
    for line in unhealthy:
        logger.warning(f"MCP health failure: {line}")

    # Try Slack notification via the public accessor
    try:
        from jarvis.notifications import get_slack_bot
        slack_bot = get_slack_bot()
        if slack_bot:
            message = "MCP Server Health Check Failed:\n" + "\n".join(unhealthy)
            await slack_bot.post_message(message)
    except (ImportError, AttributeError) as e:
        logger.debug(f"Slack notification unavailable: {e}")
    except Exception as e:
        logger.error(f"Failed to send health check notification: {e}")


def filter_healthy_servers(mcp_servers: dict[str, Any], health_results: dict[str, Any]) -> dict[str, Any]:
    """Filter out unhealthy servers from MCP server config.

    Args:
        mcp_servers: Original MCP server config dict
        health_results: Results from health_check_all_servers

    Returns:
        Filtered dict with only healthy servers
    """
    quarantined = get_quarantined_servers(health_results)
    return {
        name: config
        for name, config in mcp_servers.items()
        if name not in quarantined
    }
