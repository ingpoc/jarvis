# Phase 4: Testing & Validation

**Goal:** Ensure code works correctly and handles edge cases.

---

## Checklist

- [ ] **Unit Tests**
  - Test all functions/methods
  - Test edge cases
  - Test error conditions
  - Achieve >80% coverage

- [ ] **Integration Tests**
  - Test component interactions
  - Test with real dependencies (or mocks)
  - Test data flow

- [ ] **Browser Testing** (if web app)
  ```bash
  # Setup browser testing
  browser_setup(container_id, "chromium")

  # Navigate to app
  browser_navigate(container_id, "http://localhost:3000", ...)

  # Test interactions
  browser_interact(container_id, actions=[...])
  ```

- [ ] **API Testing** (if API)
  ```bash
  browser_api_test(
    method: "GET",
    url: "http://localhost:3000/api/test",
    expected_status: 200
  )
  ```

- [ ] **Fix Failures** (max 100 iterations)
  - Read error messages
  - Identify root cause
  - Fix issue
  - Re-run test
  - Repeat until pass

- [ ] **Document Test Results**
  - Pass/fail count
  - Coverage percentage
  - Known issues

---

## Test Categories

### 1. Happy Path Tests
- Normal usage scenarios
- Expected inputs
- Expected outputs

### 2. Edge Case Tests
- Empty inputs
- Null/undefined values
- Boundary values
- Large datasets

### 3. Error Tests
- Invalid inputs
- Network failures
- Database errors
- Timeout scenarios

### 4. Security Tests
- SQL injection attempts
- XSS attempts
- Authentication bypass
- Rate limiting

---

## Test Framework Examples

### Node.js (Jest)
```javascript
describe('API Endpoint', () => {
  test('should return data', async () => {
    const response = await fetch('/api/data');
    expect(response.status).toBe(200);
    expect(await response.json()).toHaveProperty('data');
  });

  test('should handle errors', async () => {
    const response = await fetch('/api/invalid');
    expect(response.status).toBe(404);
  });
});
```

### Python (Pytest)
```python
def test_get_data():
    response = client.get("/api/data")
    assert response.status_code == 200
    assert "data" in response.json()

def test_error_handling():
    response = client.get("/api/invalid")
    assert response.status_code == 404
```

---

## Browser Testing with Playwright

### Setup
```bash
browser_setup(container_id, "chromium")
```

### Navigate and Test
```bash
browser_navigate(
  container_id,
  url="http://localhost:3000",
  screenshot_path="/workspace/test-screenshots/home.png",
  wait_for="networkidle"
)
```

### Interact with Elements
```bash
browser_interact(
  container_id,
  url="http://localhost:3000",
  actions=[
    "fill(#username, testuser)",
    "fill(#password, password123)",
    "click(#login-button)",
    "waitForNavigation()"
  ]
)
```

---

## Test Results Template

```markdown
## Test Results for {task_name}

### Summary
- Total Tests: {count}
- Passed: {count}
- Failed: {count}
- Coverage: {percentage}%

### Unit Tests
{results}

### Integration Tests
{results}

### Browser Tests
{results}

### Fixed Issues
1. {issue_1} -> {fix}
2. {issue_2} -> {fix}

### Time Spent
{duration}
```

---

## Quality Gates

❌ **Must Pass:**
- All unit tests
- All integration tests
- >80% code coverage
- No critical security issues

⚠️ **Warnings:**
- Coverage between 60-80%
- Some edge cases not tested
- Performance degradation noted

---

## Time Budget

| Complexity | Time Budget |
|------------|-------------|
| Simple | 10-20 minutes |
| Medium | 20-40 minutes |
| Complex | 40-90 minutes |

---

## Next Phase

Once all tests pass, proceed to **Phase 5: Review & Quality Gates**.
