---
name: dockerfile-generation
description: Generate optimized Dockerfiles from codebase analysis
max_uses_per_session: 3
confidence: 0.90
auto_generated: false
---

## Context

Bootstrap skill for generating production-ready Dockerfiles by analyzing
the project structure, dependencies, and runtime requirements.

## When to Use This Skill

Use when the user asks to:
- Create a Dockerfile for a project
- Containerize an application
- Optimize an existing Dockerfile
- Set up Docker Compose

## Prompt

You are generating a Dockerfile. Follow this process:

1. **Analyze the project**:
   - Detect language and framework (L1 context)
   - Identify the entry point (main file, start script)
   - List dependencies (package.json, requirements.txt, Cargo.toml, go.mod)
   - Check for build steps (TypeScript compilation, asset bundling)

2. **Select base image**:
   - Node.js: `node:20-slim` (or alpine for minimal)
   - Python: `python:3.12-slim`
   - Rust: `rust:1-slim` (multi-stage with `debian:bookworm-slim`)
   - Go: `golang:1.22` (multi-stage with `scratch` or `alpine`)

3. **Optimize the Dockerfile**:
   - Use multi-stage builds to reduce image size
   - Copy dependency files first, install, then copy source (layer caching)
   - Use `.dockerignore` to exclude node_modules, .git, etc.
   - Run as non-root user
   - Set appropriate EXPOSE ports
   - Use HEALTHCHECK if applicable

4. **Generate docker-compose.yml** if the project needs:
   - Database (PostgreSQL, MySQL, Redis, MongoDB)
   - Cache (Redis, Memcached)
   - Message queue (RabbitMQ, Kafka)
   - Reverse proxy (Nginx, Traefik)

5. **Add .dockerignore** with sensible defaults.

## Examples

1. "Create a Dockerfile for this Node.js app" -> Multi-stage Node Dockerfile
2. "Containerize this Python API" -> Slim Python image with gunicorn
3. "Add Docker support" -> Dockerfile + docker-compose.yml + .dockerignore

## Validation

Pre-seeded bootstrap skill for the coding domain.
Templates validated against Node.js, Python, Rust, and Go projects.
