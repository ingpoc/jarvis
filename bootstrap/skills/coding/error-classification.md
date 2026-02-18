---
name: error-classification
description: Classify and triage errors by type, severity, and suggest resolution approach
max_uses_per_session: 3
confidence: 0.90
auto_generated: false
---

## Context

Bootstrap skill for classifying errors encountered during development.
Routes errors to the appropriate resolution strategy based on type
and severity.

## When to Use This Skill

Use when encountering:
- Build errors or compilation failures
- Runtime errors or exceptions
- Test failures
- Linting or type checking errors
- Dependency resolution issues

## Prompt

You are classifying and triaging an error. Follow this process:

1. **Identify error type**:
   - **Syntax**: Missing brackets, invalid syntax, typos
   - **Type**: Type mismatch, undefined variable, wrong argument type
   - **Import**: Module not found, circular import, version mismatch
   - **Runtime**: Null reference, division by zero, index out of bounds
   - **Dependency**: Package not installed, version conflict, peer dependency
   - **Environment**: Missing env var, wrong Node/Python version, missing binary
   - **Logic**: Wrong algorithm, off-by-one, race condition

2. **Assess severity**:
   - **Critical**: App won't start, data corruption risk
   - **High**: Feature broken, tests failing
   - **Medium**: Degraded functionality, warning
   - **Low**: Style issue, minor inconsistency

3. **Determine resolution approach**:
   - Syntax/Type: Direct fix in code
   - Import: Check package.json/requirements.txt, install missing deps
   - Runtime: Add null checks, input validation, error handling
   - Dependency: Update versions, resolve conflicts
   - Environment: Check config, set env vars
   - Logic: Review algorithm, add test cases

4. **Check learning history**: Query known error patterns before attempting fix.

5. **Apply fix and verify**: Make the change, run tests, confirm resolution.

## Examples

1. "ModuleNotFoundError: No module named 'foo'" -> Import error, install package
2. "TypeError: Cannot read properties of undefined" -> Runtime null reference
3. "EADDRINUSE: address already in use" -> Environment port conflict

## Validation

Pre-seeded bootstrap skill for the coding domain.
Classification taxonomy based on common error categories.
