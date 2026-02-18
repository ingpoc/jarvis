---
name: git-workflow
description: Execute standard git workflows - branch, commit, PR with conventional format
max_uses_per_session: 3
confidence: 0.95
auto_generated: false
---

## Context

Bootstrap skill for executing standard git workflows. Handles branching,
committing with conventional format, and PR creation.

## When to Use This Skill

Use when the user asks to:
- Create a feature branch
- Commit changes
- Create a pull request
- Follow git workflow conventions

## Prompt

You are managing git operations. Follow these conventions:

1. **Branch naming**:
   - Feature: `feature/<description>`
   - Bug fix: `fix/<description>`
   - Refactor: `refactor/<description>`
   - Use kebab-case: `feature/add-user-auth`

2. **Commit messages** (Conventional Commits):
   - Format: `type(scope): description`
   - Types: feat, fix, refactor, test, docs, chore, style, perf
   - Scope: module or component name
   - Description: imperative mood, lowercase, no period
   - Examples: `feat(auth): add JWT token validation`

3. **Workflow**:
   - Always check `git status` first
   - Stage only relevant files (not build artifacts or .env)
   - Run tests before committing
   - Create descriptive PR titles and bodies

4. **PR creation**:
   - Title: short summary (<70 chars)
   - Body: what changed, why, how to test
   - Link related issues

5. **Safety rules**:
   - Never force push to main/master
   - Never commit secrets or .env files
   - Always pull before push to avoid conflicts

## Examples

1. "Commit these changes" -> Stage, format message, commit
2. "Create a PR for this feature" -> Branch, push, create PR
3. "Set up feature branch for auth" -> Create and checkout branch

## Validation

Pre-seeded bootstrap skill for the coding domain.
Follows Conventional Commits specification.
