# Claude Agent SDK Python Capabilities (Built-In First)

Repository: `anthropics/claude-agent-sdk-python` (DeepWiki)

## Core Built-Ins To Use Before Custom Logic

| Area | Built-in capability | Practical use for Jarvis |
|------|----------------------|--------------------------|
| Client patterns | `query()` and `ClaudeSDKClient` | Use `query()` for one-shot, client for multi-turn orchestration |
| Streaming | Bidirectional message streaming | Real-time event-driven UX and orchestration |
| Session control | Session/fork options | Continue or branch long tasks |
| Permission gating | `can_use_tool` callback | Programmatic tool-level approval policy |
| Lifecycle hooks | Hook matchers/callbacks | Pre/post tool checks and context injection |
| Custom tools | In-process SDK MCP tools | Fast tool extensions without subprocess overhead |
| External integrations | External MCP server support | Combine SDK tools with existing MCP servers |
| Recovery | File checkpointing + rewind | Safe rollback for file-mutating tasks |
| Cost/limits | Budget/thinking/resource options | Bound runtime cost and effort |
| Isolation | Sandbox configuration | Restrict shell behavior at runtime |

## What Should Stay App-Level (Outside SDK)

1. Product workflow state machine and task routing policy.
2. Domain-specific business logic (trading, mail, etc.).
3. Persistence model decisions (beyond SDK session mechanics).
4. UI protocols and channel orchestration (WS/Slack/app behavior).
5. Learning-loop governance (which failures become policy/rules/docs).

## Recommended Optimization Order

1. Use `ClaudeSDKClient` + streaming as default execution core.
2. Add `can_use_tool` and lifecycle hooks before writing custom wrappers.
3. Implement high-frequency custom tools via SDK MCP first.
4. Add checkpoint/rewind for risky file operations.
5. Only then add app-specific orchestration layers for unmet requirements.

## Practical Boundary

If a requirement is "control Claude behavior around tool usage/session/lifecycle," prefer SDK options first.  
If requirement is "product-specific business workflow and cross-channel behavior," implement at Jarvis application layer.
