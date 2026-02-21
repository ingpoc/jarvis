import json
from pathlib import Path

from jarvis.context_files import _sync_runtime_mcp_from_opencode


def test_sync_runtime_mcp_from_opencode_maps_enabled_servers(tmp_path: Path) -> None:
    opencode_cfg = tmp_path / "opencode.json"
    runtime_mcp = tmp_path / ".mcp.json"
    opencode_cfg.write_text(
        json.dumps(
            {
                "mcp": {
                    "token-efficient": {
                        "type": "local",
                        "enabled": True,
                        "command": ["node", "/tmp/token-efficient/index.js"],
                    },
                    "context7": {
                        "type": "local",
                        "enabled": False,
                        "command": ["npx", "-y", "@upstash/context7-mcp"],
                    },
                    "deepwiki": {
                        "type": "remote",
                        "enabled": True,
                        "url": "https://mcp.deepwiki.com/mcp",
                        "headers": {"Authorization": "Bearer token"},
                    },
                    "context-graph": {
                        "type": "local",
                        "enabled": True,
                        "command": [
                            "uv",
                            "--directory",
                            "/tmp/context-graph-mcp",
                            "run",
                            "python",
                            "server.py",
                        ],
                        "environment": {"VOYAGE_API_KEY": "{env:VOYAGE_API_KEY}"},
                    },
                }
            }
        )
    )

    assert _sync_runtime_mcp_from_opencode(opencode_cfg, runtime_mcp) is True

    data = json.loads(runtime_mcp.read_text())
    servers = data["mcpServers"]
    assert "context7" not in servers
    assert servers["token-efficient"]["command"] == "node"
    assert servers["token-efficient"]["args"] == ["/tmp/token-efficient/index.js"]
    assert servers["deepwiki"]["url"] == "https://mcp.deepwiki.com/mcp"
    assert servers["deepwiki"]["headers"]["Authorization"] == "Bearer token"
    assert servers["context-graph"]["command"] == "uv"
    assert servers["context-graph"]["args"] == [
        "--directory",
        "/tmp/context-graph-mcp",
        "run",
        "python",
        "server.py",
    ]
    assert servers["context-graph"]["env"]["VOYAGE_API_KEY"] == "{env:VOYAGE_API_KEY}"


def test_sync_runtime_mcp_from_opencode_applies_dynamic_overlay(tmp_path: Path) -> None:
    opencode_cfg = tmp_path / "opencode.json"
    runtime_mcp = tmp_path / ".mcp.json"
    overlay = tmp_path / ".opencode" / ".mcp.json"
    overlay.parent.mkdir(parents=True, exist_ok=True)

    opencode_cfg.write_text(
        json.dumps(
            {
                "mcp": {
                    "token-efficient": {
                        "type": "local",
                        "enabled": True,
                        "command": ["node", "/base/token-efficient.js"],
                    },
                    "deepwiki": {
                        "type": "remote",
                        "enabled": True,
                        "url": "https://mcp.deepwiki.com/mcp",
                    },
                }
            }
        )
    )
    overlay.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "token-efficient": {"disabled": True},
                    "context7": {
                        "command": "npx",
                        "args": ["-y", "@upstash/context7-mcp"],
                    },
                }
            }
        )
    )

    assert _sync_runtime_mcp_from_opencode(
        opencode_cfg, runtime_mcp, dynamic_overlay_path=overlay
    )

    data = json.loads(runtime_mcp.read_text())
    servers = data["mcpServers"]
    assert "token-efficient" not in servers
    assert "deepwiki" in servers
    assert servers["context7"]["command"] == "npx"
    assert servers["context7"]["args"] == ["-y", "@upstash/context7-mcp"]
