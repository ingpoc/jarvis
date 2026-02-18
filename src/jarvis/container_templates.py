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


# --- Docker Fallback ---

class DockerFallback:
    """Docker-based container runtime fallback.

    Used when Apple Containerization is unavailable (non-macOS or
    older macOS versions). Provides the same interface using Docker CLI.
    """

    def __init__(self):
        self._docker_available: bool | None = None

    def is_available(self) -> bool:
        """Check if Docker is installed and running."""
        if self._docker_available is not None:
            return self._docker_available

        import subprocess
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
            )
            self._docker_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._docker_available = False

        return self._docker_available

    def run_container(
        self,
        template: ContainerTemplate,
        workspace_path: str,
        workspace_dir: str = "/workspace",
        name: str | None = None,
    ) -> dict:
        """Start a Docker container using the given template.

        Args:
            template: Container template to use
            workspace_path: Host path to mount as workspace
            workspace_dir: Container path for workspace mount
            name: Optional container name

        Returns:
            dict with container_id and status
        """
        import subprocess

        cmd = ["docker", "run", "-d"]

        # Container name
        if name:
            cmd.extend(["--name", name])

        # Mount workspace
        cmd.extend(["-v", f"{workspace_path}:{workspace_dir}"])
        cmd.extend(["-w", workspace_dir])

        # Environment variables
        for key, value in template.env.items():
            cmd.extend(["-e", f"{key}={value}"])

        # Image
        cmd.append(template.base_image)

        # Keep container running
        cmd.extend(["tail", "-f", "/dev/null"])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                return {
                    "status": "error",
                    "error": result.stderr.strip(),
                }

            container_id = result.stdout.strip()[:12]

            # Run setup commands
            for setup_cmd in template.setup_commands:
                subprocess.run(
                    ["docker", "exec", container_id, "bash", "-c", setup_cmd],
                    capture_output=True,
                    timeout=120,
                )

            return {
                "status": "running",
                "container_id": container_id,
                "backend": "docker",
            }

        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return {"status": "error", "error": str(e)}

    def exec_in_container(self, container_id: str, command: str) -> dict:
        """Execute a command in a running Docker container."""
        import subprocess

        try:
            result = subprocess.run(
                ["docker", "exec", container_id, "bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=300,
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "stdout": "", "stderr": "Command timed out"}

    def stop_container(self, container_id: str) -> bool:
        """Stop and remove a Docker container."""
        import subprocess

        try:
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                capture_output=True,
                timeout=30,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """Get logs from a Docker container."""
        import subprocess

        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", str(tail), container_id],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout + result.stderr
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""


# Singleton fallback instance
_docker_fallback: DockerFallback | None = None


def get_docker_fallback() -> DockerFallback:
    """Get the Docker fallback runtime."""
    global _docker_fallback
    if _docker_fallback is None:
        _docker_fallback = DockerFallback()
    return _docker_fallback
