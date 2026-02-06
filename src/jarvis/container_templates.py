"""Container template library for Jarvis.

Provides pre-configured container environments for common project types.
Templates define base images, setup commands, and environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ContainerTemplate:
    """Pre-configured container environment."""

    name: str
    display_name: str
    base_image: str
    description: str
    setup_commands: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    detection_files: list[str] = field(default_factory=list)


# --- Template Definitions ---

TEMPLATES: dict[str, ContainerTemplate] = {}


def _register(t: ContainerTemplate) -> ContainerTemplate:
    TEMPLATES[t.name] = t
    return t


_register(ContainerTemplate(
    name="base",
    display_name="Base (Ubuntu)",
    base_image="ubuntu:latest",
    description="Minimal Ubuntu environment with build essentials",
    setup_commands=[
        "apt-get update -qq",
        "apt-get install -y -qq build-essential curl git wget unzip",
    ],
    env={"DEBIAN_FRONTEND": "noninteractive"},
    detection_files=[],
))

_register(ContainerTemplate(
    name="node-dev",
    display_name="Node.js Development",
    base_image="node:22",
    description="Node.js 22 with npm/pnpm/yarn, TypeScript support",
    setup_commands=[
        "corepack enable",
        "npm install -g typescript tsx",
    ],
    env={"NODE_ENV": "development"},
    detection_files=["package.json", "tsconfig.json", ".nvmrc", ".node-version"],
))

_register(ContainerTemplate(
    name="python-dev",
    display_name="Python Development",
    base_image="python:3.12",
    description="Python 3.12 with pip/uv, virtual environment support",
    setup_commands=[
        "pip install --quiet uv",
        "uv pip install --system pytest ruff mypy",
    ],
    env={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"},
    detection_files=["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"],
))

_register(ContainerTemplate(
    name="fullstack",
    display_name="Full-Stack (Node + Python)",
    base_image="ubuntu:latest",
    description="Combined Node.js and Python environment for full-stack projects",
    setup_commands=[
        "apt-get update -qq",
        "apt-get install -y -qq build-essential curl git wget unzip",
        "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
        "apt-get install -y -qq nodejs",
        "corepack enable",
        "apt-get install -y -qq python3 python3-pip python3-venv",
        "pip3 install --quiet uv",
    ],
    env={
        "DEBIAN_FRONTEND": "noninteractive",
        "NODE_ENV": "development",
        "PYTHONDONTWRITEBYTECODE": "1",
    },
    detection_files=[],  # Detected by combo: package.json + pyproject.toml
))

_register(ContainerTemplate(
    name="rust-dev",
    display_name="Rust Development",
    base_image="rust:latest",
    description="Rust with cargo, clippy, rustfmt",
    setup_commands=[
        "rustup component add clippy rustfmt",
        "cargo install cargo-watch",
    ],
    env={"CARGO_TERM_COLOR": "always"},
    detection_files=["Cargo.toml", "Cargo.lock"],
))


def detect_template(project_path: str | Path) -> ContainerTemplate:
    """Auto-detect the best container template for a project.

    Uses score-based detection from marker files.
    Returns the template with the highest score, defaulting to 'base'.
    """
    path = Path(project_path)
    scores: dict[str, int] = {name: 0 for name in TEMPLATES}

    for name, template in TEMPLATES.items():
        for marker in template.detection_files:
            if (path / marker).exists():
                scores[name] += 1

    # Fullstack bonus: both node and python markers present
    node_score = scores.get("node-dev", 0)
    python_score = scores.get("python-dev", 0)
    if node_score > 0 and python_score > 0:
        scores["fullstack"] = node_score + python_score + 1

    # Find best match
    best_name = max(scores, key=lambda k: scores[k])
    if scores[best_name] == 0:
        return TEMPLATES["base"]
    return TEMPLATES[best_name]


def get_template(name: str) -> ContainerTemplate | None:
    """Look up a template by name."""
    return TEMPLATES.get(name)


def list_templates() -> list[ContainerTemplate]:
    """Return all available templates."""
    return list(TEMPLATES.values())


def build_setup_script(template: ContainerTemplate) -> str:
    """Generate a bash setup script for container provisioning."""
    lines = [
        "#!/bin/bash",
        "set -e",
        f"# Container setup: {template.display_name}",
        "",
    ]

    # Export environment variables
    for key, value in template.env.items():
        lines.append(f"export {key}={value!r}")

    if template.env:
        lines.append("")

    # Run setup commands
    for cmd in template.setup_commands:
        lines.append(cmd)

    lines.append("")
    lines.append(f'echo "Template {template.name} setup complete"')
    return "\n".join(lines)
