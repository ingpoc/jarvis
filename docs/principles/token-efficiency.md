# Token Efficiency

Context is scarce. Don't waste it.

---

## The Problem

| Waste | Impact |
|-------|--------|
| Raw data in context | Crowds out task |
| Repeated context | Redundant tokens |
| Verbose explanations | Lost signal |
| Full file reads | Unnecessary content |

---

## Token Budget

| Budget | Strategy |
|--------|----------|
| 100K tokens | On-demand loading |
| Large data | Sandbox execution (99% savings) |
| Skills | Progressive disclosure (98% savings) |
| Logs/CSV | Server-side processing (95-99% savings) |

---

## MCP Tools for Efficiency

| Tool | Use For | Savings |
|------|---------|---------|
| `execute_code` | Python/Bash/Node in sandbox | 98%+ |
| `process_csv` | CSV with filters | 99% |
| `process_logs` | Log pattern matching | 95% |
| `search_tools` | Find tools by keyword | 95% |
| `batch_process_csv` | Multiple CSVs | Batch |

---

## Loading Strategies

| Strategy | When | Example |
|----------|------|---------|
| **Read summary** | First | File head, not full |
| **Search then read** | Specific content | Grep pattern |
| **Delegate** | Large exploration | Spawn subagent |
| **Sandbox** | Data processing | `execute_code` |

---

## Anti-Patterns

| Anti-Pattern | Waste |
|--------------|-------|
| Read full file for 1 line | 99% waste |
| Load 1000-line log | 99% waste |
| Repeat context every turn | Cumulative |
| Verbose responses | Every message |

---

## Patterns

| Pattern | Savings |
|---------|---------|
| `head -n 50` vs full read | 90%+ |
| Grep pattern vs full file | 95%+ |
| `execute_code` for data | 98%+ |
| Subagent for exploration | 100% (out of context) |

---

## Rules

| Rule | Enforcement |
|------|-------------|
| Never load >50 items raw | Use MCP tools |
| Process before summarizing | Server-side |
| One feature at a time | Focus |
| Local over remote | Cache |

---

## Key Insight

> "Token efficiency is not optimization—it's survival. Every wasted token is less context for the task."
