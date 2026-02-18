#!/usr/bin/env python3
"""
Generate compressed docs index for AGENTS.md/CLAUDE.md.

Usage:
    python scripts/generate-agents-md-index.py [--output AGENTS.md]

Based on Vercel research: compressed 8KB index achieved 100% pass rate vs skills at 79%.
https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals
"""

import argparse
import os
from pathlib import Path
from typing import Dict, List


def scan_docs_directory(docs_dir: Path) -> Dict[str, List[str]]:
    """Scan docs directory and return structure."""
    structure = {}

    if not docs_dir.exists():
        return structure

    for subdir in sorted(docs_dir.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith('.'):
            files = sorted([
                f.name for f in subdir.iterdir()
                if f.suffix == '.md' and f.name != 'README.md'
            ])
            if files:
                structure[subdir.name] = files

    return structure


def generate_index(project_name: str, docs_dir: Path, triggers: List[str]) -> str:
    """Generate compressed index block."""

    structure = scan_docs_directory(docs_dir)

    lines = [
        f"[{project_name} Docs Index]|root: ./docs",
        f"|IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning for {project_name} tasks",
    ]

    # Add triggers
    if triggers:
        lines.append("|TRIGGERS:")
        for trigger in triggers:
            lines.append(f"|{trigger}")

    # Add directory listings
    for dir_name, files in structure.items():
        files_str = ",".join(files)
        lines.append(f"|{dir_name}:{{{files_str}}}")

    return "\n".join(lines)


def generate_full_agents_md(project_name: str, index_block: str) -> str:
    """Generate full AGENTS.md content."""

    return f'''# {project_name}

Agent-first development. Humans steer, agents execute.

---

## Docs Index

```
{index_block}
```

---

## Quick Start

| Task | Command |
|------|---------|
| Start | `./start-{project_name.lower()}.sh` |
| Stop | `./stop-{project_name.lower()}.sh` |
| Test | `pytest` |
| Lint | `ruff check .` |

---

## Critical Rules

### Common Errors

<!-- Add project-specific common errors here -->

### Logs & Cache

| Path | Use |
|------|-----|
| `~/.{project_name.lower()}/logs/` | Runtime logs |

---

## Verification

- [ ] Tests pass (exit code 0)
- [ ] Lint passes
- [ ] Service healthy

---

## Conventions

| Area | Rule |
|------|------|
| Git | No force-push main, no amend, no --no-verify |
| Tools | Token-efficient MCP for large data |
'''


def main():
    parser = argparse.ArgumentParser(description='Generate compressed docs index')
    parser.add_argument('--project', default='Jarvis', help='Project name')
    parser.add_argument('--docs-dir', default='docs', help='Docs directory')
    parser.add_argument('--output', default='AGENTS.md', help='Output file')
    parser.add_argument('--index-only', action='store_true', help='Output only the index block')
    parser.add_argument('--triggers', nargs='*', default=[
        'daemon/ws changes → jarvis/debugging.md',
        'adding API → jarvis/api-reference.md',
        'tests failing → principles/determinism.md',
        'large data → principles/token-efficiency.md',
    ], help='Task triggers (format: "pattern → path")')

    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    index_block = generate_index(args.project, docs_dir, args.triggers)

    if args.index_only:
        print(index_block)
    else:
        content = generate_full_agents_md(args.project, index_block)

        if args.output == '-':
            print(content)
        else:
            output_path = Path(args.output)
            output_path.write_text(content)
            lines = len(content.split('\n'))
            bytes_count = len(content.encode('utf-8'))
            print(f"Generated {args.output}: {lines} lines, {bytes_count} bytes")

            # Check size targets
            if lines > 80:
                print(f"⚠️  Warning: {lines} lines exceeds target of 80")
            if bytes_count > 2000:
                print(f"⚠️  Warning: {bytes_count} bytes exceeds target of 2000")


if __name__ == '__main__':
    main()
