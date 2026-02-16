---
name: rest-endpoint-scaffold
description: Scaffold a complete REST API endpoint with CRUD operations, validation, and tests
max_uses_per_session: 3
confidence: 0.95
auto_generated: false
---

## Context

Bootstrap skill for scaffolding REST API endpoints. Works across frameworks
(Express, FastAPI, Flask, etc.) by detecting the project's stack first.

## When to Use This Skill

Use when the user asks to:
- Create a new API endpoint
- Add CRUD operations for a resource
- Scaffold REST routes
- Build an API controller

## Prompt

You are scaffolding a REST API endpoint. Follow this process:

1. **Detect the framework**: Check package.json (Express/Fastify/Koa), pyproject.toml/requirements.txt (FastAPI/Flask/Django), Cargo.toml (Actix/Axum), or go.mod (Gin/Echo).

2. **Determine the resource**: Extract the resource name from the user's request (e.g., "users", "products", "orders").

3. **Generate the endpoint files**:
   - Route/controller file with CRUD handlers (GET list, GET by ID, POST, PUT/PATCH, DELETE)
   - Request/response models or schemas with validation
   - Database model/migration if applicable
   - Test file with tests for each endpoint

4. **Follow project conventions**:
   - Match existing code style (indentation, naming, imports)
   - Use the same ORM/database client as existing code
   - Follow the existing directory structure

5. **Include proper error handling**:
   - 400 for validation errors
   - 404 for not found
   - 500 for server errors
   - Consistent error response format

## Examples

1. "Add a users API endpoint" -> Scaffold GET/POST/PUT/DELETE /api/users
2. "Create CRUD for products" -> Full product resource with validation
3. "Build an orders REST API" -> Orders endpoint with pagination

## Validation

Pre-seeded bootstrap skill for the coding domain.
Tested against Express, FastAPI, and Flask projects.
