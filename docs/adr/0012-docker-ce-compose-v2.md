# ADR-0012: Docker Engine CE + Compose v2

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D12

## Context

Apps, projects, databases and PHP runtimes run in containers.

## Decision

Docker Engine CE + Compose v2 plugin from the official Docker apt repository or a configured mirror. Existing Docker ≥ 24 with Compose v2 is reused.

## Consequences

Container ports are published on 127.0.0.1 by default; public exposure goes through DOCKER-USER rules.
