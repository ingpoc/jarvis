# Apple Container MCP Tool Limitations

**Last Updated:** 2025-02-12
**Status:** ⚠️ CRITICAL LIMITATIONS IDENTIFIED

---

## Executive Summary

After extensive testing and research, the **MCP container tools (`mcp__jarvis-container__*`) have critical limitations** that prevent them from being used for interactive development workflows.

**Bottom Line:** The Apple `container` CLI tool supports interactive mode, but the MCP wrapper does NOT expose the necessary parameters.

---

## What Works in CLI (But NOT in MCP)

### Apple Container CLI (Full Feature Set)

```bash
# ✅ Interactive shell - WORKS in CLI
container run -it python:3.11-slim /bin/bash

# ✅ Execute commands in running container - WORKS in CLI
container exec -it my-container pytest

# ✅ Custom entrypoint - WORKS in CLI
container run --entrypoint /bin/sh python:3.11-slim

# ✅ Long-running process - WORKS in CLI
container run -d python:3.11-slim sleep infinity
```

### MCP Container Tools (Limited Feature Set)

```python
# ❌ No interactive flag available
container_run(
    image="python:3.11-slim",
    name="mydev",
    # NO: interactive, tty, command, entrypoint params
)

# ❌ Container exits immediately because:
# - Runs python3 with no args
# - No TTY allocated
# - No way to override entrypoint
```

---

## MCP Tool Parameters (Actual vs Expected)

### container_run Parameters

| Parameter | Available | Notes |
|------------|-----------|--------|
| `image` | ✅ | Works |
| `name` | ✅ | Works |
| `volumes` | ⚠️ | Requires named volumes, rejects anonymous |
| `ports` | ✅ | Works |
| `env` | ✅ | Works |
| `cpus` | ✅ | Works |
| `memory` | ✅ | Works |
| `ssh_forward` | ✅ | Works |
| `template` | ⚠️ | Applies even with empty string |
| **`interactive`** | ❌ | **MISSING** |
| **`tty`** | ❌ | **MISSING** |
| **`command`** | ❌ | **MISSING** |
| **`entrypoint`** | ❌ | **MISSING** |

### container_exec Parameters

| Parameter | Available | Notes |
|------------|-----------|--------|
| `command` | ✅ | Works |
| `workdir` | ✅ | Works |
| `env` | ✅ | Works |
| `timeout` | ✅ | Works |

**However:** container_exec only works if container is RUNNING, which requires container_run to keep it alive.

---

## The Fundamental Problem

### When container_run is Called:

```
1. MCP creates container with: image, name, volumes, ports, env, cpus, memory, ssh_forward, template
2. Template applies (python-dev, node-dev, etc.)
3. Container starts with DEFAULT command from image (e.g., "python3")
4. Default command has NO ARGUMENTS → exits immediately
5. vminitd sees exit code 0 → shuts down container
6. container_exec fails → "container not running"
```

### What Should Happen (CLI):

```
1. User runs: container run -it python:3.11-slim /bin/bash
2. Container starts with: interactive=true, tty=true, command=/bin/bash
3. /bin/bash KEEPS RUNNING (waits for input)
4. Container stays alive
5. User can run: container exec -it <container> pytest
```

---

## Evidence from Logs

### Container Creation Log Analysis

```
2026-02-12T15:41:29+0000 info vminitd : id=jarvis-keep-alive-test [vminitd] starting managed process
...
commandLine: ""                    # ← Empty! No custom command
args: ["python3"]               # ← Default from image
terminal: false                   # ← No TTY allocated!
...
2026-02-12T15:41:29+0000 debug vminitd : count=0 pid=74 status=0 [vminitd] managed process exit
2026-02-12T15:41:29+0000 info vminitd : id=jarvis-keep-alive-test status=0 [vminitd] managed process exit
```

**Process Exit Status:** 0 (normal exit, not crash)
**Cause:** `python3` with no arguments exits immediately
**Result:** Container stops before container_exec can be used

---

## Template System Issues

### Problem 1: Template Applies Despite Empty String

```python
# Attempt to disable template:
container_run(..., template="")  # Empty string

# Result from logs:
"template": "python-dev"  # STILL APPLIED!
```

### Problem 2: Template Failure Crashes Container

```
"setup_exit_code": 1  # Template script failed
# Container starts anyway but may be in bad state
```

### Problem 3: No Template Documentation

- Available templates: `python-dev`, `node-dev`, others unknown
- No way to list available templates
- No way to see what template does
- Cannot customize template behavior

---

## Workarounds Attempted

### ❌ Attempt 1: Sleep Infinity

```bash
# Would work in CLI:
container run -d python:3.11-slim sleep infinity

# But MCP has no 'command' parameter to specify this
```

### ❌ Attempt 2: Background Process

```bash
# Can't specify command to run in background:
container_run(..., command="tail -f /dev/null")  # No 'command' param
```

### ❌ Attempt 3: Quick container_exec

```python
# Create container (stops immediately)
container_run(...)

# Try to exec before fully stopped
container_exec(...)  # Error: "container not running"
```

### ❌ Attempt 4: Named Volumes

```python
# Anonymous volumes rejected:
volumes="/tmp/myproject:/workspace"  # Error

# Would need to pre-create named volumes
# But no MCP tool to manage volumes!
```

---

## Recommended Approach

### For JARVIS Workflow:

1. **Use Local Development** (Primary)
   - Faster iteration
   - Full interactivity
   - Native debugging
   - No container overhead

2. **Use Containers for Specific Tasks** (Secondary)
   - **Server Testing:** Start long-running server process
   - **Browser Testing:** Use browser_test tools with server in container
   - **Production Simulation:** Test deployment-like environment
   - **Isolation Testing:** Verify dependencies work correctly

3. **When to Use Containers:**
   ```python
   # ✅ Good for container workflow:
   - Start web server: container_run with ports mapped
   - Run integration tests: Server already running
   - Browser automation: browser_navigate to localhost:port

   # ❌ Bad for container workflow:
   - Interactive development (no shell access)
   - Command execution (container stops too fast)
   - Package installation (no persistent shell)
   - Debugging (no TTY for breakpoints)
   ```

---

## Future MCP Tool Improvements Needed

### High Priority:

1. **Add `interactive` boolean flag**
   - Maps to CLI `-i` flag
   - Keeps STDIN open

2. **Add `tty` boolean flag**
   - Maps to CLI `-t` flag
   - Allocates pseudo-TTY for shell

3. **Add `command` string parameter**
   - Override default image command
   - Specify custom entrypoint
   - Enable "sleep infinity" pattern

4. **Fix template system**
   - Respect empty string (no template)
   - Document available templates
   - List template with `--template-list`

5. **Add volume management tools**
   - `container_volume_create()`
   - `container_volume_list()`
   - `container_volume_delete()`

### Medium Priority:

6. **Better error messages**
   - "Anonymous volumes not supported" → suggest how to create named volume
   - "Container not running" → explain why and how to fix

7. **Container lifecycle hooks**
   - `on_start` callback when container ready
   - `on_exit` callback when container stops
   - Enable "run command immediately after start" pattern

---

## References

- [Apple Container GitHub Repository](https://github.com/apple/container)
- [Container Command Reference](https://github.com/apple/container/blob/main/docs/command-reference.md)
- [DeepWiki: Apple Container Commands](https://deepwiki.com/search/what-is-the-correct-way-to-run_86aab388-1a54-44b5-b303-5c16e72edc69)
- [WWDC 2025: Meet Containerization](https://developer.apple.com/videos/play/wwdc2025/346/)

---

## Summary

**The MCP container tools are fundamentally limited compared to the Apple container CLI.**

While the CLI supports full interactive development with `-it` flags and custom commands, the MCP wrapper:
- Exposes only ~40% of CLI parameters
- Cannot allocate TTY for interactive shells
- Cannot override default commands
- Cannot keep containers alive for subsequent commands
- Applies templates even when disabled

**Recommendation:** Use hybrid workflow - local development + container-based server testing. This works within current MCP limitations while still leveraging container isolation for final validation.
