# Architecture Layers

Dependency direction enforcement.

---

## Layer Model

```
Types → Config → Repo → Service → Runtime → UI
                    ↑
              Providers (cross-cutting)
```

### Layer Definitions

| Layer | Contains | Depends On |
|-------|----------|------------|
| **Types** | Data models, schemas | Nothing |
| **Config** | Settings, env vars | Types |
| **Repo** | Data access, storage | Config |
| **Service** | Business logic | Repo |
| **Runtime** | Execution, daemons | Service |
| **UI** | Interface, API handlers | Runtime |
| **Providers** | Auth, telemetry, connectors | Config |

---

## Dependency Rules

| From | Can Import | Cannot Import |
|------|------------|---------------|
| Types | (nothing) | Everything |
| Config | Types | Repo, Service, UI |
| Repo | Config, Types | Service, UI |
| Service | Repo, Config, Types | UI |
| UI | All | (nothing restricted) |

---

## Jarvis Mapping

| Layer | Files |
|-------|-------|
| Types | `config.py` (models) |
| Config | `config.py` (settings) |
| Repo | `memory.py` |
| Service | `orchestrator/core.py` |
| Runtime | `daemon.py`, `ws_server.py` |
| UI | `orchestrator/core.py` |
| Providers | `self_learning.py`, `macos_native.py` |

---

## Enforcement

```bash
# Check layer violations (TODO: implement)
python scripts/check_layers.py
```

---

## Why This Matters

> "Architecture you postpone until 100s of engineers is prerequisite with agents."

Constraints enable speed without decay.
