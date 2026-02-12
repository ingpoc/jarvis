# Phase 1: Planning & Analysis

**Goal:** Clear understanding of requirements before writing any code.

---

## Checklist

- [ ] **Understand Requirements**
  - Read task description carefully
  - Identify functional requirements
  - Identify non-functional requirements (performance, security)
  - Ask clarifying questions if needed

- [ ] **Break Down Task**
  - Split into 3-7 sub-tasks
  - Identify dependencies between sub-tasks
  - Order sub-tasks logically

- [ ] **Assess Complexity**
  - Simple: 1-2 files, straightforward logic (< 30 min)
  - Medium: 3-10 files, some integration (30 min - 2 hrs)
  - Complex: 10+ files, multiple systems (2+ hrs)

- [ ] **Query Context Graph**
  ```bash
  # Search for similar decisions
  context_query_traces(query="{tech_stack} {use_case}", limit=5)
  ```
  - Example: "database choice for realtime app"
  - Example: "testing strategy for REST API"

- [ ] **Select Tech Stack**
  - Language: Python / Node.js / Rust / Go
  - Framework: Express / FastAPI / Actix
  - Database: PostgreSQL / MongoDB / SQLite
  - Testing: Jest / Pytest / Custom

- [ ] **Identify Risks**
  - Security concerns
  - Performance bottlenecks
  - External dependencies
  - Unknown APIs

- [ ] **Plan Container Setup**
  - Choose base image from templates
  - List required ports
  - List required volumes

---

## Output

After this phase, you should have:

```markdown
## Task: {task_name}

### Requirements
- {requirement_1}
- {requirement_2}

### Sub-tasks
1. {subtask_1}
2. {subtask_2}
3. {subtask_3}

### Tech Stack
- Language: {language}
- Framework: {framework}
- Database: {database}
- Testing: {testing_framework}

### Container Specs
- Image: {image_name}
- Ports: {ports}
- Volumes: {volumes}

### Context Graph Insights
- {relevant_past_decision_1}
- {relevant_past_decision_2}

### Risks
- {risk_1} -> {mitigation}
- {risk_2} -> {mitigation}

### Estimated Complexity
{simple|medium|complex}
```

---

## Time Budget

| Complexity | Time Budget |
|------------|-------------|
| Simple | 2-5 minutes |
| Medium | 5-10 minutes |
| Complex | 10-20 minutes |

---

## Next Phase

Once planning is complete, proceed to **Phase 2: Environment Setup**.
