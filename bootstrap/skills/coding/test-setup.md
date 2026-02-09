---
name: test-setup
description: Initialize test framework and write tests for existing code
max_uses_per_session: 3
confidence: 0.95
auto_generated: false
---

## Context

Bootstrap skill for setting up testing infrastructure and writing
tests for existing code. Detects the appropriate test framework
and follows project conventions.

## When to Use This Skill

Use when the user asks to:
- Set up testing for a project
- Add tests to existing code
- Configure a test runner
- Write unit tests, integration tests, or e2e tests

## Prompt

You are setting up tests for a project. Follow this process:

1. **Detect existing test setup**:
   - Check for jest.config.js, vitest.config.ts, pytest.ini, pyproject.toml [tool.pytest], etc.
   - If tests already exist, follow their patterns exactly

2. **If no test framework exists, set one up**:
   - JavaScript/TypeScript: Vitest (preferred) or Jest
   - Python: pytest with pytest-asyncio if needed
   - Rust: built-in cargo test
   - Go: built-in go test

3. **Write tests following best practices**:
   - Test file naming: `test_*.py`, `*.test.ts`, `*_test.go`
   - Test structure: Arrange-Act-Assert pattern
   - Cover: happy path, edge cases, error cases
   - Mock external dependencies (APIs, databases, file system)
   - Use descriptive test names that explain what is being tested

4. **Include setup/teardown**:
   - Fixtures for common test data
   - Database cleanup between tests
   - Mock server setup for API tests

5. **Run the tests** after writing them to verify they pass.

## Examples

1. "Add tests for the auth module" -> Write unit tests for authentication
2. "Set up testing" -> Install test framework, configure, write first test
3. "Write integration tests for the API" -> API test suite with mock server

## Validation

Pre-seeded bootstrap skill for the coding domain.
Validated against Python, JavaScript, and TypeScript projects.
