# ADR-0008: Panel-internal Redis

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D8

## Context

Celery, Channels, caching and login throttling need a fast shared store.

## Decision

Ubuntu `redis-server` (or `valkey-server`), Unix socket only, password protected, `maxmemory 64mb`, never used for user applications.

## Consequences

No TCP exposure. User apps that need Redis install their own instance from the App Store.
