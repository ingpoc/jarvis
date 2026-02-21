"""Compatibility helpers for legacy MCP-tool wiring.

The runtime no longer depends on Claude Agent SDK, but several internal tool
modules still use `tool(...)` decorators and `create_sdk_mcp_server(...)`
factory calls. This module provides small, dependency-free replacements.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class SimpleMCPServer:
    """Minimal MCP server descriptor used by Jarvis runtime."""

    name: str
    version: str
    tools: list[Callable[..., Any]]


def tool(name: str, description: str, input_schema: dict[str, Any] | None = None):
    """Attach tool metadata to a callable and return it unchanged."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, "_tool_name", name)
        setattr(func, "_tool_description", description)
        setattr(func, "_tool_input_schema", input_schema or {})
        return func

    return decorator


def create_sdk_mcp_server(name: str, version: str, tools: list[Callable[..., Any]]) -> SimpleMCPServer:
    """Return a minimal MCP server descriptor for capability inventory."""
    return SimpleMCPServer(name=name, version=version, tools=tools)

