# ADR-0005: Realtime with Django Channels on Uvicorn

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D5

## Context

Live task logs, monitoring and terminals require WebSockets.

## Decision

Django Channels 4 (ASGI) served by Uvicorn; channel layer on Redis (in-memory layer in tests/dev).

## Consequences

A single ASGI process serves HTTP and WebSockets. Redis becomes a hard runtime dependency in production.
