# Phase 3: Implementation

**Goal:** Write working code that meets requirements.

---

## Checklist

- [ ] **Follow Test-Driven Development** (when applicable)
  1. Write test skeleton
  2. Write minimal code to pass
  3. Refactor
  4. Repeat

- [ ] **Implement Features in Order**
  - Start with core functionality
  - Add error handling
  - Add logging
  - Add validation

- [ ] **Follow Best Practices**
  - Language-specific conventions
  - Framework-specific patterns
  - Error handling patterns
  - Security best practices

- [ ] **Commit Frequently**
  ```bash
  git_add("{files}")
  git_commit("message: {clear description}")
  ```

- [ ] **Document as You Go**
  - Add comments for complex logic
  - Update README if needed
  - Document API endpoints

- [ ] **Track Progress**
  - Mark sub-tasks as complete
  - Note any deviations from plan
  - Log time spent

---

## Implementation Guidelines

### Code Quality

- **Functions should do one thing well**
- **Names should be descriptive**
- **Avoid code duplication** (DRY principle)
- **Handle errors gracefully**
- **Log important events**

### Testing Mindset

- **Write testable code**
- **Use dependency injection for mocking**
- **Avoid global state**
- **Keep functions pure when possible**

### Security

- **Validate all inputs**
- **Never hardcode secrets**
- **Use parameterized queries**
- **Sanitize user data**

---

## Common Patterns

### REST API (Node/Express)
```javascript
app.get('/api/resource', async (req, res) => {
  try {
    const data = await getResource();
    res.json(data);
  } catch (error) {
    logger.error(error);
    res.status(500).json({ error: 'Internal error' });
  }
});
```

### REST API (Python/FastAPI)
```python
@app.get("/api/resource")
async def get_resource():
    try:
        data = await get_resource()
        return data
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500)
```

### Error Handling
```javascript
// Validate input
if (!input || typeof input !== 'string') {
  throw new Error('Invalid input');
}

// Log error
logger.error('Operation failed', { error, context });

// Return safe error
return { error: 'Operation failed' };
```

---

## Time Budget

| Complexity | Time Budget |
|------------|-------------|
| Simple | 15-30 minutes |
| Medium | 30-90 minutes |
| Complex | 90-180 minutes |

---

## Next Phase

Once implementation is complete, proceed to **Phase 4: Testing & Validation**.
