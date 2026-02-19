# Draw.io Diagram Generation (Distilled)

**Source**: Internal process note (original root source removed during docs cleanup)
**TL;DR**: Process guide for generating visual diagrams using draw.io with Mermaid, XML, or CSV formats, delivered via HTML artifacts.

## Opinion

**Verdict**: **Adopt**  
**Confidence**: **High**  
**Reasoning**: This is operational process documentation for a standard tool (draw.io). The process is well-defined, includes critical XML well-formedness rules, and provides a clear delivery mechanism via HTML artifacts. No validation needed - this is tool usage documentation.

### Claims Analysis

| Claim | Agree? | Evidence | Confidence |
|-------|--------|----------|------------|
| Draw.io supports multiple formats (Mermaid, XML, CSV) | Yes | Standard draw.io capability | High |
| HTML artifact delivery prevents URL corruption | Yes | Base64 compression in URLs is fragile | High |
| XML comments cannot contain `--` | Yes | XML spec requirement | High |
| Format selection matters (Mermaid vs XML vs CSV) | Yes | Different formats for different use cases | High |

## Key Principles

| Principle | Meaning |
|-----------|---------|
| **Format Selection** | Choose format based on diagram type: Mermaid for flowcharts/sequences, XML for complex layouts, CSV for hierarchical data |
| **Artifact Delivery** | Always deliver URLs via HTML artifacts, never retype compressed URLs |
| **XML Well-Formedness** | XML must be valid - no `--` in comments, escape special characters |
| **Tool Standardization** | Use draw.io as the standard diagram generation tool for visual artifacts |

## Patterns

| Before | After |
|--------|-------|
| Manually typing compressed URLs | Generate HTML artifact with embedded link |
| Guessing format | Select format based on diagram type |
| XML with `--` in comments | Use single hyphens or rephrase |
| Direct URL output | HTML page with clickable button |

## Anti-Patterns

| Anti-Pattern | Problem |
|--------------|---------|
| Retyping compressed URLs | Single character change breaks entire link |
| Using wrong format | Inefficient or impossible to represent |
| Invalid XML | Parse errors, broken diagrams |
| Direct URL in chat | User must manually copy/paste |

## Integration Notes

**Tier**: 1 (Reference)  
**Created**: 2026-02-18  
**Sessions Used**: 0  
**Promotion Status**: Process documentation (no promotion needed)

**Location**: `docs/workflow/draw-io-diagram-generation.md`  
**Category**: Operational process (tool usage)

**Overlap Check**:
- ✅ No existing diagram generation documentation found
- ✅ Complements existing workflow docs
- ✅ Fits in `docs/workflow/` as operational knowledge

**Action**: Integrated as workflow documentation. No changes to CLAUDE.md/AGENTS.md needed (operational process, not architectural principle).
