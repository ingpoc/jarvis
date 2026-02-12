# Phase 2: Environment Setup

**Goal:** Create isolated, reproducible development environment.

---

## Checklist

- [ ] **Create Container**
  ```bash
  container_run(
    image: "{selected_image}",
    name: "jarvis-task-{timestamp}",
    volumes: "{local_path}:/workspace",
    ports: "{required_ports}",
    env: "{required_env_vars}",
    cpus: 2,
    memory: "4G"
  )
  ```

- [ ] **Verify Container**
  - Check container status: `container_status == "running"`
  - Test connectivity: `container_exec("echo 'ready'")`
  - Note container_id for later cleanup

- [ ] **Install Dependencies**
  ```bash
  # Node.js
  container_exec("npm install")

  # Python
  container_exec("pip install -r requirements.txt")

  # System packages
  container_exec("apt-get update && apt-get install -y {packages}")
  ```

- [ ] **Setup Project Structure**
  ```bash
  container_exec("mkdir -p /workspace/{src,tests,docs}")
  ```

- [ ] **Configure Environment**
  - Set environment variables
  - Create config files
  - Initialize git (if needed)

- [ ] **Verify Setup**
  - Test language runtime (node --version, python --version)
  - Test import of main dependencies
  - Log setup time

---

## Container Templates Reference

### Node.js 20
```json
{
  "image": "node:20-bullseye",
  "ports": "3000:3000",
  "volumes": "{local_path}:/workspace",
  "cpus": 2,
  "memory": "4G"
}
```

### Python 3.11
```json
{
  "image": "python:3.11-slim",
  "ports": "8000:8000",
  "volumes": "{local_path}:/workspace",
  "cpus": 2,
  "memory": "4G"
}
```

### Full Stack (Node + Postgres)
```json
{
  "image": "node:20-bullseye",
  "ports": "3000:3000,5432:5432",
  "volumes": "{local_path}:/workspace",
  "env": "POSTGRES_PASSWORD=test",
  "cpus": 4,
  "memory": "8G"
}
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Container won't start | Check image name, verify ports not in use |
| Install fails | Check network, try different registry |
| Permission denied | Check volume mount permissions |
| Out of memory | Increase memory allocation |

---

## Time Budget

| Complexity | Time Budget |
|------------|-------------|
| Simple | 2-5 minutes |
| Medium | 5-10 minutes |
| Complex | 10-20 minutes |

---

## Next Phase

Once environment is ready, proceed to **Phase 3: Implementation**.
