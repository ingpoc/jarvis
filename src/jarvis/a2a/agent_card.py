"""A2A Agent Card: Discovery endpoint response."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentCapability:
    """A capability offered by the agent."""
    name: str
    description: str = ""


@dataclass
class AgentEndpoint:
    """An API endpoint exposed by the agent."""
    path: str
    method: str = "POST"
    description: str = ""


def build_agent_card(
    name: str = "Jarvis",
    description: str = "Autonomous Mac-native development partner powered by OpenCode runtime",
    version: str = "0.1.0",
    capabilities: list[str] | None = None,
    base_url: str = "",
    port: int = 9848,
) -> dict[str, Any]:
    """Build an A2A Agent Card for discovery.

    Returns a dict matching the A2A Agent Card specification.

    Args:
        name: Agent name
        description: Agent description
        version: Agent version
        capabilities: List of capabilities (text, streaming, artifacts)
        base_url: Base URL for endpoints (e.g., "http://localhost:9848")
        port: Port number, used to construct base_url if not provided
    """
    if capabilities is None:
        capabilities = ["text", "streaming", "artifacts"]

    # Use base_url if provided, otherwise construct from port
    if not base_url:
        base_url = f"http://localhost:{port}"

    return {
        "name": name,
        "description": description,
        "version": version,
        "capabilities": capabilities,
        "url": base_url,
        "endpoints": {
            "message_send": {
                "url": f"{base_url}/",
                "method": "POST",
                "description": "Send a message to the agent (JSON-RPC 2.0)",
            },
            "tasks_get": {
                "url": f"{base_url}/",
                "method": "POST",
                "description": "Get task status (JSON-RPC 2.0)",
            },
            "tasks_cancel": {
                "url": f"{base_url}/",
                "method": "POST",
                "description": "Cancel a running task (JSON-RPC 2.0)",
            },
            "stream": {
                "url": f"{base_url}/stream/{{task_id}}",
                "method": "GET",
                "description": "SSE stream for task updates",
            },
        },
        "authentication": {
            "type": "bearer",
            "description": "Bearer token from ~/.jarvis/system/jarvis_config/a2a_token",
        },
        "metadata": {
            "protocol": "a2a",
            "protocol_version": "1.0",
        },
    }


def agent_card_json() -> str:
    """Return Agent Card as JSON string."""
    import json
    return json.dumps(build_agent_card(), indent=2)
