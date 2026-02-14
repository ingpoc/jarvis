---
name: code-review-checklist
description: Systematic code review covering logic, security, performance, and style
max_uses_per_session: 3
confidence: 0.90
auto_generated: false
---

## Context

Bootstrap skill for performing thorough code reviews. Provides a
systematic checklist covering correctness, security, performance,
and maintainability.

## When to Use This Skill

Use when the user asks to:
- Review code changes
- Check code quality before merging
- Audit code for issues
- Review a pull request

## Prompt

You are performing a code review. Check each category systematically:

### 1. Correctness
- Does the code do what it claims to do?
- Are edge cases handled (null, empty, boundary values)?
- Are error conditions handled appropriately?
- Do loops terminate correctly?
- Are off-by-one errors avoided?

### 2. Security (OWASP Top 10)
- No SQL injection (use parameterized queries)
- No XSS (sanitize user input, use templating escaping)
- No command injection (avoid shell=True, sanitize inputs)
- No hardcoded secrets (API keys, passwords)
- No path traversal (validate file paths)
- Proper authentication/authorization checks
- Input validation at system boundaries

### 3. Performance
- No N+1 query patterns
- Appropriate use of caching
- No unnecessary re-renders (React) or recomputation
- Efficient data structures for the use case
- No memory leaks (event listeners, subscriptions cleaned up)
- Pagination for large data sets

### 4. Maintainability
- Clear naming (functions, variables, classes)
- Single responsibility (functions do one thing)
- No magic numbers (use named constants)
- Appropriate error messages
- Code is readable without extensive comments
- DRY but not over-abstracted

### 5. Testing
- New code has corresponding tests
- Tests cover happy path and error cases
- Tests are deterministic (no flaky tests)
- Mocks are appropriate (not testing implementation details)

### 6. API Design
- Consistent naming conventions
- Backward compatible changes
- Proper HTTP status codes
- Clear error response format

Output a structured review with:
- **Issues**: Things that must be fixed (with severity)
- **Suggestions**: Things that could be improved
- **Positive**: Things done well

## Examples

1. "Review this PR" -> Full checklist review of changes
2. "Check this code for security issues" -> Security-focused review
3. "Review the auth module" -> Module-level code review

## Validation

Pre-seeded bootstrap skill for the coding domain.
Checklist based on OWASP Top 10 and industry best practices.
