# Memory Repository

Typed long-term memory for Jarvis. This is the continuity layer across sessions and runtimes.

## Retrieval Order

Load memory by priority under context budget constraints:

1. `critical`
2. `notable`
3. `background`

## Memory Types

| Folder | Category | Use for |
|---|---|---|
| `memory/decisions` | `decision` | Architecture and policy choices in effect |
| `memory/preferences` | `preference` | Stable user/style/runtime preferences |
| `memory/relationships` | `relationship` | Roles, ownership, and recurring collaborators |
| `memory/commitments` | `commitment` | Explicit promises with follow-up requirements |
| `memory/lessons` | `lesson` | Repeated failure patterns and their fixes |
| `memory/handoffs` | `handoff` | Transfer context between sessions/agents |

## Contract

Each note must:

- Use YAML frontmatter with required fields: `title`, `date`, `category`, `priority`, `status`, `source`, `tags`
- Live in the matching category folder
- Include sections: `## Context`, `## Memory`, `## Retrieval Cues`
- Be listed in `memory/INDEX.md`

## Enforcement

`python3 scripts/agent_docs_lint.py` enforces this contract.
