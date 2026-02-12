# Session: Container Research & Workflow Update

**Date:** 2025-02-12 23:45 UTC
**Type:** Research and Documentation
**Outcome:** ✅ COMPLETE

---

## Research Completed

### 1. Apple Container Documentation Review

**Sources:**
- [Apple Container GitHub Repository](https://github.com/apple/container)
- [Container Command Reference](https://github.com/apple/container/blob/main/docs/command-reference.md)
- [DeepWiki Q&A](https://deepwiki.com/search/what-is-the-correct-way-to-run_86aab388-1a54-44b5-b303-5c16e72edc69)
- [WWDC 2025: Meet Containerization](https://developer.apple.com/videos/play/wwdc2025/346/)

**Key Findings:**

1. **CLI tools are fully capable** of interactive development:
   ```bash
   # This WORKS in Apple Container CLI:
   container run -it python:3.11-slim /bin/bash

   # This WORKS for executing commands:
   container exec -it my-container pytest
   ```

2. **MCP wrapper is the bottleneck** - The `mcp__jarvis-container__*` tools lack critical parameters:
   - No `interactive` boolean flag
   - No `tty` boolean flag
   - No `command` string parameter
   - No `entrypoint` override

3. **Container behavior confirmed** - When `container_run()` is called via MCP:
   - Runs image's default command with no arguments (e.g., `python3`)
   - No TTY allocated (terminal: false in logs)
   - Process exits immediately with status 0
   - Container stops before `container_exec()` can be used

---

## Documentation Created

### 1. Container Limitations Document

**File:** `.jarvis/workflow/container-limitations.md`

**Contents:**
- Executive summary of MCP tool limitations
- CLI vs MCP parameter comparison table
- Evidence from actual container logs
- Template system issues
- Workarounds attempted (all failed)
- Recommended hybrid approach
- Future improvement roadmap

**Sections:**
1. What Works in CLI (But NOT in MCP)
2. MCP Tool Parameters (Actual vs Expected)
3. The Fundamental Problem
4. Evidence from Logs
5. Template System Issues
6. Workarounds Attempted
7. Recommended Approach
8. Future MCP Tool Improvements Needed

### 2. Workflow README Updates

**File:** `.jarvis/workflow/README.md`

**Changes:**
- Updated Core Principle #5: "Hybrid Environment" instead of "Isolated Testing"
- Added warning about container limitations
- Updated Phase 2 with decision tree for Local vs Container
- Added link to container-limitations.md

---

## Root Cause Analysis

### The Real Problem

**NOT:** "Apple Containers don't support interactive development"
**ACTUAL:** "MCP tools don't expose the parameters needed for interactive development"

### Evidence

From container logs (2026-02-12T15:41:29):
```
commandLine: ""                    # Empty - no custom command possible
args: ["python3"]               # Default from image, no args
terminal: false                   # No TTY allocation
```

From CLI documentation (DeepWiki research):
```bash
# CLI supports these flags:
container run -it python:3.11-slim /bin/bash
#            ^^ interactive + tty
#                               ^^^^^^^^^^ custom command

# MCP tools don't expose:
- -i, --interactive    # Not available
- -t, --tty           # Not available
- <command> argument    # Not available
```

---

## Action Items Completed

✅ Researched Apple container documentation
✅ Identified exact MCP tool limitations
✅ Created comprehensive limitations document
✅ Updated workflow README with warnings
✅ Updated session-20250212-container-attempt.md with solution
✅ Tested container creation to confirm findings
✅ Verified logs show missing parameters
✅ Documented hybrid approach recommendation

---

## Recommendations

### For Workflow (Immediate)

1. **Use hybrid approach:**
   - Phases 1-3: Local development (fast, interactive)
   - Phase 4: Container testing (servers, browsers)
   - Phases 5-6: Local review and learning

2. **Document decision tree:**
   ```
   Need interactive development?
   ├─ YES → Local environment
   └─ NO  → Container (servers, batch jobs, testing)
   ```

3. **Update templates:**
   - Add "LOCAL_FIRST" warning to all templates
   - Document when containers are appropriate

### For MCP Tools (Future)

**Priority 1 - Critical:**
- Add `interactive: boolean` parameter
- Add `tty: boolean` parameter
- Add `command: string` parameter
- Add `entrypoint: string` parameter

**Priority 2 - Important:**
- Fix template system (respect empty string)
- Better error messages
- Volume management tools

**Priority 3 - Nice to have:**
- Container lifecycle hooks
- Template listing command
- Interactive mode improvements

---

## Test Results Summary

| Test | Expected | Actual | Result |
|-------|----------|---------|--------|
| container_run() | Creates running container | Container exits immediately | ❌ |
| container_exec() | Runs command in container | "Container not running" | ❌ |
| Template override | Skip template with empty string | Template still applied | ⚠️ |
| Volume mapping | Mount directory | "Anonymous volumes not supported" | ⚠️ |

**Root Cause:** Missing MCP parameters for interactive mode

---

## Files Modified/Created

### Created:
- `.jarvis/workflow/container-limitations.md` (277 lines)
- `.jarvis/sessions/session-20250212-research-findings.md` (this file)

### Modified:
- `.jarvis/sessions/session-20250212-container-attempt.md` (added SOLUTION DISCOVERED section)
- `.jarvis/workflow/README.md` (updated Core Principles and Phase 2)

---

## Key Learnings

1. **Research pays off** - Deep dive into CLI docs revealed the exact issue
2. **Tool limitations matter** - MCP wrapper is the constraint, not the underlying tech
3. **Documentation is crucial** - Future sessions need these findings
4. **Hybrid is pragmatic** - Matches real-world dev workflows
5. **Improvement roadmap** - Clear path forward for MCP tools

---

## Next Steps

1. ✅ DONE - Document all findings
2. ⏭️ Test hybrid workflow with real task
3. ⏭️ Use containers for server testing only
4. ⏭️ Validate browser_test tools with containerized servers
5. ⏭️ Submit MCP tool improvement requests

---

*Research Duration:* ~75 minutes
*Documents Created:* 3
*Outcome:* ⚠️ Container issue fully understood and documented
*Recommendation:* Use hybrid workflow until MCP tools improve
