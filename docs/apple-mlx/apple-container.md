# Apple Container System (Distilled)

**Source**: [github.com/apple/container](https://github.com/apple/container)

**TL;DR**: Linux containers as lightweight VMs on macOS using Apple Virtualization + vmnet frameworks. XPC-based distributed architecture.

---

## Core Architecture

```
CLI (container) ──XPC──> container-apiserver ──XPC──> Helper Services
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
            container-core    container-network   container-runtime
              -images           -vmnet             -linux
```

---

## Core Services

| Service | Role | Key Routes |
|---------|------|------------|
| `container-apiserver` | Central orchestrator | Starts services, handles XPC routes |
| `container-core-images` | Image management | `imagePull`, `imageList`, `imageDelete` |
| `container-network-vmnet` | Virtual networking | `allocate`, `deallocate`, `lookup` |
| `container-runtime-linux` | Per-container VM | `bootstrap`, `createProcess`, `stop`, `kill` |

---

## XPC Communication

| Component | Purpose |
|-----------|---------|
| `XPCMessage` | Structured key-value message across process boundaries |
| `XPCServer` | Services expose routes via XPCServer |
| `XPCClient` | Client sends XPCMessage requests to services |
| Routes | Route system directs messages to handlers |

**Pattern**: All inter-service communication via XPC (secure, type-safe).

---

## Networking

| Component | Purpose |
|-----------|---------|
| `NetworksService` | Manages network configs, interacts with plugins |
| `NetworkVmnetHelper` | Interfaces with vmnet framework |
| `ReservedVmnetNetwork` | macOS 26+, deterministic subnet allocation |
| `AllocationOnlyVmnetNetwork` | Fallback for older macOS |
| `DNSServer` | Resolves container hostnames (127.0.0.1:2053) |

---

## Key Concepts

| Concept | How It Works |
|---------|--------------|
| **CLI → API Server** | ContainerClient uses XPC to communicate |
| **API Server as Orchestrator** | Central control, initializes all services |
| **Per-Container Helper** | Each container gets its own `container-runtime-linux` |
| **vmnet Isolation** | NAT-based virtual networks per container |
| **Plugin Architecture** | PluginLoader discovers/loads extensions |

---

## Container Lifecycle

```
1. User: container create
2. CLI → XPC → container-apiserver
3. apiserver launches container-runtime-linux helper
4. helper creates VM-backed container
5. helper manages: VM, processes, networking
```

---

## Compressed Index Format

For AGENTS.md/CLAUDE.md in projects using Apple Containers:

```
[Apple Container Index]|root: ./docs/containers
|IMPORTANT: Prefer retrieval-led reasoning for Apple Container APIs
|TRIGGERS:
|container errors → debugging.md#container-errors
|network issues → debugging.md#network-issues
|XPC communication → architecture.md#xpc
|services:{apiserver.md,images.md,networking.md,runtime.md}
```

---

## Apply to Jarvis

| Apple Container Concept | Jarvis Usage |
|------------------------|--------------|
| `container-runtime-linux` | Execute code in isolated VM |
| `container-network-vmnet` | Network isolation for sandbox |
| XPC communication | Not used (Python, not Swift) |
| vmnet framework | NAT for container networking |

---

## CLI Quick Reference

```bash
# List containers
container list

# Create container
container create --name mycontainer myimage

# Run command in container
container exec mycontainer ls /

# Stop container
container stop mycontainer

# Delete container
container delete mycontainer
```

---

## Integration Notes

**Tier**: 1 (Reference)
**Created**: 2026-02-17
**Sessions Used**: 0
**Outcomes**: (pending validation)

### Reasoning

1. **What problem does this solve?** Understanding Apple Container architecture for Jarvis execution
2. **Do we have this problem?** Yes - Jarvis uses Apple Containers for execution
3. **Is this the best solution we've seen?** Yes - official Apple documentation
4. **Can we verify it works?** Yes - can test with container CLI
5. **Does it align with existing principles?** Yes - agent-first, isolation

### Promotion Status

- [ ] Tier 1 → Tier 2 (needs 2+ sessions with container debugging)
- [ ] Tier 2 → Tier 3 (needs 5+ sessions, proven essential)

**Pending**: Test container integration with Jarvis, validate networking patterns
